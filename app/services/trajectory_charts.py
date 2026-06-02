"""轨迹数据分析图表生成服务.

使用 matplotlib 生成作业量指标和作业效率指标的可视化图表。
图表以 base64 编码字符串形式返回，便于前端直接显示。
"""

from __future__ import annotations

import base64
import io
from typing import Any

from loguru import logger

try:
    import matplotlib
    matplotlib.use('Agg')  # 非交互式后端
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("matplotlib 未安装，图表生成功能不可用")


def _setup_chinese_font() -> None:
    """设置中文字体支持."""
    if not HAS_MATPLOTLIB:
        return

    # 尝试使用系统中文字体
    chinese_fonts = ['SimHei', 'Microsoft YaHei', 'STSong', 'SimSun']
    for font_name in chinese_fonts:
        try:
            font_path = fm.findfont(fm.FontProperties(family=font_name))
            if font_path and 'fallback' not in font_path:
                plt.rcParams['font.sans-serif'] = [font_name]
                plt.rcParams['axes.unicode_minus'] = False
                return
        except Exception:
            continue

    # 如果没有找到中文字体，使用默认字体
    logger.warning("未找到中文字体，图表中文可能显示异常")


def _fig_to_base64(fig: plt.Figure) -> str:
    """将 matplotlib Figure 转换为 base64 字符串.

    Args:
        fig: matplotlib Figure 对象

    Returns:
        base64 编码的 PNG 图片字符串
    """
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_base64


def generate_work_volume_chart(work_volume: dict[str, Any]) -> str:
    """生成作业量指标图表.

    Args:
        work_volume: 作业量指标数据，包含:
            - work_duration_hours: 作业总时长（小时）
            - work_distance_km: 作业总行程（公里）
            - work_area_mu: 作业面积（亩）
            - avg_field_speed_kmh: 田间平均作业速度（km/h）

    Returns:
        base64 编码的图表图片
    """
    if not HAS_MATPLOTLIB:
        return ""

    _setup_chinese_font()

    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    fig.suptitle('作业量指标分析', fontsize=16, fontweight='bold')

    # 指标数据
    metrics = [
        {
            'title': '作业总时长',
            'value': work_volume.get('work_duration_hours', 0),
            'unit': '小时',
            'color': '#2196F3',
        },
        {
            'title': '作业总行程',
            'value': work_volume.get('work_distance_km', 0),
            'unit': '公里',
            'color': '#4CAF50',
        },
        {
            'title': '作业面积',
            'value': work_volume.get('work_area_mu', 0),
            'unit': '亩',
            'color': '#FF9800',
        },
        {
            'title': '田间平均速度',
            'value': work_volume.get('avg_field_speed_kmh', 0),
            'unit': 'km/h',
            'color': '#9C27B0',
        },
    ]

    for idx, (ax, metric) in enumerate(zip(axes.flat, metrics)):
        # 创建仪表盘样式的图表
        value = metric['value']
        color = metric['color']

        # 绘制半圆仪表盘
        theta = [i * 0.01 for i in range(0, 201)]
        r = [1.0] * len(theta)
        ax.plot(theta, r, color='#E0E0E0', linewidth=8, solid_capstyle='round')

        # 根据值计算角度（最大值设为数据的1.5倍或固定值）
        max_val = max(value * 1.5, 1.0)
        angle = min(value / max_val, 1.0) * 3.14
        theta_fill = [i * 0.01 for i in range(0, int(angle * 100) + 1)]
        r_fill = [1.0] * len(theta_fill)
        ax.plot(theta_fill, r_fill, color=color, linewidth=8, solid_capstyle='round')

        # 添加中心文字
        ax.text(0.5, 0.45, f'{value:.1f}', ha='center', va='center',
                fontsize=24, fontweight='bold', color=color,
                transform=ax.transAxes)
        ax.text(0.5, 0.15, metric['unit'], ha='center', va='center',
                fontsize=12, color='#666666', transform=ax.transAxes)
        ax.text(0.5, 0.85, metric['title'], ha='center', va='center',
                fontsize=14, fontweight='bold', color='#333333',
                transform=ax.transAxes)

        ax.set_xlim(-0.1, 3.24)
        ax.set_ylim(-0.2, 1.3)
        ax.set_aspect('equal')
        ax.axis('off')

    plt.tight_layout()
    return _fig_to_base64(fig)


def generate_work_efficiency_chart(efficiency: dict[str, Any]) -> str:
    """生成作业效率指标图表.

    Args:
        efficiency: 作业效率指标数据，包含:
            - compliance_rate: 综合作业达标率（%）
            - depth_compliance: 深度达标率（%）
            - speed_compliance: 速度达标率（%）
            - productivity_mu_per_hour: 生产率（亩/小时）
            - time_utilization_rate: 时间利用率（%）

    Returns:
        base64 编码的图表图片
    """
    if not HAS_MATPLOTLIB:
        return ""

    _setup_chinese_font()

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    fig.suptitle('作业效率指标分析', fontsize=16, fontweight='bold')

    # 1. 达标率饼图
    ax1 = axes[0]
    compliance_rate = efficiency.get('compliance_rate', 0)
    labels = ['达标', '未达标']
    sizes = [compliance_rate, 100 - compliance_rate]
    colors = ['#4CAF50', '#FF5252']
    explode = (0.05, 0)

    wedges, texts, autotexts = ax1.pie(
        sizes, explode=explode, labels=labels, colors=colors,
        autopct='%1.1f%%', shadow=True, startangle=90,
        textprops={'fontsize': 11}
    )
    ax1.set_title(f'综合作业达标率\n{compliance_rate:.1f}%', fontsize=12, fontweight='bold')

    # 2. 生产率柱状图
    ax2 = axes[1]
    productivity = efficiency.get('productivity_mu_per_hour', 0)
    bars = ax2.bar(['生产率'], [productivity], color='#2196F3', width=0.5)
    ax2.set_ylabel('亩/小时', fontsize=11)
    ax2.set_title('生产率', fontsize=12, fontweight='bold')
    ax2.set_ylim(0, max(productivity * 1.3, 1.0))

    # 在柱子上方添加数值
    for bar, val in zip(bars, [productivity]):
        ax2.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 0.05,
                f'{val:.1f}', ha='center', va='bottom', fontweight='bold')

    # 3. 时间利用率环形图
    ax3 = axes[2]
    time_util = efficiency.get('time_utilization_rate', 0)
    sizes3 = [time_util, 100 - time_util]
    colors3 = ['#FF9800', '#E0E0E0']

    wedges3, texts3 = ax3.pie(
        sizes3, colors=colors3, startangle=90,
        wedgeprops=dict(width=0.4, edgecolor='white'),
        textprops={'fontsize': 11}
    )

    # 中心添加百分比
    ax3.text(0, 0, f'{time_util:.1f}%', ha='center', va='center',
             fontsize=20, fontweight='bold', color='#FF9800')
    ax3.set_title('时间利用率', fontsize=12, fontweight='bold')

    plt.tight_layout()
    return _fig_to_base64(fig)


def generate_combined_analysis_chart(
    work_volume: dict[str, Any],
    work_efficiency: dict[str, Any],
) -> tuple[str, str]:
    """生成综合分析图表.

    Args:
        work_volume: 作业量指标
        work_efficiency: 作业效率指标

    Returns:
        (作业量图表base64, 作业效率图表base64)
    """
    volume_chart = generate_work_volume_chart(work_volume)
    efficiency_chart = generate_work_efficiency_chart(work_efficiency)
    return volume_chart, efficiency_chart
