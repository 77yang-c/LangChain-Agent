"""用户数据库模型"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

# 数据库文件路径
DB_DIR = Path(__file__).parent.parent.parent / "user_data"
DB_PATH = DB_DIR / "users.db"


def get_db():
    """获取数据库连接"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            github_id INTEGER UNIQUE NOT NULL,
            username TEXT NOT NULL,
            avatar_url TEXT,
            email TEXT,
            access_token TEXT,
            created_at TEXT NOT NULL,
            last_login TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    conn.commit()
    conn.close()


def upsert_user(github_id: int, username: str, avatar_url: str, email: Optional[str], access_token: str) -> int:
    """创建或更新用户，返回用户ID"""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    cursor.execute("SELECT id FROM users WHERE github_id = ?", (github_id,))
    row = cursor.fetchone()
    
    if row:
        user_id = row["id"]
        cursor.execute("""
            UPDATE users 
            SET username = ?, avatar_url = ?, email = ?, access_token = ?, last_login = ?
            WHERE github_id = ?
        """, (username, avatar_url, email, access_token, now, github_id))
    else:
        cursor.execute("""
            INSERT INTO users (github_id, username, avatar_url, email, access_token, created_at, last_login)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (github_id, username, avatar_url, email, access_token, now, now))
        user_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    return user_id


def create_session(user_id: int) -> str:
    """创建会话，返回 session_id"""
    import secrets
    
    conn = get_db()
    cursor = conn.cursor()
    
    session_id = secrets.token_urlsafe(32)
    now = datetime.now()
    expires_at = datetime.fromtimestamp(now.timestamp() + 7 * 24 * 3600)  # 7天过期
    
    cursor.execute("""
        INSERT INTO sessions (session_id, user_id, created_at, expires_at)
        VALUES (?, ?, ?, ?)
    """, (session_id, user_id, now.isoformat(), expires_at.isoformat()))
    
    conn.commit()
    conn.close()
    return session_id


def get_user_by_session(session_id: str) -> Optional[dict]:
    """通过 session_id 获取用户信息"""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    cursor.execute("""
        SELECT u.* FROM users u
        JOIN sessions s ON u.id = s.user_id
        WHERE s.session_id = ? AND s.expires_at > ?
    """, (session_id, now))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def get_user_by_github_id(github_id: int) -> Optional[dict]:
    """通过 github_id 获取用户信息"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE github_id = ?", (github_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


# 初始化数据库
init_db()
