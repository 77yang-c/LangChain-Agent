"""知识库文档存储（按 user_id 隔离，SQLite 持久化）"""

from datetime import datetime
from src.models.user import get_db


def init_docs_db():
    conn = get_db()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='documents'"
    ).fetchone()

    if row:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(documents)").fetchall()}
        if "user_id" not in cols:
            # 旧表无用户隔离：丢弃全局共享文档，重建为按用户隔离
            conn.executescript("""
                DROP TABLE documents;
                CREATE TABLE documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    content TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    uploaded_at TEXT NOT NULL,
                    UNIQUE(user_id, filename)
                );
            """)
    else:
        conn.execute("""
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                content TEXT NOT NULL,
                size INTEGER NOT NULL,
                uploaded_at TEXT NOT NULL,
                UNIQUE(user_id, filename)
            )
        """)

    conn.commit()
    conn.close()


def save_document(user_id: int, filename: str, content: str):
    conn = get_db()
    conn.execute(
        """
        INSERT INTO documents (user_id, filename, content, size, uploaded_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, filename) DO UPDATE SET
            content = excluded.content,
            size = excluded.size,
            uploaded_at = excluded.uploaded_at
        """,
        (user_id, filename, content, len(content), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def delete_document(user_id: int, filename: str) -> bool:
    conn = get_db()
    cur = conn.execute(
        "DELETE FROM documents WHERE user_id = ? AND filename = ?",
        (user_id, filename),
    )
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_documents(user_id: int) -> list:
    conn = get_db()
    rows = conn.execute(
        """
        SELECT filename, size, uploaded_at FROM documents
        WHERE user_id = ?
        ORDER BY uploaded_at DESC
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_contents(user_id: int) -> list:
    """获取该用户全部文档内容，供 RAG 加载"""
    conn = get_db()
    rows = conn.execute(
        "SELECT filename, content FROM documents WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


init_docs_db()
