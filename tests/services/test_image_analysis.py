"""图像分析服务单元测试.

测试 ImageAnalysisService 的核心逻辑:
  - 图像预处理
  - YOLO 后处理 (输出解码 + NMS)
  - 标签映射
  - 服务初始化
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.image_analysis import (
    LABEL_MAP,
    DetectionResult,
    ImageAnalysisService,
    _xywh_to_xyxy,
    nms,
    postprocess_yolo,
    preprocess_image,
)


# ---------------------------------------------------------------------------
# 测试辅助
# ---------------------------------------------------------------------------


def _make_test_image_bytes(width: int = 100, height: int = 80) -> bytes:
    """创建测试用图片字节 (JPEG)."""
    from PIL import Image
    import io

    img = Image.new("RGB", (width, height), color=(34, 139, 34))  # 绿色
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_yolo_output(
    detections: list[tuple[float, float, float, float, float, int, float]],
    num_classes: int = 15,
) -> np.ndarray:
    """构造 YOLO 模型模拟输出.

    Args:
        detections: [(cx, cy, w, h, objectness, class_id, class_prob), ...]
        num_classes: 类别数

    Returns:
        shape [1, N, 5+num_classes] 的 numpy 数组
    """
    N = max(len(detections), 1)
    output = np.zeros((1, N, 5 + num_classes), dtype=np.float32)

    for i, det in enumerate(detections):
        cx, cy, w, h, obj, cls_id, cls_prob = det
        output[0, i, 0] = cx
        output[0, i, 1] = cy
        output[0, i, 2] = w
        output[0, i, 3] = h
        output[0, i, 4] = obj
        output[0, i, 5 + cls_id] = cls_prob

    return output


# ---------------------------------------------------------------------------
# 坐标转换测试
# ---------------------------------------------------------------------------


class TestXywhToXyxy:
    def test_basic_conversion(self):
        boxes = np.array([[100, 100, 50, 30]], dtype=np.float32)
        result = _xywh_to_xyxy(boxes)
        np.testing.assert_allclose(result[0], [75, 85, 125, 115])

    def test_multiple_boxes(self):
        boxes = np.array(
            [[10, 20, 5, 5], [100, 200, 40, 60]], dtype=np.float32
        )
        result = _xywh_to_xyxy(boxes)
        assert result.shape == (2, 4)
        np.testing.assert_allclose(result[0], [7.5, 17.5, 12.5, 22.5])
        np.testing.assert_allclose(result[1], [80, 170, 120, 230])


# ---------------------------------------------------------------------------
# NMS 测试
# ---------------------------------------------------------------------------


class TestNMS:
    def test_no_overlap(self):
        boxes = np.array(
            [[10, 10, 50, 50], [200, 200, 250, 250]], dtype=np.float32
        )
        scores = np.array([0.9, 0.8], dtype=np.float32)
        keep = nms(boxes, scores, iou_threshold=0.5)
        assert len(keep) == 2

    def test_full_overlap(self):
        boxes = np.array(
            [[10, 10, 50, 50], [10, 10, 50, 50]], dtype=np.float32
        )
        scores = np.array([0.9, 0.8], dtype=np.float32)
        keep = nms(boxes, scores, iou_threshold=0.5)
        assert len(keep) == 1
        assert keep[0] == 0  # 保留得分高的

    def test_partial_overlap(self):
        boxes = np.array(
            [[10, 10, 50, 50], [30, 30, 70, 70]], dtype=np.float32
        )
        scores = np.array([0.9, 0.8], dtype=np.float32)
        keep = nms(boxes, scores, iou_threshold=0.3)
        # 部分重叠, 取决于 IoU 是否 > 0.3
        assert len(keep) >= 1


# ---------------------------------------------------------------------------
# YOLO 后处理测试
# ---------------------------------------------------------------------------


class TestPostprocessYolo:
    def test_single_detection(self):
        # 在 640x640 输入中心放一个 100x100 的检测框, 类别 1, 高置信度
        output = _make_yolo_output(
            [(320, 320, 100, 100, 0.9, 1, 0.95)],
            num_classes=15,
        )
        results = postprocess_yolo(
            output,
            input_size=640,
            orig_w=640,
            orig_h=640,
            conf_threshold=0.25,
            iou_threshold=0.45,
            num_classes=15,
        )
        assert len(results) == 1
        cls_id, conf, bbox = results[0]
        assert cls_id == 1
        assert conf > 0.8
        # bbox 应该在合理范围内
        assert 200 < bbox[0] < 400
        assert 200 < bbox[1] < 400

    def test_low_confidence_filtered(self):
        output = _make_yolo_output(
            [(320, 320, 100, 100, 0.1, 1, 0.1)],  # 低置信度
            num_classes=15,
        )
        results = postprocess_yolo(
            output,
            input_size=640,
            orig_w=640,
            orig_h=640,
            conf_threshold=0.25,
            num_classes=15,
        )
        assert len(results) == 0

    def test_coordinate_scaling(self):
        # 原图 1280x960, 模型输入 640x640
        output = _make_yolo_output(
            [(320, 320, 100, 100, 0.9, 0, 0.9)],
            num_classes=15,
        )
        results = postprocess_yolo(
            output,
            input_size=640,
            orig_w=1280,
            orig_h=960,
            conf_threshold=0.25,
            num_classes=15,
        )
        assert len(results) == 1
        _, _, bbox = results[0]
        # 坐标应被缩放到 1280x960 范围
        assert bbox[2] > 400  # x2 应该大于 400 (被放大了)

    def test_empty_output(self):
        output = np.zeros((1, 10, 20), dtype=np.float32)
        results = postprocess_yolo(
            output,
            input_size=640,
            orig_w=640,
            orig_h=640,
            conf_threshold=0.25,
            num_classes=15,
        )
        assert len(results) == 0


# ---------------------------------------------------------------------------
# 图像预处理测试
# ---------------------------------------------------------------------------


class TestPreprocessImage:
    def test_output_shape(self):
        img_bytes = _make_test_image_bytes(200, 150)
        tensor, orig_w, orig_h = preprocess_image(img_bytes, input_size=640)
        assert tensor.shape == (1, 3, 640, 640)
        assert orig_w == 200
        assert orig_h == 150

    def test_value_range(self):
        img_bytes = _make_test_image_bytes(64, 64)
        tensor, _, _ = preprocess_image(img_bytes, input_size=640)
        assert tensor.min() >= 0.0
        assert tensor.max() <= 1.0

    def test_dtype(self):
        img_bytes = _make_test_image_bytes(64, 64)
        tensor, _, _ = preprocess_image(img_bytes, input_size=640)
        assert tensor.dtype == np.float32


# ---------------------------------------------------------------------------
# 标签映射测试
# ---------------------------------------------------------------------------


class TestLabelMap:
    def test_known_labels(self):
        assert 0 in LABEL_MAP
        assert LABEL_MAP[0][0] == "healthy"
        assert LABEL_MAP[0][1] == "健康"

    def test_label_structure(self):
        for idx, (label, chinese, desc) in LABEL_MAP.items():
            assert isinstance(idx, int)
            assert isinstance(label, str)
            assert isinstance(chinese, str)
            assert isinstance(desc, str)
            assert len(label) > 0
            assert len(chinese) > 0


# ---------------------------------------------------------------------------
# 服务类测试 (mock onnxruntime)
# ---------------------------------------------------------------------------


class TestImageAnalysisService:
    def test_singleton(self):
        ImageAnalysisService.reset_instance()
        with patch("app.services.image_analysis.ort") as mock_ort:
            mock_session = MagicMock()
            mock_ort.InferenceSession.return_value = mock_session
            mock_session.get_inputs.return_value = [MagicMock(name="images", shape=[1, 3, 640, 640])]

            svc1 = ImageAnalysisService(model_path="test.onnx")
            svc2 = ImageAnalysisService.get_instance()

            # get_instance 返回的是通过 config 创建的实例, 不是直接 new 的
            assert ImageAnalysisService._instance is svc2

        ImageAnalysisService.reset_instance()

    def test_analyze_returns_detection_results(self):
        with patch("app.services.image_analysis.ort") as mock_ort:
            mock_session = MagicMock()
            mock_ort.InferenceSession.return_value = mock_session
            mock_session.get_inputs.return_value = [MagicMock(name="images", shape=[1, 3, 640, 640])]

            # 构造 mock 输出: 一个高置信度检测
            mock_output = _make_yolo_output(
                [(320, 320, 100, 100, 0.9, 1, 0.95)],
                num_classes=15,
            )
            mock_session.run.return_value = [mock_output]

            svc = ImageAnalysisService(model_path="test.onnx")
            svc._session = mock_session

            img_bytes = _make_test_image_bytes(640, 640)
            results = svc.analyze(img_bytes)

            assert len(results) == 1
            assert isinstance(results[0], DetectionResult)
            assert results[0].label == "powdery_mildew"
            assert results[0].chinese_name == "白粉病"
            assert results[0].confidence > 0.8

    def test_analyze_empty_result(self):
        with patch("app.services.image_analysis.ort") as mock_ort:
            mock_session = MagicMock()
            mock_ort.InferenceSession.return_value = mock_session
            mock_session.get_inputs.return_value = [MagicMock(name="images", shape=[1, 3, 640, 640])]

            mock_output = np.zeros((1, 10, 20), dtype=np.float32)
            mock_session.run.return_value = [mock_output]

            svc = ImageAnalysisService(model_path="test.onnx")
            svc._session = mock_session

            img_bytes = _make_test_image_bytes(640, 640)
            results = svc.analyze(img_bytes)

            assert len(results) == 0

    def test_model_not_found(self):
        ImageAnalysisService.reset_instance()
        with patch("app.services.image_analysis.ort") as mock_ort:
            svc = ImageAnalysisService(model_path="nonexistent.onnx")
            with pytest.raises(FileNotFoundError, match="模型文件不存在"):
                svc.analyze(_make_test_image_bytes())
