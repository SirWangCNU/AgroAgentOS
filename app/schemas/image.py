"""图片分析接口的数据模型."""

from pydantic import BaseModel, Field


class DetectionItem(BaseModel):
    """单个检测结果."""

    label: str = Field(..., description="检测标签 (英文)")
    chinese_name: str = Field(..., description="中文名称")
    confidence: float = Field(..., description="置信度 0-1", ge=0, le=1)
    bbox: list[float] = Field(
        ..., description="边界框 [x1, y1, x2, y2] (像素坐标)", min_length=4, max_length=4
    )


class ImageAnalysisResponse(BaseModel):
    """图片分析响应."""

    success: bool = Field(..., description="是否分析成功")
    detections: list[DetectionItem] = Field(
        default_factory=list, description="检测结果列表"
    )
    summary: str = Field(default="", description="识别结果摘要文本")
    diagnosis: str = Field(default="", description="多模态模型生成的详细诊断文本")
    model: str = Field(default="", description="使用的图像分析模型")
    image_size: list[int] = Field(
        default_factory=list, description="原始图片尺寸 [width, height]"
    )
    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "detections": [
                    {
                        "label": "powdery_mildew",
                        "chinese_name": "白粉病",
                        "confidence": 0.92,
                        "bbox": [120.5, 80.3, 350.2, 290.7],
                    }
                ],
                "summary": "检测到 1 个病虫害: 白粉病(92.0%)",
                "image_size": [640, 480],
            }
        }
    }
