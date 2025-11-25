"""initial schema

Revision ID: 20241124_0001
Revises: 
Create Date: 2025-11-24

"""
from alembic import op
import os

# revision identifiers, used by Alembic.
revision = '20241124_0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Execute schema.sql idempotently. The file already uses IF NOT EXISTS guards.
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'db', 'schema.sql')
    # Normalize path
    schema_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'schema.sql'))
    with open(schema_path, 'r', encoding='utf-8') as f:
        sql = f.read()
    for stmt in [s.strip() for s in sql.split(';') if s.strip()]:
        op.execute(stmt)


def downgrade():
    # Explicit full drop not implemented; handle via manual script if needed.
    pass
