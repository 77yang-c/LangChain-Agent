# 阶段3：Agent 组装

## 一、从手动循环到 create_agent

阶段2 手动写了 ~30 行 while 循环处理工具调用。`create_agent` 一行替代：

```python
from langchain.agents import create_agent

agent = create_agent(
    model=llm,
    tools=ALL_TOOLS,
    checkpointer=memory,
    system_prompt="你是一个有用的助手，用中文回答，尽量简洁。",
)
```

## 二、create_agent 做了什么

```
create_agent 内部封装了：

1. llm.bind_tools(tools)        → 把工具描述转为 function calling schema
2. ReAct 循环                    → LLM 推理 → 执行工具 → 回传结果 → 再推理
3. 消息管理                      → 自动追加 ToolMessage 到对话历史
4. checkpointer 状态持久化       → 每轮对话自动保存/恢复
```

## 三、invoke 调用

```python
thread = {"configurable": {"thread_id": "user-1"}}

result = agent.invoke(
    {"messages": [("human", user_input)]},
    config=thread,
)

# result["messages"] 包含本轮完整消息链
final = result["messages"][-1]
print(final.content)
```

## 四、stream 流式输出

```python
for chunk, metadata in agent.stream(
    {"messages": [("human", user_input)]},
    config=thread,
    stream_mode="messages",
):
    # 过滤：只打印 AI 文本
    if isinstance(chunk, (AIMessage, AIMessageChunk)) and chunk.content:
        print(chunk.content, end="", flush=True)
```

### stream_mode 模式

| 值 | 输出粒度 |
|------|------|
| `"messages"` | 逐消息/token |
| `"updates"` | 逐节点（agent节点 → tools节点 → agent节点） |
| `"values"` | 每次状态更新后输出完整状态 |

## 五、显示工具调用过程

流式模式下 `tool_calls` 分 chunk 到达，需要判断完整性：

```python
if isinstance(chunk, AIMessageChunk):
    if hasattr(chunk, "tool_calls") and chunk.tool_calls:
        for tc in chunk.tool_calls:
            if tc.get("name"):                    # ★ 有 name 才算完整
                print(f"正在调用工具：{tc['name']}")
```

> 流式下 args 是分散到达的，同名工具调用只会在第一个有 name 的 chunk 触发打印。

## 六、从 langgraph.prebuilt 迁移到 langchain.agents

| 旧 | 新 |
|------|------|
| `from langgraph.prebuilt import create_react_agent` | `from langchain.agents import create_agent` |
| `state_modifier=SystemMessage(content="...")` | `system_prompt="..."` |

## 七、完整模板

```python
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, AIMessageChunk

from src.utlist.config import get_config
from src.tools.tools import ALL_TOOLS

config = get_config()
llm = ChatOpenAI(
    model=config.model_name,
    api_key=config.openai_api_key,
    base_url=config.base_url,
    temperature=config.temperature,
    timeout=30,
)

agent = create_agent(
    model=llm,
    tools=ALL_TOOLS,
    checkpointer=MemorySaver(),
    system_prompt="你是一个有用的助手，用中文回答，尽量简洁。",
)

thread = {"configurable": {"thread_id": "user-1"}}

while True:
    user_input = input("you>> ")
    if user_input.lower() in ("q", "quit", "exit"):
        break

    for chunk, metadata in agent.stream(
        {"messages": [("human", user_input)]},
        config=thread,
        stream_mode="messages",
    ):
        if isinstance(chunk, (AIMessage, AIMessageChunk)) and chunk.content:
            print(chunk.content, end="", flush=True)
    print()
```
