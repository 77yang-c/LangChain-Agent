"""知识库文档存储（SQLite，不受 Git 部署影响）"""

from datetime import datetime
from src.models.user import get_db


def init_docs_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            content TEXT NOT NULL,
            size INTEGER NOT NULL,
            uploaded_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_document(filename: str, content: str):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO documents (filename, content, size, uploaded_at) VALUES (?, ?, ?, ?)",
        (filename, content, len(content), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def delete_document(filename: str):
    conn = get_db()
    conn.execute("DELETE FROM documents WHERE filename = ?", (filename,))
    conn.commit()
    conn.close()


def get_documents() -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT filename, size, uploaded_at FROM documents ORDER BY uploaded_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_contents() -> list:
    """获取所有文档内容，供 RAG 加载"""
    conn = get_db()
    rows = conn.execute("SELECT filename, content FROM documents").fetchall()
    conn.close()
    return [dict(r) for r in rows]


init_docs_db()
