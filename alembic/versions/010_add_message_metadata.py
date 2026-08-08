"""Legacy migration compatibility anchor.

Revision ID: 010_add_message_metadata
Revises: 009_add_sensor_reading
"""

from typing import Sequence, Union


revision: str = "010_add_message_metadata"
down_revision: Union[str, Sequence[str], None] = "009_add_sensor_reading"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Keep databases stamped by the retired workflow migration upgradeable."""


def downgrade() -> None:
    """Compatibility anchors intentionally have no schema operation."""

