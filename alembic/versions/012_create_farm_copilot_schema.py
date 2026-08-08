"""Legacy migration compatibility anchor.

Revision ID: 012_farm_copilot_schema
Revises: 011_trajectory_evidence
"""

from typing import Sequence, Union


revision: str = "012_farm_copilot_schema"
down_revision: Union[str, Sequence[str], None] = "011_trajectory_evidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Keep databases stamped by the retired workflow migration upgradeable."""


def downgrade() -> None:
    """Compatibility anchors intentionally have no schema operation."""

