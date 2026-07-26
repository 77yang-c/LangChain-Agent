"""工具模块： @tool """
from langchain_core.tools import tool
from datetime import datetime
from pathlib import Path


@tool
def get_current_time() -> str:
    """获取当前日期和时间，不需要参数"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@tool
def read_file(path: str) -> str:
    """读取指定文件的内容。path 为文件的完整路径或相对于当前目录的路径。"""
    p = Path(path)
    if not p.is_absolute():
        p = Path.cwd()/p
    p = p.resolve()
    if not p.exists():
        return f"文件不存在：{p}"
    return p.read_text(encoding="utf-8", errors="replace")[:60000]

@tool
def write_file(path: str, content: str) -> str:
    """将内容写入文件。path 为文件路径，content 为要写入的内容。"""
    p = Path(path)
    if not p.is_absolute():
        p = Path.cwd()/p
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"文件已经写入: {p}"

from src.tools.rag import search_docs


ALL_TOOLS = [get_current_time,
             read_file,
             write_file,
             search_docs
        ]