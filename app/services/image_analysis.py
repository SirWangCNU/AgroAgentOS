"""基于 YOLO ONNX 模型的病虫害图像识别服务.

使用 onnxruntime 进行推理, 纯 numpy 实现 YOLO 后处理 (解码 + NMS).
模型文件为 ONNX 格式, 放置在 models/ 目录下.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger
from PIL import Image

try:
    import onnxruntime as ort
except ImportError:
    ort = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class DetectionResult:
    """单个检测结果."""

    label: str
    chinese_name: str
    confidence: float
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2


# ---------------------------------------------------------------------------
# 病虫害标签映射 (label_index -> (英文名, 中文名, 简要描述))
# 支持常见农业病虫害类别, 可根据实际模型标签文件扩展.
# ---------------------------------------------------------------------------
LABEL_MAP: dict[int, tuple[str, str, str]] = {
    0: ("healthy", "健康", "叶片正常, 无病虫害症状"),
    1: ("powdery_mildew", "白粉病", "叶面出现白色粉状霉层, 影响光合作用"),
    2: ("rust", "锈病", "叶片出现锈色或橙色孢子堆"),
    3: ("leaf_spot", "叶斑病", "叶片出现褐色或黑色圆形/不规则病斑"),
    4: ("blight", "疫病", "叶片或茎部出现水渍状病斑, 迅速扩展"),
    5: ("anthracnose", "炭疽病", "叶片或果实出现黑色凹陷病斑"),
    6: ("gray_mold", "灰霉病", "灰色霉层覆盖, 组织软腐"),
    7: ("downy_mildew", "霜霉病", "叶背出现灰紫色霉层, 叶面黄化"),
    8: ("fusarium_wilt", "枯萎病", "植株萎蔫, 维管束变褐"),
    9: ("bacterial_spot", "细菌性斑点病", "叶片出现水渍状小斑点, 有黄色晕圈"),
    10: ("aphids", "蚜虫", "群集嫩梢和叶背, 分泌蜜露"),
    11: ("whitefly", "白粉虱", "叶背白色小飞虫, 叶片黄化"),
    12: ("spider_mites", "红蜘蛛", "叶背红色小点, 叶片失绿变灰"),
    13: ("thrips", "蓟马", "叶片银灰色斑点, 畸形卷曲"),
    14: ("caterpillar", "菜青虫", "叶片孔洞, 可见虫粪"),
    15: ("leafhopper", "叶蝉", "叶片边缘黄化, 有跳跃小虫"),
}

# 未知标签兜底
_UNKNOWN_LABEL = ("unknown", "未知病害", "无法识别, 建议咨询农技专家")


# ---------------------------------------------------------------------------
# YOLO 后处理 (纯 numpy)
# ---------------------------------------------------------------------------


def _xywh_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    """将 [cx, cy, w, h] 转换为 [x1, y1, x2, y2]."""
    xyxy = np.empty_like(boxes)
    xyxy[:, 0] = boxes[:, 0] - boxes[:, 2] / 2  # x1
    xyxy[:, 1] = boxes[:, 1] - boxes[:, 3] / 2  # y1
    xyxy[:, 2] = boxes[:, 0] + boxes[:, 2] / 2  # x2
    xyxy[:, 3] = boxes[:, 1] + boxes[:, 3] / 2  # y2
    return xyxy


def _compute_iou(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    """计算一个 box 与一组 boxes 的 IoU."""
    x1 = np.maximum(box[0], boxes[:, 0])
    y1 = np.maximum(box[1], boxes[:, 1])
    x2 = np.minimum(box[2], boxes[:, 2])
    y2 = np.minimum(box[3], boxes[:, 3])

    inter = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
    area_a = (box[2] - box[0]) * (box[3] - box[1])
    area_b = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])

    return inter / (area_a + area_b - inter + 1e-6)


def nms(
    boxes: np.ndarray,
    scores: np.ndarray,
    iou_threshold: float = 0.45,
) -> np.ndarray:
    """非极大值抑制, 返回保留的索引."""
    order = scores.argsort()[::-1]
    keep: list[int] = []

    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        if order.size == 1:
            break
        ious = _compute_iou(boxes[i], boxes[order[1:]])
        remain = np.where(ious <= iou_threshold)[0]
        order = order[remain + 1]

    return np.array(keep, dtype=np.int64)


def postprocess_yolo(
    output: np.ndarray,
    input_size: int,
    orig_w: int,
    orig_h: int,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    num_classes: int = 15,
) -> list[tuple[int, float, tuple[float, float, float, float]]]:
    """解析 YOLOv8 输出并执行 NMS.

    Args:
        output: 模型原始输出, shape [1, num_detections, 5+num_classes]
        input_size: 模型输入尺寸 (如 640)
        orig_w/orig_h: 原始图片宽高
        conf_threshold: 置信度阈值
        iou_threshold: NMS IoU 阈值
        num_classes: 类别数

    Returns:
        [(class_id, confidence, (x1,y1,x2,y2)), ...] 坐标已映射回原图尺寸
    """
    # output shape: [1, N, 5+num_classes]
    preds = output[0]  # [N, 5+num_classes]

    # 提取 box (cx, cy, w, h) 和 scores
    boxes_xywh = preds[:, :4]  # [N, 4]
    objectness = preds[:, 4]  # [N]
    class_scores = preds[:, 5:]  # [N, num_classes]

    # 最终置信度 = objectness * class_prob
    class_ids = np.argmax(class_scores, axis=1)  # [N]
    class_max_scores = class_scores[np.arange(len(class_scores)), class_ids]  # [N]
    confidences = objectness * class_max_scores  # [N]

    # 过滤低置信度
    mask = confidences >= conf_threshold
    boxes_xywh = boxes_xywh[mask]
    confidences = confidences[mask]
    class_ids = class_ids[mask]

    if len(confidences) == 0:
        return []

    # xywh -> xyxy
    boxes_xyxy = _xywh_to_xyxy(boxes_xywh)

    # 坐标缩放到原图尺寸
    scale_x = orig_w / input_size
    scale_y = orig_h / input_size
    boxes_xyxy[:, [0, 2]] *= scale_x
    boxes_xyxy[:, [1, 3]] *= scale_y

    # 按类别分组做 NMS
    results: list[tuple[int, float, tuple[float, float, float, float]]] = []
    unique_classes = np.unique(class_ids)

    for cls_id in unique_classes:
        cls_mask = class_ids == cls_id
        cls_boxes = boxes_xyxy[cls_mask]
        cls_scores = confidences[cls_mask]
        cls_indices = nms(cls_boxes, cls_scores, iou_threshold)

        for idx in cls_indices:
            box = tuple(cls_boxes[idx].tolist())
            results.append((int(cls_id), float(cls_scores[idx]), box))  # type: ignore[arg-type]

    return results


# ---------------------------------------------------------------------------
# 图像预处理
# ---------------------------------------------------------------------------


def preprocess_image(
    image_bytes: bytes, input_size: int = 640
) -> tuple[np.ndarray, int, int]:
    """将图片字节预处理为模型输入 tensor.

    Returns:
        (tensor, orig_width, orig_height) - tensor shape [1, 3, H, W] float32
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    orig_w, orig_h = img.size

    # Resize (保持比例用 letterbox, 这里简单 resize)
    img_resized = img.resize((input_size, input_size), Image.BILINEAR)

    # To numpy, normalize to [0, 1], transpose to CHW
    arr = np.array(img_resized, dtype=np.float32) / 255.0
    arr = arr.transpose(2, 0, 1)  # HWC -> CHW

    # Add batch dimension
    tensor = np.expand_dims(arr, axis=0)  # [1, 3, H, W]
    return tensor, orig_w, orig_h


# ---------------------------------------------------------------------------
# 服务主类
# ---------------------------------------------------------------------------


class ImageAnalysisService:
    """基于 YOLO ONNX 的病虫害图像识别服务 (进程单例)."""

    _instance: Optional["ImageAnalysisService"] = None

    def __init__(
        self,
        model_path: str = "models/pest_yolo.onnx",
        confidence_threshold: float = 0.25,
        nms_threshold: float = 0.45,
        input_size: int = 640,
        num_classes: int = 15,
    ) -> None:
        if ort is None:
            raise RuntimeError(
                "onnxruntime 未安装. 请执行: pip install onnxruntime"
            )

        self._model_path = Path(model_path)
        self._conf_threshold = confidence_threshold
        self._nms_threshold = nms_threshold
        self._input_size = input_size
        self._num_classes = num_classes
        self._session: Optional[ort.InferenceSession] = None

    def _ensure_model_loaded(self) -> ort.InferenceSession:
        """延迟加载模型 (首次调用时加载)."""
        if self._session is not None:
            return self._session

        if not self._model_path.exists():
            raise FileNotFoundError(
                f"YOLO 模型文件不存在: {self._model_path}. "
                f"请先执行: python scripts/download_pest_model.py"
            )

        logger.info(f"[image] 加载 ONNX 模型: {self._model_path}")
        self._session = ort.InferenceSession(
            str(self._model_path),
            providers=["CPUExecutionProvider"],
        )
        logger.info(
            f"[image] 模型加载完成, input: {self._session.get_inputs()[0].name}, "
            f"shape: {self._session.get_inputs()[0].shape}"
        )
        return self._session

    def analyze(self, image_bytes: bytes) -> list[DetectionResult]:
        """分析图片, 返回检测结果列表.

        Args:
            image_bytes: 图片文件的原始字节

        Returns:
            DetectionResult 列表, 按置信度降序排列
        """
        session = self._ensure_model_loaded()

        # 预处理
        tensor, orig_w, orig_h = preprocess_image(image_bytes, self._input_size)
        logger.debug(f"[image] 预处理完成: orig={orig_w}x{orig_h}, tensor={tensor.shape}")

        # 推理
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: tensor})
        raw_output = outputs[0]  # [1, N, 5+num_classes]
        logger.debug(f"[image] 推理完成: output shape={raw_output.shape}")

        # 后处理
        detections_raw = postprocess_yolo(
            raw_output,
            input_size=self._input_size,
            orig_w=orig_w,
            orig_h=orig_h,
            conf_threshold=self._conf_threshold,
            iou_threshold=self._nms_threshold,
            num_classes=self._num_classes,
        )

        # 映射标签
        results: list[DetectionResult] = []
        for class_id, confidence, bbox in detections_raw:
            label_info = LABEL_MAP.get(class_id, _UNKNOWN_LABEL)
            results.append(
                DetectionResult(
                    label=label_info[0],
                    chinese_name=label_info[1],
                    confidence=round(confidence, 4),
                    bbox=bbox,
                )
            )

        # 按置信度降序
        results.sort(key=lambda r: r.confidence, reverse=True)
        logger.info(f"[image] 检测完成: {len(results)} 个目标")
        return results

    def get_label_map(self) -> dict[int, tuple[str, str, str]]:
        """返回标签映射表 (供外部查询)."""
        return LABEL_MAP.copy()

    @classmethod
    def get_instance(cls) -> "ImageAnalysisService":
        """获取进程单例."""
        if cls._instance is None:
            from app.config import settings

            cls._instance = cls(
                model_path=settings.yolo_model_path,
                confidence_threshold=settings.yolo_confidence_threshold,
                nms_threshold=settings.yolo_nms_threshold,
                input_size=settings.yolo_input_size,
            )
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例 (用于测试)."""
        cls._instance = None
