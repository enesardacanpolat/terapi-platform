"""Profile education, appointment intake and authenticated reviews.

Existing reviews without authors are preserved, but not publicly displayed.
"""
from alembic import op
import sqlalchemy as sa

revision = 'b17c20260923'
down_revision = '63414cf93aec'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('therapist_profiles', sa.Column('education', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('appointments', sa.Column('mood', sa.String(20)))
    op.add_column('appointments', sa.Column('expectations', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('appointments', sa.Column('session_price', sa.Numeric(10, 2)))
    op.add_column('reviews', sa.Column('client_id', sa.UUID(), sa.ForeignKey('users.id')))
    op.create_unique_constraint('uq_review_client_therapist', 'reviews', ['therapist_id', 'client_id'])
    # NOT VALID preserves possible legacy outliers while enforcing all new writes.
    op.execute('ALTER TABLE reviews ADD CONSTRAINT ck_review_rating CHECK (rating BETWEEN 1 AND 5) NOT VALID')


def downgrade():
    op.drop_constraint('ck_review_rating', 'reviews')
    op.drop_constraint('uq_review_client_therapist', 'reviews')
    op.drop_column('reviews', 'client_id')
    op.drop_column('appointments', 'session_price')
    op.drop_column('appointments', 'expectations')
    op.drop_column('appointments', 'mood')
    op.drop_column('therapist_profiles', 'education')
