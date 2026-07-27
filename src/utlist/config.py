"""加载.env配置"""

import os
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

@dataclass
class Config:
    model_name: str = "deepseek-v4-flash"
    openai_api_key: str = ""
    base_url: str = ""
    temperature: float = 0.0
    cwd: str = os.getcwd()

    # Embedding 独立配置（可与主模型不同提供商）
    embedding_model: str = "embedding-3"
    embedding_api_key: str = ""
    embedding_base_url: str = ""

    # GitHub OAuth 配置
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:5000/api/auth/github/callback"


def get_config() -> Config:
    return Config(
        model_name=os.getenv("MODEL_NAME", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        base_url=os.getenv("BASE_URL", ""),
        temperature=float(os.getenv("TEMPERATURE", "0")),
        embedding_model=os.getenv("EMBEDDING_MODEL", "embedding-3"),
        embedding_api_key=os.getenv("EMBEDDING_API_KEY", ""),
        embedding_base_url=os.getenv("EMBEDDING_BASE_URL", ""),
        github_client_id=os.getenv("GITHUB_CLIENT_ID", ""),
        github_client_secret=os.getenv("GITHUB_CLIENT_SECRET", ""),
        github_redirect_uri=os.getenv("GITHUB_REDIRECT_URI", "http://localhost:5000/api/auth/github/callback"),
    )
