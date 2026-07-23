"""工具模块： @tool """
from langchain_core.tools import tool
from datetime import datetime
from pathlib import Path
from src.utlist.config import Config


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

@tool
def web_tool_read(url : str)->str:
    """打开网页并获取页面文本内容。url 为完整的网页地址(如 https://example.com)。"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(headless=False)
        page = b.new_page()
        page.goto(url, timeout=15000)
        text = page.inner_text("body")
        b.close()
        return text[:8000]


from src.tools.rag import search_docs

    
ALL_TOOLS = [get_current_time,
             read_file,
             write_file,
             web_tool_read,
             search_docs
        ]