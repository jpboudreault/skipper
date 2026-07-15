import os
from sqlmodel import SQLModel, create_engine, Session

# Using SQLite for local development, with env override for production volumes
sqlite_file_name = os.getenv("DATABASE_PATH", "database.db")
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
# SQL statement logging is noisy in production; enable it explicitly with SQL_ECHO=true.
sql_echo = os.getenv("SQL_ECHO", "false").lower() == "true"
engine = create_engine(sqlite_url, echo=sql_echo, connect_args=connect_args)

def _ensure_game_schedule_status_column() -> None:
    """Add schedule_status to existing SQLite databases without Alembic."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "game" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("game")}
    if "schedule_status" in columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE game ADD COLUMN schedule_status VARCHAR"))


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    _ensure_game_schedule_status_column()

def get_session():
    with Session(engine) as session:
        yield session
