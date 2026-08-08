"""Legacy migration compatibility anchor.

Revision ID: 008_crop_season_event
Revises: 007_add_farm_agent_workflow
"""

from typing import Sequence, Union


revision: str = "008_crop_season_event"
down_revision: Union[str, Sequence[str], None] = "007_add_farm_agent_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Keep databases stamped by the retired workflow migration upgradeable."""


def downgrade() -> None:
    """Compatibility anchors intentionally have no schema operation."""

