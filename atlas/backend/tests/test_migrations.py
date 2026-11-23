from alembic import command

from atlas.db import alembic_config


def test_models_match_migrations(client, tmp_path):
    """Falla si se cambia un modelo sin crear su migración de Alembic."""
    command.check(alembic_config(f"sqlite:///{tmp_path / 'atlas.db'}"))
