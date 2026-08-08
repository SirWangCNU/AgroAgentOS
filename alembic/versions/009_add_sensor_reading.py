"""Legacy migration compatibility anchor.

Revision ID: 009_add_sensor_reading
Revises: 008_crop_season_event
"""

from typing import Sequence, Union


revision: str = "009_add_sensor_reading"
down_revision: Union[str, Sequence[str], None] = "008_crop_season_event"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Keep databases stamped by the retired workflow migration upgradeable."""


def downgrade() -> None:
    """Compatibility anchors intentionally have no schema operation."""

