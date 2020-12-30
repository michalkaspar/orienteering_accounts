import os
import sys

import psycopg2


def test_postgresql():
    PGHOST = os.getenv("POSTGRESQL_HOST", "db")
    PGPORT = os.getenv("POSTGRESQL_PORT", 5432)
    PGDATABASE = os.getenv("POSTGRESQL_DATABASE", "postgres")
    PGUSER = os.getenv("POSTGRESQL_USER", "postgres")
    PGPASSWORD = os.getenv("POSTGRESQL_PASSWORD", "postgres")
    PGSSLMODE = os.getenv("POSTGRESQL_SSLMODE", "allow")

    try:
        conn = psycopg2.connect(
            host=PGHOST,
            port=PGPORT,
            dbname=PGDATABASE,
            user=PGUSER,
            password=PGPASSWORD,
            connect_timeout=1
        )
        conn.close()
        sys.exit(0)
    except Exception as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    test_postgresql()
