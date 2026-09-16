import psycopg2
import psycopg2.extras
from app.config import DATABASE_URL


class _CursorWrapper:
    """包装 psycopg2 cursor，让 sqlite 风格的 '?' 占位符能自动转成 '%s'。"""

    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql, params=None):
        sql = sql.replace("?", "%s")
        self._cur.execute(sql, params if params else None)
        return self

    def executescript(self, script):
        self._cur.execute(script)

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def close(self):
        self._cur.close()

    @property
    def rowcount(self):
        return self._cur.rowcount


class _ConnWrapper:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        return _CursorWrapper(cur)

    def execute(self, sql, params=None):
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql = sql.replace("?", "%s")
        cur.execute(sql, params if params else None)
        return _CursorWrapper(cur)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_client():
    conn = psycopg2.connect(DATABASE_URL)
    return _ConnWrapper(conn)


def init_db():
    pass