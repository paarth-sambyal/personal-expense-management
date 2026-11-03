"""MySQL connection helpers. Credentials are read only from environment."""
import os
from contextlib import contextmanager

import mysql.connector
from mysql.connector import pooling

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        ssl_ca = os.getenv("DB_SSL_CA", "").strip()
        ssl_options = {"ssl_ca": ssl_ca, "ssl_verify_cert": True} if ssl_ca else {}
        _pool = pooling.MySQLConnectionPool(
            pool_name="expense_pool", pool_size=5,
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            database=os.getenv("DB_NAME", "personal_expense_db"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            autocommit=False,
            **ssl_options,
        )
    return _pool


@contextmanager
def connection():
    conn = get_pool().get_connection()
    try:
        yield conn
    finally:
        conn.close()


def query(sql, params=(), *, one=False, commit=False):
    """Execute parameterised SQL and return dictionaries or affected rows."""
    with connection() as conn:
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(sql, params)
            if commit:
                conn.commit()
                return cur.lastrowid if cur.lastrowid else cur.rowcount
            if not cur.with_rows:
                return cur.rowcount
            return cur.fetchone() if one else cur.fetchall()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


def execute_transaction(statements):
    """Run a sequence of (SQL, params) statements atomically."""
    with connection() as conn:
        cur = conn.cursor()
        try:
            for sql, params in statements:
                cur.execute(sql, params)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
