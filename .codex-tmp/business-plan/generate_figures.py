from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math


OUT = Path(r"E:\GithubProgram\AgroAgentOS\.codex-tmp\business-plan\figures")
OUT.mkdir(parents=True, exist_ok=True)
FONT = r"C:\Windows\Fonts\msyh.ttc"


def font(size, bold=False):
    return ImageFont.truetype(FONT, size=size, index=1 if bold else 0)


NAVY = "#0B3558"
BLUE = "#1677A6"
TEAL = "#16857A"
GREEN = "#2D8A5E"
LIGHT = "#EEF6F4"
PALE = "#F5F8FA"
GRAY = "#5E6D78"
GRID = "#D9E3E8"
ORANGE = "#D98C2B"


def rounded(draw, box, fill, outline=None, radius=24, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def centered(draw, box, text, fnt, fill=NAVY, spacing=6):
    x1, y1, x2, y2 = box
    bbox = draw.multiline_textbbox((0, 0), text, font=fnt, align="center", spacing=spacing)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.multiline_text(((x1 + x2 - w) / 2, (y1 + y2 - h) / 2), text, font=fnt, fill=fill, align="center", spacing=spacing)


def arrow(draw, start, end, fill=TEAL, width=8, head=18):
    draw.line([start, end], fill=fill, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    p1 = (end[0] - head * math.cos(angle - math.pi / 6), end[1] - head * math.sin(angle - math.pi / 6))
    p2 = (end[0] - head * math.cos(angle + math.pi / 6), end[1] - head * math.sin(angle + math.pi / 6))
    draw.polygon([end, p1, p2], fill=fill)


def save(img, name):
    img.save(OUT / name, optimize=True)


# Architecture
img = Image.new("RGB", (1800, 1100), "white")
d = ImageDraw.Draw(img)
d.text((80, 55), "AgroAgentOS 多智能体智慧农服技术架构", font=font(50, True), fill=NAVY)
d.text((82, 123), "从农业经营场景出发，以可追溯知识与受控工具完成任务协同", font=font(28), fill=GRAY)

layers = [
    ("用户与场景层", ["农场 / 合作社", "农技服务机构", "农业企业"]),
    ("应用服务层", ["农业问答", "农场档案", "天气农事", "病虫害", "市场行情", "内容营销"]),
    ("多智能体协同层", ["SkillRouter\n技能路由", "Planner\n任务规划", "Executor\n工具执行", "Replanner\n结果复核"]),
    ("知识与工具层", ["混合RAG\n关键词＋向量", "农业Skill\n工具白名单", "天气 / 市场\n受限联网", "机构知识库\n来源保留"]),
    ("数据与治理层", ["农场 / 地块 / 会话", "身份认证与权限", "执行记录与降级", "SQLite / MySQL\nRedis / Milvus"]),
]
ys = [190, 340, 500, 675, 855]
colors = ["#E8F2F8", "#E7F4EF", "#EAF0F8", "#EEF6F4", "#F3F5F7"]
for idx, ((label, items), y) in enumerate(zip(layers, ys)):
    rounded(d, (70, y, 310, y + 112), NAVY if idx == 2 else "#DCE9EF", radius=18)
    centered(d, (70, y, 310, y + 112), label, font(27, True), "white" if idx == 2 else NAVY)
    gap = 22
    x0, x1 = 350, 1730
    box_w = (x1 - x0 - gap * (len(items) - 1)) / len(items)
    for j, item in enumerate(items):
        bx1 = int(x0 + j * (box_w + gap))
        bx2 = int(bx1 + box_w)
        rounded(d, (bx1, y, bx2, y + 112), colors[idx], outline="#B8CDD8", radius=18, width=2)
        centered(d, (bx1 + 8, y + 4, bx2 - 8, y + 108), item, font(25, idx == 2), NAVY)
    if idx < len(layers) - 1:
        arrow(d, (900, y + 118), (900, ys[idx + 1] - 10), fill="#7AA7B8", width=6, head=16)
save(img, "architecture.png")


# Business loop
img = Image.new("RGB", (1800, 900), "white")
d = ImageDraw.Draw(img)
d.text((80, 55), "农业智能服务闭环", font=font(50, True), fill=NAVY)
d.text((82, 123), "将一次问答沉淀为可持续改进的农场知识与服务资产", font=font(28), fill=GRAY)
centers = [(300, 350), (760, 260), (1300, 350), (1180, 650), (520, 650)]
labels = [
    ("农场数字档案", "地块・作物・位置・会话"),
    ("智能任务协同", "路由・规划・工具・复核"),
    ("农技与经营建议", "天气・植保・市场・营销"),
    ("人工执行与反馈", "采纳・修订・现场核验"),
    ("知识持续沉淀", "专属资料・典型问题・版本"),
]
for i in range(len(centers)):
    arrow(d, centers[i], centers[(i + 1) % len(centers)], fill="#79AFA2", width=10, head=24)
for i, ((cx, cy), (title, sub)) in enumerate(zip(centers, labels)):
    fill = ["#E8F2F8", "#E7F4EF", "#EAF0F8", "#FFF4E5", "#EEF6F4"][i]
    rounded(d, (cx - 190, cy - 78, cx + 190, cy + 78), fill, outline="#8EB5B4", radius=30, width=3)
    centered(d, (cx - 180, cy - 66, cx + 180, cy - 4), title, font(30, True), NAVY)
    centered(d, (cx - 180, cy + 3, cx + 180, cy + 62), sub, font(23), GRAY)
rounded(d, (705, 420, 1095, 545), NAVY, radius=30)
centered(d, (715, 430, 1085, 535), "AgroAgentOS\n人机协同与安全边界", font(30, True), "white")
save(img, "business_loop.png")


# Market funnel
img = Image.new("RGB", (1800, 1000), "white")
d = ImageDraw.Draw(img)
d.text((80, 55), "目标市场分层与三年切入路径", font=font(50, True), fill=NAVY)
d.text((82, 123), "由组织客户付费，再通过服务网络辐射小农户", font=font(28), fill=GRAY)
funnel = [
    (170, 280, 1630, 440, "潜在主体市场 TAM", "约615.5万个家庭农场、合作社与联合社", "#DDECF3"),
    (310, 465, 1490, 625, "初期可服务市场 SAM", "按潜在主体1%规划，约6.2万个组织客户", "#CDE7DF"),
    (510, 650, 1290, 810, "三年可获得市场 SOM", "200家SaaS客户＋15个私有化项目", "#A9D0C2"),
]
for x1, y1, x2, y2, title, sub, fill in funnel:
    notch = 55
    d.polygon([(x1, y1), (x2, y1), (x2 - notch, y2), (x1 + notch, y2)], fill=fill, outline="#6D9EA3")
    centered(d, (x1 + 40, y1 + 15, x2 - 40, y1 + 85), title, font(35, True), NAVY)
    centered(d, (x1 + 55, y1 + 82, x2 - 55, y2 - 12), sub, font(27), GRAY)
rounded(d, (430, 855, 1370, 940), "#FFF4E5", outline="#D6A35A", radius=20)
centered(d, (445, 862, 1355, 932), "三年收入目标590万元：属于经营预测，不代表已实现收入", font(28, True), "#855217")
save(img, "market_funnel.png")


# Financial chart
img = Image.new("RGB", (1800, 1050), "white")
d = ImageDraw.Draw(img)
d.text((80, 55), "三年财务预测", font=font(50, True), fill=NAVY)
d.text((82, 123), "单位：万元｜预测口径，非已实现经营业绩", font=font(28), fill=GRAY)
left, top, right, bottom = 180, 220, 1680, 860
d.line((left, top, left, bottom), fill=NAVY, width=4)
d.line((left, bottom, right, bottom), fill=NAVY, width=4)
for value in range(0, 701, 100):
    y = bottom - value / 700 * (bottom - top)
    d.line((left, y, right, y), fill=GRID, width=2)
    d.text((85, y - 15), str(value), font=font(23), fill=GRAY)
years = ["第一年", "第二年", "第三年"]
revenue = [60, 220, 590]
cost = [75, 190, 428]
profit = [-15, 30, 162]
group_x = [440, 920, 1400]
bar_w = 95
for i, x in enumerate(group_x):
    for j, (val, color, label) in enumerate([(revenue[i], BLUE, "收入"), (cost[i], TEAL, "总成本")]):
        x1 = x - 115 + j * 150
        y = bottom - val / 700 * (bottom - top)
        d.rounded_rectangle((x1, y, x1 + bar_w, bottom), radius=12, fill=color)
        d.text((x1 + 8, y - 38), str(val), font=font(25, True), fill=color)
    py = bottom - max(profit[i], 0) / 700 * (bottom - top)
    d.ellipse((x + 142, py - 13, x + 168, py + 13), fill=ORANGE)
    d.text((x + 178, py - 20), f"结余 {profit[i]}", font=font(24, True), fill="#9B5E14")
    d.text((x - 70, bottom + 28), years[i], font=font(28, True), fill=NAVY)
rounded(d, (600, 915, 1200, 995), PALE, outline=GRID, radius=18)
d.rectangle((640, 941, 672, 969), fill=BLUE); d.text((690, 937), "营业收入", font=font(24), fill=NAVY)
d.rectangle((830, 941, 862, 969), fill=TEAL); d.text((880, 937), "总成本", font=font(24), fill=NAVY)
d.ellipse((1010, 942, 1038, 970), fill=ORANGE); d.text((1053, 937), "经营结余", font=font(24), fill=NAVY)
save(img, "financial_chart.png")


# Roadmap
img = Image.new("RGB", (1800, 900), "white")
d = ImageDraw.Draw(img)
d.text((80, 55), "AgroAgentOS 三年演进路线", font=font(50, True), fill=NAVY)
d.text((82, 123), "验证价值 → 标准复制 → 伙伴规模化", font=font(28), fill=GRAY)
cols = [
    ("第一年｜验证", "产品", "机构版、评测、安全与移动适配", "市场", "3个试点、20家SaaS客户", "知识", "3个重点作物知识包", "#E8F2F8"),
    ("第二年｜复制", "产品", "农事记录、预警与客户运营", "市场", "80家SaaS、8个私有化项目", "知识", "6个作物及区域版本", "#E7F4EF"),
    ("第三年｜规模化", "产品", "开放平台与伙伴工具", "市场", "200家SaaS、15个私有化项目", "知识", "持续更新的知识伙伴体系", "#FFF4E5"),
]
xs = [90, 620, 1150]
for i, (title, a, av, b, bv, c, cv, fill) in enumerate(cols):
    x = xs[i]
    rounded(d, (x, 235, x + 470, 790), fill, outline="#9BB9C2", radius=28, width=3)
    rounded(d, (x + 25, 265, x + 445, 355), NAVY if i == 0 else TEAL if i == 1 else ORANGE, radius=22)
    centered(d, (x + 35, 270, x + 435, 350), title, font(32, True), "white")
    rows = [(a, av), (b, bv), (c, cv)]
    y = 405
    for label, value in rows:
        d.text((x + 45, y), label, font=font(26, True), fill=NAVY)
        d.multiline_text((x + 45, y + 45), value, font=font(24), fill=GRAY, spacing=7)
        y += 120
    if i < 2:
        arrow(d, (x + 475, 515), (xs[i + 1] - 15, 515), fill="#6FA59B", width=10, head=22)
save(img, "roadmap.png")

print("GENERATED", len(list(OUT.glob("*.png"))))
