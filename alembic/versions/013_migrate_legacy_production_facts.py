"""Legacy migration compatibility anchor.

Revision ID: 013_copilot_facts
Revises: 012_farm_copilot_schema
"""

from typing import Sequence, Union


revision: str = "013_copilot_facts"
down_revision: Union[str, Sequence[str], None] = "012_farm_copilot_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Keep databases stamped by the retired workflow migration upgradeable."""


def downgrade() -> None:
    """Compatibility anchors intentionally have no schema operation."""

