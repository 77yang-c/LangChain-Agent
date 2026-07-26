"""加载.env配置"""

import os
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

@dataclass
class Config:
    model_name : str = "GLM-4.7-flash"
    openai_api_key : str = ""
    base_url : str = ""
    temperature : float = 0.0
    cwd: str = os.getcwd()
    
    # GitHub OAuth 配置
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:5000/api/auth/github/callback"

def get_config() -> Config:
    return Config(
        model_name=os.getenv("MODEL_NAME",""),
        openai_api_key=os.getenv("OPENAI_API_KEY",""),
        base_url=os.getenv("BASE_URL",""),
        temperature=float(os.getenv("TEMPERATURE","0")),
        github_client_id=os.getenv("GITHUB_CLIENT_ID", ""),
        github_client_secret=os.getenv("GITHUB_CLIENT_SECRET", ""),
        github_redirect_uri=os.getenv("GITHUB_REDIRECT_URI", "http://localhost:5000/api/auth/github/callback"),
    )
