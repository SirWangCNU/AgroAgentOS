"""诊断记录管理接口.

POST   /api/v1/diagnosis/records          - 保存诊断记录
POST   /api/v1/diagnosis/records/conversation - 保存对话记录
GET    /api/v1/diagnosis/records          - 分页查询记录
GET    /api/v1/diagnosis/records/{id}     - 获取单条记录
DELETE /api/v1/diagnosis/records/{id}     - 删除单条记录
DELETE /api/v1/diagnosis/records          - 清空记录
GET    /api/v1/diagnosis/records/session/{session_id} - 获取会话记录
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from app.schemas.diagnosis import (
    ConversationRecordRequest,
    DiagnosisRecordRequest,
    RecordListResponse,
    RecordResponse,
)
from app.schemas.common import ApiResponse
from app.services.diagnosis_recorder import diagnosis_recorder

router = APIRouter(prefix="/diagnosis", tags=["diagnosis-records"])


@router.post(
    "/records",
    summary="保存诊断记录",
    description="将诊断结果保存到历史记录数据库",
    response_model=ApiResponse[RecordResponse],
)
async def save_diagnosis_record(req: DiagnosisRecordRequest) -> ApiResponse:
    """保存诊断记录.

    将 AIOps 诊断或监控系统产生的诊断结果保存到 SQLite 历史记录表中。
    """
    record_id = await diagnosis_recorder.record_diagnosis(
        question=req.question,
        answer=req.answer,
        source=req.source,
        session_id=req.session_id,
        skill=req.skill,
        sources=req.sources,
    )

    if not record_id:
        return ApiResponse.error(
            code="SAVE_FAILED",
            message="保存诊断记录失败",
        )

    record = await diagnosis_recorder.get_record(record_id)
    return ApiResponse.success(
        data=record,
        message="诊断记录已保存",
    )


@router.post(
    "/records/conversation",
    summary="保存对话记录",
    description="将 RAG 聊天对话保存到历史记录数据库",
    response_model=ApiResponse[RecordResponse],
)
async def save_conversation_record(req: ConversationRecordRequest) -> ApiResponse:
    """保存对话记录.

    将用户和助手的对话保存到 SQLite 历史记录表中。
    """
    record_id = await diagnosis_recorder.record_conversation(
        session_id=req.session_id,
        user_message=req.user_message,
        assistant_response=req.assistant_response,
        source=req.source,
        skill=req.skill,
    )

    if not record_id:
        return ApiResponse.error(
            code="SAVE_FAILED",
            message="保存对话记录失败",
        )

    record = await diagnosis_recorder.get_record(record_id)
    return ApiResponse.success(
        data=record,
        message="对话记录已保存",
    )


@router.get(
    "/records",
    summary="查询历史记录（分页）",
    description="分页查询诊断和对话的历史记录",
    response_model=ApiResponse[RecordListResponse],
)
async def list_records(
    page: int = 1,
    page_size: int = 20,
    source: str | None = None,
) -> ApiResponse:
    """分页查询历史记录.

    支持按来源筛选 (aiops/chat/monitoring)。
    """
    if page < 1:
        return ApiResponse.error(code="INVALID_PARAM", message="page 必须 >= 1")
    if page_size < 1 or page_size > 100:
        return ApiResponse.error(
            code="INVALID_PARAM", message="page_size 必须在 1-100 之间"
        )

    data = await diagnosis_recorder.list_records(
        page=page,
        page_size=page_size,
        source=source,
    )
    return ApiResponse.success(data=data)


@router.get(
    "/records/{record_id}",
    summary="获取单条历史记录",
    description="获取指定 ID 的历史记录详情",
    response_model=ApiResponse[RecordResponse],
)
async def get_record(record_id: str) -> ApiResponse:
    """获取指定 ID 的历史记录详情."""
    record = await diagnosis_recorder.get_record(record_id)
    if record is None:
        return ApiResponse.error(
            code="NOT_FOUND", message=f"记录不存在: {record_id}"
        )
    return ApiResponse.success(data=record)


@router.delete(
    "/records/{record_id}",
    summary="删除单条历史记录",
    description="删除指定 ID 的历史记录",
)
async def delete_record(record_id: str) -> ApiResponse:
    """删除指定 ID 的历史记录."""
    deleted = await diagnosis_recorder.delete_record(record_id)
    if not deleted:
        return ApiResponse.error(
            code="NOT_FOUND", message=f"记录不存在: {record_id}"
        )
    return ApiResponse.success(data={"record_id": record_id})


@router.delete(
    "/records",
    summary="清空历史记录",
    description="清空历史记录，默认清空全部来源",
)
async def clear_records(source: str | None = None) -> ApiResponse:
    """清空历史记录.

    支持按来源筛选清空。
    """
    count = await diagnosis_recorder.clear_records(source=source)
    return ApiResponse.success(data={"deleted_count": count})


@router.get(
    "/records/session/{session_id}",
    summary="获取会话的所有记录",
    description="根据 session_id 获取该会话的所有诊断和对话记录",
)
async def get_session_records(session_id: str) -> ApiResponse:
    """获取会话的所有记录."""
    records = await diagnosis_recorder.get_records_by_session(session_id)
    return ApiResponse.success(
        data={
            "session_id": session_id,
            "total": len(records),
            "records": records,
        }
    )
