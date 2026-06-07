from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection

from alembic import context

# EVA application imports — populate target_metadata and build sync URL
from app.config import get_settings
from app.db import Base

# Register the pgvector type with the sync connection for Alembic migrations
import pgvector.psycopg

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLAlchemy model metadata for autogenerate support.
# All models registered via Base (DeclarativeBase) are included automatically.
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    settings = get_settings()
    url = settings.database_url.replace("+asyncpg", "+psycopg")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Uses a sync SQLAlchemy engine (via psycopg) because Alembic's
    migration operations require synchronous DBAPI connections.
    The pgvector type is registered on the raw connection so that
    operations on Vector columns work during migrations.
    """

    settings = get_settings()
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg")
    connectable = create_engine(sync_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        # register_vector needs the raw psycopg connection (via the pool fairy), not the SQLAlchemy wrapper
        pgvector.psycopg.register_vector(connection.connection.driver_connection)
        do_run_migrations(connection)

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
