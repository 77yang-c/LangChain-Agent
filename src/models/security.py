"""OAuth state / 限流等安全相关持久化（SQLite，重启不丢）"""

from datetime import datetime, timedelta
from src.models.user import get_db


def init_security_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS oauth_states (
            state TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            user_id INTEGER NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rate_limits_user_time ON rate_limits(user_id, created_at)"
    )
    conn.commit()
    conn.close()


def save_oauth_state(state: str, ttl_seconds: int = 600) -> None:
    """保存 OAuth CSRF state，默认 10 分钟过期"""
    now = datetime.now()
    expires = now + timedelta(seconds=ttl_seconds)
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO oauth_states (state, created_at, expires_at) VALUES (?, ?, ?)",
        (state, now.isoformat(), expires.isoformat()),
    )
    # 顺手清理过期 state
    conn.execute("DELETE FROM oauth_states WHERE expires_at < ?", (now.isoformat(),))
    conn.commit()
    conn.close()


def consume_oauth_state(state: str) -> bool:
    """校验并一次性消费 state；无效或过期返回 False"""
    now = datetime.now().isoformat()
    conn = get_db()
    row = conn.execute(
        "SELECT state FROM oauth_states WHERE state = ? AND expires_at > ?",
        (state, now),
    ).fetchone()
    if not row:
        conn.close()
        return False
    conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
    conn.commit()
    conn.close()
    return True


def check_rate_limit(user_id: int, limit: int = 10, window: int = 60) -> bool:
    """滑动窗口限流。允许则记一次并返回 True，超限返回 False。"""
    now = datetime.now().timestamp()
    cutoff = now - window
    conn = get_db()
    conn.execute(
        "DELETE FROM rate_limits WHERE user_id = ? AND created_at < ?",
        (user_id, cutoff),
    )
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM rate_limits WHERE user_id = ? AND created_at >= ?",
        (user_id, cutoff),
    ).fetchone()["c"]
    if count >= limit:
        conn.commit()
        conn.close()
        return False
    conn.execute(
        "INSERT INTO rate_limits (user_id, created_at) VALUES (?, ?)",
        (user_id, now),
    )
    conn.commit()
    conn.close()
    return True


init_security_db()
