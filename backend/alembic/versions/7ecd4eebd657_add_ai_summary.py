"""add ai_summary

Revision ID: 7ecd4eebd657
Revises: 7ecd4eebd656
Create Date: 2026-04-14 22:52:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7ecd4eebd657'
down_revision: Union[str, None] = '7ecd4eebd656'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('job_descriptions', sa.Column('ai_summary', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('job_descriptions', 'ai_summary')
