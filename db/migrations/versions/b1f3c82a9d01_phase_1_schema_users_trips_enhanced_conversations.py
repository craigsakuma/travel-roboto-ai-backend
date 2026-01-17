"""phase 1 schema - users trips enhanced conversations

Revision ID: b1f3c82a9d01
Revises: a9a374705e02
Create Date: 2025-01-16 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b1f3c82a9d01'
down_revision: Union[str, Sequence[str], None] = 'a9a374705e02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema for Phase 1."""

    # ========================================================================
    # Create users table
    # ========================================================================
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('home_city', sa.String(length=100), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_users_email')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # ========================================================================
    # Create trips table
    # ========================================================================
    op.create_table(
        'trips',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('destination', sa.String(length=200), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('structured_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('raw_extractions', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_trips_created_by', 'trips', ['created_by_user_id'], unique=False)
    op.create_index('ix_trips_dates', 'trips', ['start_date', 'end_date'], unique=False)

    # ========================================================================
    # Create trip_travelers table (many-to-many)
    # ========================================================================
    op.create_table(
        'trip_travelers',
        sa.Column('trip_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='traveler'),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('trip_id', 'user_id')
    )
    op.create_index('ix_trip_travelers_user', 'trip_travelers', ['user_id'], unique=False)

    # ========================================================================
    # Modify existing conversations table
    # ========================================================================
    # Add trip_id foreign key constraint (it's currently just a string)
    # First, need to convert trip_id to UUID type if it's not already
    # Then add foreign key

    # Add new columns to conversations
    op.add_column('conversations', sa.Column('conversation_type', sa.String(length=50), nullable=False, server_default='chat'))
    op.add_column('conversations', sa.Column('next_turn_number', sa.Integer(), nullable=False, server_default='1'))

    # Drop old model tracking columns (moving to messages table)
    op.drop_column('conversations', 'model_used')
    op.drop_column('conversations', 'ab_test_variant')
    op.drop_column('conversations', 'message_count')

    # Update user_id and trip_id to be UUIDs and add foreign keys
    # Note: This assumes trip_id can be nullable during migration
    op.execute("ALTER TABLE conversations ALTER COLUMN user_id TYPE UUID USING user_id::uuid")
    op.execute("ALTER TABLE conversations ALTER COLUMN trip_id TYPE UUID USING trip_id::uuid")
    op.create_foreign_key('fk_conversations_user', 'conversations', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_conversations_trip', 'conversations', 'trips', ['id'], ['id'], ondelete='CASCADE')

    # Add unique constraint: one conversation per user per trip
    op.create_unique_constraint('uq_conversation_trip_user', 'conversations', ['trip_id', 'user_id', 'conversation_type'])

    # ========================================================================
    # Modify existing messages table
    # ========================================================================
    # Add new columns for Phase 1
    op.add_column('messages', sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('messages', sa.Column('turn_number', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('messages', sa.Column('model_provider', sa.String(length=50), nullable=True))
    op.add_column('messages', sa.Column('model_name', sa.String(length=100), nullable=True))
    op.add_column('messages', sa.Column('prompt_version', sa.String(length=20), nullable=True))
    op.add_column('messages', sa.Column('tool_calls', postgresql.JSONB(), nullable=True))
    op.add_column('messages', sa.Column('tokens_input', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('tokens_output', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('cost_usd', sa.Numeric(precision=10, scale=6), nullable=True))
    op.add_column('messages', sa.Column('latency_ms', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('feedback', sa.String(length=10), nullable=True))

    # Add foreign key for user_id
    op.create_foreign_key('fk_messages_user', 'messages', 'users', ['user_id'], ['id'], ondelete='SET NULL')

    # Add check constraint for role
    op.create_check_constraint('ck_message_role', 'messages', "role IN ('user', 'assistant', 'system', 'tool')")

    # Add new index for conversation_id + turn_number
    op.create_index('ix_messages_conversation_turn', 'messages', ['conversation_id', 'turn_number'], unique=False)

    # Drop old timestamp column and related indexes (using created_at instead)
    op.drop_index('ix_messages_conversation_timestamp', table_name='messages')
    op.drop_index(op.f('ix_messages_timestamp'), table_name='messages')
    op.drop_column('messages', 'timestamp')

    # Drop sources and extra_metadata (using specific columns now)
    op.drop_column('messages', 'sources')
    op.drop_column('messages', 'extra_metadata')

    # Drop updated_at (not needed for messages)
    op.drop_column('messages', 'updated_at')

    # ========================================================================
    # Create llm_requests table (observability)
    # ========================================================================
    op.create_table(
        'llm_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('model_provider', sa.String(length=50), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('full_prompt', sa.Text(), nullable=False),
        sa.Column('full_response', sa.Text(), nullable=False),
        sa.Column('tool_calls', postgresql.JSONB(), nullable=True),
        sa.Column('tokens_input', sa.Integer(), nullable=False),
        sa.Column('tokens_output', sa.Integer(), nullable=False),
        sa.Column('cost_usd', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('finish_reason', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_llm_requests_conversation', 'llm_requests', ['conversation_id'], unique=False)
    op.create_index('ix_llm_requests_created_at', 'llm_requests', ['created_at'], unique=False)
    op.create_index('ix_llm_requests_model', 'llm_requests', ['model_provider', 'model_name'], unique=False)

    # ========================================================================
    # Create metrics table
    # ========================================================================
    op.create_table(
        'metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('dimensions', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_metrics_name_time', 'metrics', ['metric_name', 'timestamp'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""

    # Drop metrics table
    op.drop_index('ix_metrics_name_time', table_name='metrics')
    op.drop_table('metrics')

    # Drop llm_requests table
    op.drop_index('ix_llm_requests_model', table_name='llm_requests')
    op.drop_index('ix_llm_requests_created_at', table_name='llm_requests')
    op.drop_index('ix_llm_requests_conversation', table_name='llm_requests')
    op.drop_table('llm_requests')

    # Restore messages table to original state
    op.add_column('messages', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False))
    op.add_column('messages', sa.Column('extra_metadata', postgresql.JSONB(), nullable=False, server_default='{}'))
    op.add_column('messages', sa.Column('sources', postgresql.JSONB(), nullable=True))
    op.add_column('messages', sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')))

    op.create_index(op.f('ix_messages_timestamp'), 'messages', ['timestamp'], unique=False)
    op.create_index('ix_messages_conversation_timestamp', 'messages', ['conversation_id', 'timestamp'], unique=False)

    op.drop_index('ix_messages_conversation_turn', table_name='messages')
    op.drop_constraint('ck_message_role', 'messages', type_='check')
    op.drop_constraint('fk_messages_user', 'messages', type_='foreignkey')

    op.drop_column('messages', 'feedback')
    op.drop_column('messages', 'latency_ms')
    op.drop_column('messages', 'cost_usd')
    op.drop_column('messages', 'tokens_output')
    op.drop_column('messages', 'tokens_input')
    op.drop_column('messages', 'tool_calls')
    op.drop_column('messages', 'prompt_version')
    op.drop_column('messages', 'model_name')
    op.drop_column('messages', 'model_provider')
    op.drop_column('messages', 'turn_number')
    op.drop_column('messages', 'user_id')

    # Restore conversations table
    op.drop_constraint('uq_conversation_trip_user', 'conversations', type_='unique')
    op.drop_constraint('fk_conversations_trip', 'conversations', type_='foreignkey')
    op.drop_constraint('fk_conversations_user', 'conversations', type_='foreignkey')

    # Convert UUID columns back to strings
    op.execute("ALTER TABLE conversations ALTER COLUMN trip_id TYPE VARCHAR(255)")
    op.execute("ALTER TABLE conversations ALTER COLUMN user_id TYPE VARCHAR(255)")

    op.add_column('conversations', sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('conversations', sa.Column('ab_test_variant', sa.String(length=50), nullable=True))
    op.add_column('conversations', sa.Column('model_used', sa.String(length=100), nullable=False, server_default='claude-3-5-sonnet'))

    op.drop_column('conversations', 'next_turn_number')
    op.drop_column('conversations', 'conversation_type')

    # Drop trip_travelers table
    op.drop_index('ix_trip_travelers_user', table_name='trip_travelers')
    op.drop_table('trip_travelers')

    # Drop trips table
    op.drop_index('ix_trips_dates', table_name='trips')
    op.drop_index('ix_trips_created_by', table_name='trips')
    op.drop_table('trips')

    # Drop users table
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
