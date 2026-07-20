"""Add metadata columns to chat_session_messages.

为 chat_session_messages 表增加 status / error_message / extra_json 三列:
  - status:         消息状态 (success / error / partial), 默认 success
  - error_message:  AI 回复失败时的错误信息, 仅 status=error 时有值
  - extra_json:     tokens / sources / rewritten_query 等元数据

Revision ID: 010_add_message_metadata
Revises: 009_add_sensor_reading
Create Date: 2026-07-19 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010_add_message_metadata"
down_revision: Union[str, Sequence[str], None] = "009_add_sensor_reading"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """给 chat_session_messages 增加 status / error_message / extra_json 列.

    老部署可能已经通过 Base.metadata.create_all 建表但缺少新列, 用 inspector 检测后跳过.
    兼容 SQLite 与 MySQL:
      - SQLite ALTER TABLE ADD COLUMN 不支持 IF NOT EXISTS, 用 inspector 检测
      - MySQL 同样用 inspector 检测, 避免重复添加
    """
    inspector = sa.inspect(op.get_bind())
    table_names = set(inspector.get_table_names())

    if "chat_session_messages" not in table_names:
        # 表不存在 (新部署将由 Base.metadata.create_all 创建), 跳过
        return

    existing_columns = {col["name"] for col in inspector.get_columns("chat_session_messages")}

    if "status" not in existing_columns:
        op.add_column(
            "chat_session_messages",
            sa.Column(
                "status",
                sa.String(length=16),
                nullable=False,
                server_default="success",
            ),
        )

    if "error_message" not in existing_columns:
        op.add_column(
            "chat_session_messages",
            sa.Column("error_message", sa.Text(), nullable=True),
        )

    if "extra_json" not in existing_columns:
        op.add_column(
            "chat_session_messages",
            sa.Column("extra_json", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    """回滚: 移除新增的三列."""
    inspector = sa.inspect(op.get_bind())
    table_names = set(inspector.get_table_names())

    if "chat_session_messages" not in table_names:
        return

    existing_columns = {col["name"] for col in inspector.get_columns("chat_session_messages")}

    # SQLite DROP COLUMN 需要 3.35+, MySQL 直接支持
    for col_name in ("extra_json", "error_message", "status"):
        if col_name in existing_columns:
            try:
                op.drop_column("chat_session_messages", col_name)
            except Exception:
                # SQLite 老版本不支持 DROP COLUMN, 允许跳过 (downgrade 失败不阻塞 upgrade)
                pass