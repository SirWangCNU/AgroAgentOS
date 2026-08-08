"""Legacy migration compatibility anchor.

Revision ID: 014_retire_farm_flow
Revises: 013_copilot_facts
"""

from typing import Sequence, Union


revision: str = "014_retire_farm_flow"
down_revision: Union[str, Sequence[str], None] = "013_copilot_facts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Preserve the retired migration ID without reintroducing legacy tables."""


def downgrade() -> None:
    """Compatibility anchors intentionally have no schema operation."""

