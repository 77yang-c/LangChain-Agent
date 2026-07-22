"""工具模块： @tool """
from langchain_core.tools import tool
from datetime import datetime

@tool
def get_current_time() -> str:
    """获取当前日期和时间，不需要参数"""
    return datetime.now().strftime("%/%/% %:%:%")

ALL_TOOLS = [get_current_time]