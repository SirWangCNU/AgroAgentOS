"""历史记录管理接口.

GET  /api/v1/history              - 分页查询历史记录
GET  /api/v1/history/{id}        - 获取单条记录详情
DELETE /api/v1/history/{id}      - 删除单条记录
POST /api/v1/history/{id}/upload-kb - 上传记录到知识库
DELETE /api/v1/history            - 清空历史记录
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from app.schemas.common import ApiResponse
import app.services.history_service as history_service

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", summary="查询历史记录（分页）")
async def list_history(
    page: int = 1,
    page_size: int = 20,
    source: str | None = None,
) -> ApiResponse:
    """分页查询历史记录，默认按时间倒序."""
    if page < 1:
        return ApiResponse.error(code="INVALID_PARAM", message="page 必须 >= 1")
    if page_size < 1 or page_size > 100:
        return ApiResponse.error(code="INVALID_PARAM", message="page_size 必须在 1-100 之间")

    data = await history_service.list_records(
        page=page,
        page_size=page_size,
        source=source,
    )
    return ApiResponse.success(data=data)


@router.get("/{record_id}", summary="获取单条历史记录")
async def get_history_record(record_id: str) -> ApiResponse:
    """获取指定 ID 的历史记录详情."""
    record = await history_service.get_record(record_id)
    if record is None:
        return ApiResponse.error(code="NOT_FOUND", message=f"记录不存在: {record_id}")
    return ApiResponse.success(data=record)


@router.delete("/{record_id}", summary="删除单条历史记录")
async def delete_history_record(record_id: str) -> ApiResponse:
    """删除指定 ID 的历史记录."""
    deleted = await history_service.delete_record(record_id)
    if not deleted:
        return ApiResponse.error(code="NOT_FOUND", message=f"记录不存在: {record_id}")
    return ApiResponse.success(data={"record_id": record_id})


@router.post("/{record_id}/upload-kb", summary="上传历史记录到知识库")
async def upload_to_knowledge_base(record_id: str) -> ApiResponse:
    """将历史记录上传到 RAG 知识库 (Milvus 向量库).

    将农业问答格式化为 Markdown 文档并分块存储，供后续 RAG 检索使用。
    """
    record = await history_service.get_record(record_id)
    if record is None:
        return ApiResponse.error(code="NOT_FOUND", message=f"记录不存在: {record_id}")

    if record.get("knowledge_base_uploaded"):
        return ApiResponse.error(code="ALREADY_UPLOADED", message="该记录已上传过知识库")

    if not record.get("answer"):
        return ApiResponse.error(code="NO_ANSWER", message="该记录没有回答，无法上传")

    success = await history_service.upload_record_to_kb(record_id)
    if not success:
        return ApiResponse.error(code="UPLOAD_FAILED", message="上传知识库失败，请检查 Milvus 服务是否正常")

    return ApiResponse.success(
        data={"record_id": record_id},
        message="已成功上传到知识库",
    )


@router.delete("", summary="清空历史记录")
async def clear_history(source: str | None = None) -> ApiResponse:
    """清空历史记录，默认清空全部来源.

    Query:
        source: 可选，按农业业务来源筛选清空
    """
    count = await history_service.clear_records(source=source)
    return ApiResponse.success(data={"deleted_count": count})
