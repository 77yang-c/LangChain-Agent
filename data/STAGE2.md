# 阶段2：Tool 定义与绑定

## 一、Tool 是什么

LLM 只能输出文本，Tool 让它能**执行外部动作**——读文件、搜网页、调 API。

```
用户说"帮我查一下 README.md"
        ↓
LLM 判断 → 调用 read_file("README.md")
        ↓
工具执行 → 返回文件内容
        ↓
LLM 根据内容回答用户
```

## 二、@tool 装饰器

```python
from langchain_core.tools import tool

@tool
def read_file(path: str) -> str:
    """读取指定文件的内容。path 为文件的完整路径或相对于当前目录的路径。"""
    p = Path(path)
    return p.read_text(encoding="utf-8")
```

三个要素：

| 要素 | 来源 | LLM 怎么用 |
|------|------|-----------|
| 工具名 | 函数名 | 知道"该调谁" |
| 功能描述 | docstring | 知道"什么时候调" |
| 参数列表 | 类型注解 + docstring | 知道"传什么参数" |

## 三、无参 vs 有参工具

```python
# 无参数
@tool
def get_current_time() -> str:
    """获取当前日期和时间，不需要参数。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 有参数（LLM 根据 docstring 自动填）
@tool
def write_file(path: str, content: str) -> str:
    """将内容写入文件。path 为文件路径，content 为要写入的内容。"""
    ...
```

## 四、工具注册表

所有工具放进一个列表，统一管理：

```python
ALL_TOOLS = [get_current_time, read_file, write_file, web_tool_read]
```

## 五、bind_tools 绑定（手动模式）

```python
llm_with_tools = llm.bind_tools(ALL_TOOLS)
```

原理：langchain 把工具定义的函数签名转为 OpenAI/DeepSeek 的 function calling JSON schema，随请求一起发给 LLM。LLM 看到 schema 就知道有哪些工具可用。

手动循环：

```python
llm_with_tools = llm.bind_tools(tools)

while True:
    response = llm_with_tools.invoke(messages)

    if response.tool_calls:
        for tc in response.tool_calls:
            tool = tools_by_name[tc["name"]]
            result = tool.invoke(tc["args"])
            messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
    else:
        print(response.content)   # 最终答案
        break
```

## 六、Playwright 浏览器工具

```bash
pip install playwright
playwright install chromium
```

```python
@tool
def web_tool_read(url: str) -> str:
    """打开网页并获取页面文本内容。url 为完整的网页地址。"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)    # headless=False 可见浏览器窗口
        page = b.new_page()
        page.goto(url, timeout=15000)
        text = page.inner_text("body")
        b.close()
        return text[:8000]
```

## 七、Tool 设计 checklist

- [ ] 函数名清晰，一看就知道干什么
- [ ] docstring 第一行说清楚功能，LLM 据此判断何时调用
- [ ] 每个参数有类型注解（`: str`）
- [ ] docstring 里描述每个参数的含义
- [ ] 加入 ALL_TOOLS 注册表
