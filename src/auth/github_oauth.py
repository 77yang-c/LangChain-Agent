"""GitHub OAuth 认证模块"""

import httpx
from typing import Optional, Tuple
from src.utlist.config import get_config

# GitHub OAuth URLs
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_API = "https://api.github.com/user"


def get_github_auth_url(state: str) -> str:
    """生成 GitHub 授权 URL"""
    config = get_config()
    client_id = config.github_client_id
    
    params = {
        "client_id": client_id,
        "redirect_uri": config.github_redirect_uri,
        "scope": "read:user user:email",
        "state": state,
    }
    
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GITHUB_AUTHORIZE_URL}?{query}"


async def exchange_code_for_token(code: str) -> Optional[str]:
    """用授权码换取 access_token"""
    config = get_config()
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": config.github_client_id,
                "client_secret": config.github_client_secret,
                "code": code,
                "redirect_uri": config.github_redirect_uri,
            },
            timeout=10.0,
        )
        
        if resp.status_code == 200:
            data = resp.json()
            return data.get("access_token")
    
    return None


async def get_github_user(access_token: str) -> Optional[dict]:
    """获取 GitHub 用户信息"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            GITHUB_USER_API,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=10.0,
        )
        
        if resp.status_code == 200:
            return resp.json()
    
    return None


async def get_github_user_email(access_token: str) -> Optional[str]:
    """获取 GitHub 用户邮箱（私有邮箱需要额外请求）"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_USER_API}/emails",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=10.0,
        )
        
        if resp.status_code == 200:
            emails = resp.json()
            for email in emails:
                if email.get("primary") and email.get("verified"):
                    return email.get("email")
    
    return None
