"""图片分析接口 (病虫害识别).

POST /api/v1/image/analyze
  -> 接收图片文件 (multipart/form-data)
  -> YOLO ONNX 模型推理
  -> 返回识别结果列表
"""

from fastapi import APIRouter, Depends, File, UploadFile
from loguru import logger

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.image import DetectionItem, ImageAnalysisResponse
from app.services.image_analysis import ImageAnalysisService

router = APIRouter(prefix="/image", tags=["image"])

# 允许的图片类型
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post(
    "/analyze",
    response_model=ImageAnalysisResponse,
    summary="病虫害图片识别",
    description=(
        "上传农作物图片, 使用 YOLO 模型识别病虫害类型.\n\n"
        "**支持格式**: JPEG, PNG, WebP\n"
        "**文件大小限制**: 10MB\n\n"
        "返回识别到的病虫害列表, 包含标签、置信度和边界框坐标."
    ),
)
async def analyze_image(
    file: UploadFile = File(..., description="待识别的图片文件"),
    current_user: User = Depends(get_current_user),
) -> ImageAnalysisResponse:
    # 校验文件类型
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        logger.warning(f"[image] 不支持的文件类型: {file.content_type}")
        return ImageAnalysisResponse(
            success=False,
            summary=f"不支持的图片格式: {file.content_type}, 请上传 JPEG/PNG/WebP",
        )

    # 读取文件内容
    image_bytes = await file.read()

    # 校验文件大小
    if len(image_bytes) > MAX_FILE_SIZE:
        logger.warning(f"[image] 文件过大: {len(image_bytes)} bytes")
        return ImageAnalysisResponse(
            success=False,
            summary=f"图片文件过大 ({len(image_bytes) // 1024 // 1024}MB), 限制 10MB",
        )

    logger.info(
        f"[image] 用户 {current_user.username} 上传图片: "
        f"{file.filename}, {file.content_type}, {len(image_bytes)} bytes"
    )

    try:
        service = ImageAnalysisService.get_instance()
        results = service.analyze(image_bytes)

        # 构建响应
        detections = [
            DetectionItem(
                label=r.label,
                chinese_name=r.chinese_name,
                confidence=r.confidence,
                bbox=list(r.bbox),
            )
            for r in results
        ]

        # 生成摘要
        if results:
            items = [f"{r.chinese_name}({r.confidence:.0%})" for r in results[:5]]
            summary = f"检测到 {len(results)} 个病虫害: {', '.join(items)}"
        else:
            summary = "未检测到明显病虫害症状, 图片可能为健康状态或需更清晰的图片"

        # 获取图片尺寸
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_bytes))
        image_size = list(img.size)

        return ImageAnalysisResponse(
            success=True,
            detections=detections,
            summary=summary,
            image_size=image_size,
        )

    except FileNotFoundError as e:
        logger.error(f"[image] 模型文件未找到: {e}")
        return ImageAnalysisResponse(
            success=False,
            summary="识别模型未部署, 请管理员先下载模型文件",
        )
    except Exception as e:
        logger.exception(f"[image] 推理异常: {e}")
        return ImageAnalysisResponse(
            success=False,
            summary=f"图片分析失败: {type(e).__name__}: {e}",
        )
