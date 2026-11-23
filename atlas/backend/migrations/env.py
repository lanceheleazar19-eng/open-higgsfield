from alembic import context
from sqlalchemy import engine_from_config, pool

from atlas.models import Base

config = context.config
target_metadata = Base.metadata


def include_name(name, type_, parent_names):  # noqa: ANN001
    """Las tablas FTS5 de búsqueda (y sus tablas internas) se gestionan a mano en las migraciones."""
    if type_ == "table" and name and "_fts" in name:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        # render_as_batch: necesario para ALTER TABLE en SQLite
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True,
                          include_name=include_name)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
