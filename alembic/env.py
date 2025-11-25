import os
from logging.config import fileConfig
from alembic import context
from sqlalchemy import create_engine

# We use raw SQL migration scripts; no ORM models yet.
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

db_url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

target_metadata = None  # No SQLAlchemy models

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=False,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = create_engine(config.get_main_option("sqlalchemy.url"))
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=False,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
