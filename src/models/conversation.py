"""对话持久化存储"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional
from src.models.user import get_db, DB_DIR


def init_conversation_db():
    """初始化对话表"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            thread_id TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, thread_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            thread_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def save_message(user_id: int, thread_id: str, role: str, content: str):
    """保存一条消息"""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    # 确保 conversation 存在
    cursor.execute("""
        INSERT INTO conversations (user_id, thread_id, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, thread_id) DO UPDATE SET updated_at = ?
    """, (user_id, thread_id, '', now, now, now))

    cursor.execute("""
        INSERT INTO messages (user_id, thread_id, role, content, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, thread_id, role, content, now))

    # 自动取第一句用户消息作为标题
    cursor.execute("""
        UPDATE conversations
        SET title = (SELECT content FROM messages WHERE thread_id = ? AND role = 'human' ORDER BY id LIMIT 1)
        WHERE user_id = ? AND thread_id = ? AND title = ''
    """, (thread_id, user_id, thread_id))

    conn.commit()
    conn.close()


def get_conversations(user_id: int) -> list:
    """获取用户的所有对话列表"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT thread_id, title, created_at, updated_at
        FROM conversations
        WHERE user_id = ?
        ORDER BY updated_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_messages(user_id: int, thread_id: str) -> list:
    """获取某个对话的所有消息"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content, created_at
        FROM messages
        WHERE user_id = ? AND thread_id = ?
        ORDER BY id ASC
    """, (user_id, thread_id))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


init_conversation_db()
