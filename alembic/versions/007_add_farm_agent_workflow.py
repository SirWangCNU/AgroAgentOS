"""Legacy migration compatibility anchor.

Revision ID: 007_add_farm_agent_workflow
Revises: 006_add_wx_binding
"""

from typing import Sequence, Union


revision: str = "007_add_farm_agent_workflow"
down_revision: Union[str, Sequence[str], None] = "006_add_wx_binding"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Keep databases stamped by the retired workflow migration upgradeable."""


def downgrade() -> None:
    """Compatibility anchors intentionally have no schema operation."""

