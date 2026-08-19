"""appointments

Revision ID: 52950e066a5a
Revises: a302747b3abb
Create Date: 2026-08-19 15:40:35.581617

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '52950e066a5a'
down_revision: Union[str, Sequence[str], None] = 'a302747b3abb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table('appointments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('therapist_id', sa.UUID(), nullable=False),
    sa.Column('client_id', sa.UUID(), nullable=False),
    sa.Column('slot', postgresql.TSTZRANGE(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['client_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['therapist_id'], ['therapist_profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.execute("""
            ALTER TABLE appointments
            ADD CONSTRAINT no_overlap_therapist
            EXCLUDE USING gist (
                therapist_id WITH =,
                slot WITH &&
            ) WHERE (status IN ('pending', 'confirmed'))
        """)

    op.execute("""
            ALTER TABLE appointments
            ADD CONSTRAINT no_overlap_client
            EXCLUDE USING gist (
                client_id WITH =,
                slot WITH &&
            ) WHERE (status IN ('pending', 'confirmed'))
        """)

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('appointments')
    op.execute("DROP EXTENSION IF EXISTS btree_gist")