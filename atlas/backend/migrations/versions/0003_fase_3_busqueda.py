"""fase 3: índices de búsqueda de texto completo (SQLite FTS5)

Revision ID: 0003
Revises: 0002
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# (tabla FTS, tabla origen, columna)
INDEXES = [("memory_fts", "memories", "content"), ("message_fts", "conversation_messages", "content")]


def upgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return  # en PostgreSQL la búsqueda usa LIKE (o tsvector en el futuro)
    for fts, src, col in INDEXES:
        op.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {fts} USING fts5("
            f"{col}, content='{src}', content_rowid='id', tokenize='unicode61 remove_diacritics 2')"
        )
        op.execute(f"CREATE TRIGGER IF NOT EXISTS {fts}_ai AFTER INSERT ON {src} BEGIN "
                   f"INSERT INTO {fts}(rowid, {col}) VALUES (new.id, new.{col}); END")
        op.execute(f"CREATE TRIGGER IF NOT EXISTS {fts}_ad AFTER DELETE ON {src} BEGIN "
                   f"INSERT INTO {fts}({fts}, rowid, {col}) VALUES ('delete', old.id, old.{col}); END")
        op.execute(f"CREATE TRIGGER IF NOT EXISTS {fts}_au AFTER UPDATE OF {col} ON {src} BEGIN "
                   f"INSERT INTO {fts}({fts}, rowid, {col}) VALUES ('delete', old.id, old.{col}); "
                   f"INSERT INTO {fts}(rowid, {col}) VALUES (new.id, new.{col}); END")
        op.execute(f"INSERT INTO {fts}({fts}) VALUES ('rebuild')")


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    for fts, _src, _col in INDEXES:
        for t in ("ai", "ad", "au"):
            op.execute(f"DROP TRIGGER IF EXISTS {fts}_{t}")
        op.execute(f"DROP TABLE IF EXISTS {fts}")
