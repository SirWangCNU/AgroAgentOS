"""Farm Agent 工具调用期间可信身份上下文的生命周期管理。"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator, Literal

from app.exceptions import AppException


@dataclass(frozen=True, slots=True)
class FarmRunContext:
    """由受信任的运行入口绑定、供工具和服务只读使用的身份上下文。"""

    user_id: int
    farm_id: int
    run_id: str
    run_type: Literal["inspection", "task_verification"]
    task_id: str | None = None
    demo_scenario: str | None = None


_farm_run_context: ContextVar[FarmRunContext | None] = ContextVar(
    "farm_run_context",
    default=None,
)


def get_farm_run_context() -> FarmRunContext | None:
    """返回当前执行上下文，未绑定时返回 ``None``。"""

    return _farm_run_context.get()


def require_farm_run_context() -> FarmRunContext:
    """返回当前执行上下文，未绑定时拒绝继续执行。"""

    context = get_farm_run_context()
    if context is None:
        raise AppException(
            status_code=500,
            code="FARM_RUN_CONTEXT_MISSING",
            message="Farm Agent 运行上下文缺失",
        )
    return context


@contextmanager
def bind_farm_run_context(context: FarmRunContext) -> Iterator[FarmRunContext]:
    """在当前执行流中临时绑定上下文，并在退出时可靠恢复。"""

    token = _farm_run_context.set(context)
    try:
        yield context
    finally:
        _farm_run_context.reset(token)
