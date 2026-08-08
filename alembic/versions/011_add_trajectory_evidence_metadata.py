"""Legacy migration compatibility anchor.

Revision ID: 011_trajectory_evidence
Revises: 010_add_message_metadata
"""

from typing import Sequence, Union


revision: str = "011_trajectory_evidence"
down_revision: Union[str, Sequence[str], None] = "010_add_message_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Keep databases stamped by the retired workflow migration upgradeable."""


def downgrade() -> None:
    """Compatibility anchors intentionally have no schema operation."""

