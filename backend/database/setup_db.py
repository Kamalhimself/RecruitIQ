"""
RecruitIQ - Week 1
Database connection + setup script.

1. Create a .env with your DB credentials (or just edit DATABASE_URL below).
2. Run: python setup_db.py
   This will execute schema.sql against your database and create all tables.

Requires: pip install sqlalchemy psycopg2-binary python-dotenv
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------
# Edit this or set DATABASE_URL in your .env file
# Format: postgresql://<user>:<password>@<host>:<port>/<dbname>
# ------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:yourpassword@localhost:5432/recruitiq")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def get_engine():
    return create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


def run_schema(schema_path: str = "schema.sql"):
    engine = get_engine()
    with open(schema_path, "r") as f:
        schema_sql = f.read()

    with engine.connect() as conn:
        # Run as a single transaction; split is not needed because
        # SQLAlchemy + psycopg2 can execute multi-statement scripts
        # via raw connection.
        raw_conn = conn.connection
        with raw_conn.cursor() as cur:
            cur.execute(schema_sql)
        raw_conn.commit()

    print("✅ Schema applied successfully.")


def verify_tables():
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """))
        tables = [row[0] for row in result]

    print("Tables in DB:")
    for t in tables:
        print(f"  - {t}")


if __name__ == "__main__":
    run_schema()
    verify_tables()
