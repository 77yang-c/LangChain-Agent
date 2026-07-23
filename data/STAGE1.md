# 阶段1：LCEL 管道

## 一、LCEL 核心

```
chain = prompt | llm | parser
```

`|` 是管道运算符，数据从左流到右。一切组件都是 `Runnable`，接口统一，任意拼接。

```
{变量 dict}
    │
    ▼
┌──────────────────┐
│ prompt           │  ChatPromptTemplate
│ 模板 → 消息列表   │  from_messages()
└───────┬───────── ┘
        │ [SystemMessage, HumanMessage, ...]
        ▼
┌───────────────┐
│ llm           │  ChatOpenAI
│ 调用 API 推理  │  invoke() → AIMessage
└───────┬───────┘
        │ AIMessage
        ▼
┌───────────────┐
│ parser         │  StrOutputParser
│ AIMessage → str│
└───────┬───────┘
        │
        ▼
    纯文本字符串
```

## 二、三个基础组件

| 组件 | 类名 | 输入 | 输出 | 职责 |
|------|------|------|------|------|
| 提示模板 | `ChatPromptTemplate` | dict | `list[BaseMessage]` | 把变量填入模板 |
| 大模型 | `ChatOpenAI` | `list[BaseMessage]` | `AIMessage` | 调用 API |
| 输出解析 | `StrOutputParser` | `AIMessage` | `str` | 剥壳取文本 |

## 三、四种消息类型

```python
SystemMessage   →  角色设定、行为约束、规则
HumanMessage    →  用户输入的内容
AIMessage       →  LLM 返回的回复
ToolMessage     →  工具执行结果（阶段2 才会用到）
```

构建消息时可用元组简写：
```python
("system", "你是...")     →  SystemMessage
("human", "你好")         →  HumanMessage
("assistant", "你好啊")   →  AIMessage
```

## 四、三种调用方式

| 方法 | 行为 | 场景 |
|------|------|------|
| `invoke(input)` | 一次性返回完整结果 | 后台、脚本 |
| `stream(input)` | 逐 token 流式输出 | 聊天 UI |
| `batch(inputs)` | 并发处理多条 | 离线批处理 |

```python
# invoke
result = chain.invoke({"role": "数学老师", "language": "中文", "user_input": "勾股定理？"})

# stream
for chunk in chain.stream({"role": "...", "language": "...", "user_input": "..."}):
    print(chunk, end="", flush=True)

# batch
results = chain.batch([
    {"role": "数学老师", "language": "中文", "user_input": "勾股定理？"},
    {"role": "英语老师", "language": "中文", "user_input": "勾股定理？"},
])
```

## 五、多轮对话的两种写法

### 方案 A：占位符变量（单次）

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是{role}，用{language}回答。"),
    ("human", "{user_input}"),
])
chain.invoke({"role": "数学老师", "language": "中文", "user_input": "问题"})
```

适合一次性问答。

### 方案 B：MessagesPlaceholder（多轮）

```python
from langchain_core.prompts import MessagesPlaceholder

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是有用的助手，用中文回答，尽量简洁。"),
    MessagesPlaceholder(variable_name="messages"),
])

messages = [("human", "问题1"), ("assistant", "回答1"), ("human", "问题2")]
chain.invoke({"messages": messages})
```

适合对话，手动管理消息列表追加历史。

## 六、项目配置模式

```
.env        ←  API Key（不提交 Git）
.gitignore  ←  排除 .env、__pycache__、venv
config.py   ←  load_dotenv() + dataclass 统一入口
```

```python
# .env
OPENAI_API_KEY=sk-xxx
MODEL_NAME=deepseek-v4-pro
BASE_URL=https://api.deepseek.com

# config.py
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

@dataclass
class Config:
    model_name: str
    openai_api_key: str
    base_url: str
    temperature: float

def get_config() -> Config:
    return Config(
        model_name=os.getenv("MODEL_NAME", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        base_url=os.getenv("BASE_URL", ""),
        temperature=float(os.getenv("TEMPERATURE", "0")),
    )
```

## 七、对接非 OpenAI 模型

`ChatOpenAI` 默认连 OpenAI API，换模型只需加 `base_url`：

```python
ChatOpenAI(
    model="deepseek-v4-pro",
    api_key="sk-xxx",
    base_url="https://api.deepseek.com",   # ← 关键参数
)
```

---

## 阶段1 完整代码

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from src.utlist.config import get_config

# 1. Prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个有用的助手，用中文回答，尽量简洁。"),
    MessagesPlaceholder(variable_name="messages"),
])

# 2. LLM
config = get_config()
llm = ChatOpenAI(
    model=config.model_name,
    api_key=config.openai_api_key,
    base_url=config.base_url,
    temperature=config.temperature,
)

# 3. 管道
chain = prompt | llm | StrOutputParser()

# 4. 多轮对话
messages = []
while True:
    user_input = input("\n🧑 你：")
    if user_input.lower() in ("quit", "exit"):
        break
    messages.append(("human", user_input))

    print("\n🤖 AI：", end="", flush=True)
    full = ""
    for chunk in chain.stream({"messages": messages}):
        print(chunk, end="", flush=True)
        full += chunk
    print()

    messages.append(("assistant", full))
```
