"""Initial migration - create all tables

Revision ID: 001_initial
Revises:
Create Date: 2026-05-28 14:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables."""
    # Create chat_sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(128), nullable=False),
        sa.Column('user_id', sa.String(128), nullable=True),
        sa.Column('title', sa.String(256), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('extra_json', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id'),
    )
    op.create_index('ix_chat_sessions_session_id', 'chat_sessions', ['session_id'])
    op.create_index('ix_chat_sessions_user_id', 'chat_sessions', ['user_id'])

    # Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(128), nullable=False),
        sa.Column('role', sa.String(32), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('extra_json', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'])

    # Create agent_execution_logs table
    op.create_table(
        'agent_execution_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(128), nullable=True),
        sa.Column('skill_name', sa.String(128), nullable=True),
        sa.Column('step_index', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('tool_name', sa.String(128), nullable=True),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_execution_logs_session_id', 'agent_execution_logs', ['session_id'])
    op.create_index('ix_agent_execution_logs_skill_name', 'agent_execution_logs', ['skill_name'])

    # Create history_records table
    op.create_table(
        'history_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('record_id', sa.String(32), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=True),
        sa.Column('source', sa.String(32), nullable=False),
        sa.Column('session_id', sa.String(128), nullable=True),
        sa.Column('skill', sa.String(128), nullable=True),
        sa.Column('sources_json', sa.Text(), nullable=True),
        sa.Column('extra_json', sa.Text(), nullable=True),
        sa.Column('knowledge_base_uploaded', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('record_id'),
    )
    op.create_index('ix_history_records_record_id', 'history_records', ['record_id'])
    op.create_index('ix_history_records_source', 'history_records', ['source'])
    op.create_index('ix_history_records_session_id', 'history_records', ['session_id'])

    # Create business_records table
    op.create_table(
        'business_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('record_type', sa.String(64), nullable=False),
        sa.Column('record_key', sa.String(256), nullable=True),
        sa.Column('title', sa.String(256), nullable=True),
        sa.Column('content_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_business_records_record_type', 'business_records', ['record_type'])
    op.create_index('ix_business_records_record_key', 'business_records', ['record_key'])

    # Create weather_queries table
    op.create_table(
        'weather_queries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('query_id', sa.String(64), nullable=False),
        sa.Column('location', sa.String(128), nullable=False),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('humidity', sa.Integer(), nullable=True),
        sa.Column('wind_speed', sa.Float(), nullable=True),
        sa.Column('wind_level', sa.Integer(), nullable=True),
        sa.Column('condition', sa.String(64), nullable=True),
        sa.Column('rain_probability', sa.Integer(), nullable=True),
        sa.Column('agriculture_advice', sa.Text(), nullable=True),
        sa.Column('session_id', sa.String(128), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('query_id'),
    )
    op.create_index('ix_weather_queries_query_id', 'weather_queries', ['query_id'])
    op.create_index('ix_weather_queries_location', 'weather_queries', ['location'])
    op.create_index('ix_weather_queries_session_id', 'weather_queries', ['session_id'])

    # Create marketing_tasks table
    op.create_table(
        'marketing_tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.String(64), nullable=False),
        sa.Column('product_name', sa.String(256), nullable=False),
        sa.Column('product_features', sa.Text(), nullable=True),
        sa.Column('target_platform', sa.String(64), nullable=False),
        sa.Column('content_style', sa.String(64), nullable=True),
        sa.Column('generated_title', sa.Text(), nullable=True),
        sa.Column('generated_content', sa.Text(), nullable=True),
        sa.Column('generated_script', sa.Text(), nullable=True),
        sa.Column('session_id', sa.String(128), nullable=True),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id'),
    )
    op.create_index('ix_marketing_tasks_task_id', 'marketing_tasks', ['task_id'])
    op.create_index('ix_marketing_tasks_session_id', 'marketing_tasks', ['session_id'])

    # Create pest_diagnoses table
    op.create_table(
        'pest_diagnoses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('diagnosis_id', sa.String(64), nullable=False),
        sa.Column('crop_type', sa.String(128), nullable=False),
        sa.Column('symptoms', sa.Text(), nullable=False),
        sa.Column('affected_part', sa.String(64), nullable=True),
        sa.Column('diagnosis_result', sa.Text(), nullable=True),
        sa.Column('treatment_plan', sa.Text(), nullable=True),
        sa.Column('session_id', sa.String(128), nullable=True),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('diagnosis_id'),
    )
    op.create_index('ix_pest_diagnoses_diagnosis_id', 'pest_diagnoses', ['diagnosis_id'])
    op.create_index('ix_pest_diagnoses_crop_type', 'pest_diagnoses', ['crop_type'])
    op.create_index('ix_pest_diagnoses_session_id', 'pest_diagnoses', ['session_id'])

    # Create agent_runs table
    op.create_table(
        'agent_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.String(64), nullable=False),
        sa.Column('session_id', sa.String(128), nullable=True),
        sa.Column('query', sa.Text(), nullable=True),
        sa.Column('selected_skill', sa.String(128), nullable=True),
        sa.Column('status', sa.String(32), nullable=True),
        sa.Column('total_steps', sa.Integer(), nullable=True),
        sa.Column('total_tool_calls', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('total_ms', sa.Integer(), nullable=True),
        sa.Column('model_used', sa.String(128), nullable=True),
        sa.Column('reroute_count', sa.Integer(), nullable=True),
        sa.Column('transitions_json', sa.Text(), nullable=True),
        sa.Column('report_preview', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id'),
    )
    op.create_index('ix_agent_runs_run_id', 'agent_runs', ['run_id'])
    op.create_index('ix_agent_runs_session_id', 'agent_runs', ['session_id'])
    op.create_index('ix_agent_runs_selected_skill', 'agent_runs', ['selected_skill'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('agent_runs')
    op.drop_table('pest_diagnoses')
    op.drop_table('marketing_tasks')
    op.drop_table('weather_queries')
    op.drop_table('business_records')
    op.drop_table('history_records')
    op.drop_table('agent_execution_logs')
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
