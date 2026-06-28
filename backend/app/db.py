import os
from sqlmodel import SQLModel, create_engine, Session

# Using SQLite for local development, with env override for production volumes
sqlite_file_name = os.getenv("DATABASE_PATH", "database.db")
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
# SQL statement logging is noisy in production; enable it explicitly with SQL_ECHO=true.
sql_echo = os.getenv("SQL_ECHO", "false").lower() == "true"
engine = create_engine(sqlite_url, echo=sql_echo, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
