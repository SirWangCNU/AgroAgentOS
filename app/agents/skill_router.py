from __future__ import annotations

from loguru import logger
from pydantic import BaseModel, Field

from app.agents.state import PlanExecuteState
from app.core.llm import get_chat_llm
from app.core.structured import ainvoke_structured
from app.runtime.agent_harness import get_agent_harness
from app.runtime.transitions import (
    ROUTER_FALLBACK_GENERIC,
    ROUTER_LLM_FAILED,
    ROUTER_OK,
    ROUTER_OUT_OF_SCOPE,
    make_transition,
)
from app.skills.registry import GENERIC_SKILL_NAME, get_skill_registry


class SkillChoice(BaseModel):
    is_oncall: bool = Field(default=True, description="用户输入是否属于农业领域范围")
    skill_name: str = Field(..., description="选中的 Skill name (snake_case), 必须是给定菜单中已存在的项")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="路由置信度, 0 到 1")
    reason: str = Field(default="", description="一句话说明为什么选这个 Skill, 用于可观测")


# 农业领域关键词
_AGRICULTURE_KEYWORDS = (
    "种植", "播种", "栽培", "育苗", "插秧", "施肥", "肥料", "追肥", "底肥", "复合肥",
    "病虫害", "打药", "农药", "虫害", "病害", "杀虫", "杀菌", "除草", "除虫",
    "灌溉", "浇水", "排水", "补水", "浇灌", "喷灌", "滴灌",
    "收获", "采收", "收割", "采摘", "丰收",
    "天气", "温度", "降雨", "风速", "气象", "气温", "降水", "霜冻", "干旱",
    "营销", "广告", "文案", "销售", "推广", "直播", "带货", "电商",
    "知识库", "查资料", "检索", "文档", "农技", "农学",
    "庄稼", "作物", "农田", "田地", "土地", "土壤", "耕地",
    "水稻", "小麦", "玉米", "大豆", "棉花", "蔬菜", "水果", "果树",
    "水稻", "稻谷", "麦子", "高粱", "花生", "芝麻", "油菜",
    "番茄", "黄瓜", "辣椒", "茄子", "白菜", "萝卜", "土豆", "红薯",
    "苹果", "梨", "桃", "葡萄", "西瓜", "草莓", "樱桃", "柑橘", "橙子",
    "养殖", "畜牧", "家禽", "家畜", "养猪", "养鸡", "养鱼", "水产",
    "农机", "农具", "拖拉机", "收割机", "播种机",
    "种子", "种苗", "秧苗", "苗木", "化肥", "有机肥", "农家肥",
    "温室", "大棚", "设施农业", "滴灌", "喷灌", "地膜",
    "节气", "农时", "农事", "田间管理", "中耕", "除草", "间苗", "定苗",
)

_OUT_OF_SCOPE_KEYWORDS = (
    "动漫", "漫画", "电影", "电视剧", "小说", "游戏", "编程", "代码", "开发",
    "股票", "基金", "理财", "金融", "炒股",
)

_AMBIGUOUS_AGRI_HINTS = (
    "庄稼", "地里", "叶子", "苗", "根", "果实", "长势", "收成",
    "生虫", "发黄", "枯萎", "烂根", "死苗", "不结果",
)


def _looks_like_agriculture_input(text: str) -> bool:
    normalized = (text or "").lower()
    if any(keyword in normalized for keyword in _OUT_OF_SCOPE_KEYWORDS):
        return False
    if any(keyword in normalized for keyword in _AMBIGUOUS_AGRI_HINTS):
        return True
    return any(keyword in normalized for keyword in _AGRICULTURE_KEYWORDS)


def _build_out_of_scope_response(user_input: str) -> str:
    return (
        "# 无法启动农业智能服务\n\n"
        f"你输入的内容是：`{user_input.strip() or '(空)'}`。\n\n"
        "它看起来不属于农业领域（种植、养殖、病虫害、天气农事、农产品营销、农业知识检索等），"
        "因此我没有继续调用知识库或天气工具。\n\n"
        "如果你想咨询农业问题，可以尝试以下类型：\n\n"
        "- **种植技术**：例如 `玉米什么时候播种最好`、`水稻如何施肥`\n"
        "- **病虫害防治**：例如 `叶子发黄是什么原因`、`如何防治蚜虫`\n"
        "- **天气农事**：例如 `今天适合喷药吗`、`明天会下雨吗`\n"
        "- **农产品营销**：例如 `帮我写一段苹果的推广文案`\n"
        "- **知识检索**：例如 `查一下葡萄种植技术`"
    )


def _build_router_fallback_result(user_input: str) -> PlanExecuteState:
    if not _looks_like_agriculture_input(user_input):
        reason = "Router LLM 调用失败后, 规则兜底判断为非农业输入"
        logger.info(f"[Router] fallback 非农业输入, 直接结束: {user_input[:100]!r}")
        return {
            "selected_skill": GENERIC_SKILL_NAME,
            "skill_reason": reason,
            "plan": [],
            "response": _build_out_of_scope_response(user_input),
            "iteration": 0,
        }
    return {
        "selected_skill": GENERIC_SKILL_NAME,
        "skill_reason": "Router LLM 调用失败后, 规则兜底放行到 generic_oncall",
    }


async def skill_router_node(state: PlanExecuteState) -> PlanExecuteState:
    user_input = state.get("input", "")
    registry = get_skill_registry()
    available = registry.names()

    if not available:
        logger.warning("[Router] SkillRegistry 为空, 跳过路由")
        return {"selected_skill": "", "skill_reason": "registry empty"}

    non_generic = [n for n in available if n != GENERIC_SKILL_NAME]
    if not non_generic:
        logger.info("[Router] 仅有兜底 Skill, 直接选择 generic_oncall")
        return {
            "selected_skill": GENERIC_SKILL_NAME,
            "skill_reason": "no specific skill defined, fallback to generic",
        }

    harness = get_agent_harness()
    router_model = harness.router_model()
    llm = get_chat_llm(model=router_model, temperature=0, timeout=30, max_retries=1)
    messages = harness.build_skill_router_messages(
        menu=registry.to_router_menu(),
        user_input=user_input,
        generic=GENERIC_SKILL_NAME,
    )

    try:
        choice = await ainvoke_structured(
            llm=llm,
            schema_cls=SkillChoice,
            messages=messages,
            model_name=router_model,
        )
    except Exception as e:
        detail = f"{type(e).__name__}: {e}"
        logger.exception(f"[Router] LLM 路由失败, 使用规则兜底: {e}")
        logger.warning(f"[transition] node=skill_router reason={ROUTER_LLM_FAILED} detail={detail}")
        result = _build_router_fallback_result(user_input)
        result["transition_history"] = [make_transition("skill_router", ROUTER_LLM_FAILED, detail)]
        return result

    if not choice.is_oncall:
        reason = choice.reason or "Router 判断输入不属于农业领域范围"
        logger.info(
            f"[Router] LLM 判断非农业, 直接结束: confidence={choice.confidence}, input={user_input[:100]!r}"
        )
        logger.info(f"[transition] node=skill_router reason={ROUTER_OUT_OF_SCOPE}")
        return {
            "selected_skill": GENERIC_SKILL_NAME,
            "skill_reason": reason,
            "plan": [],
            "response": _build_out_of_scope_response(user_input),
            "iteration": 0,
            "transition_history": [make_transition("skill_router", ROUTER_OUT_OF_SCOPE, reason)],
        }

    chosen = choice.skill_name.strip().lower()
    fallback_used = False
    if chosen not in available:
        logger.warning(f"[Router] LLM 返回不存在的 skill {chosen!r}, 回退到 {GENERIC_SKILL_NAME}")
        logger.warning(f"[transition] node=skill_router reason={ROUTER_FALLBACK_GENERIC} unknown={chosen!r}")
        unknown = chosen
        chosen = GENERIC_SKILL_NAME
        fallback_used = True

    skill = registry.get(chosen)
    display = skill.display_name if skill else chosen
    logger.info(
        f"[Router] 选择 Skill: {chosen} ({display}) | confidence={choice.confidence} | reason={choice.reason}"
    )

    if fallback_used:
        transition = make_transition(
            "skill_router",
            ROUTER_FALLBACK_GENERIC,
            f"LLM 返回未知 skill={unknown!r}, 回退到 {GENERIC_SKILL_NAME}",
        )
    else:
        transition = make_transition(
            "skill_router",
            ROUTER_OK,
            f"chosen={chosen} confidence={choice.confidence}",
        )
    return {
        "selected_skill": chosen,
        "skill_reason": choice.reason,
        "transition_history": [transition],
    }
