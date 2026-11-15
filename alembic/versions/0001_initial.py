"""Create users and mentions tables."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "mentions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("brand", sa.String(255), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sentiment", sa.String(32)),
        sa.Column("topic", sa.String(255)),
        sa.Column("urgency", sa.String(32)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("owner_id", "url", name="uq_mention_owner_url"),
    )
    op.create_index("ix_mentions_owner_id", "mentions", ["owner_id"])
    op.create_index("ix_mentions_brand", "mentions", ["brand"])
    op.create_index("ix_mentions_timestamp", "mentions", ["timestamp"])


def downgrade() -> None:
    op.drop_table("mentions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
