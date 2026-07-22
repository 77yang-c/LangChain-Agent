"""加载.env配置"""

import os
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

@dataclass
class Config:
    model_name : str = "deepseek-v4-pro"
    openai_api_key : str = ""
    base_url : str = ""
    temperature : float = 0.0
    cwd: str = os.getcwd()

def get_config() -> Config:
    return Config(
        model_name=os.getenv("MODEL_NAME",""),
        openai_api_key=os.getenv("OPENAI_API_KEY",""),
        base_url=os.getenv("BASE_URL",""),
        temperature=float(os.getenv("TEMPERATURE","0")),
    )