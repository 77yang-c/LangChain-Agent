# 基于 LangChain 架构的 Agent

## 一、LangChain 架构概览

```
┌──────────────────────────────────────────────────────┐
│                    LangGraph                         │
│           有状态、带分支的 Agent 编排框架                │
├──────────────────────────────────────────────────────┤
│                   langchain                          │
│      Chains / Agents / Tools — 高层应用组装            │
├──────────────────────────────────────────────────────┤
│               langchain-community                    │
│   三方集成：文档加载器、向量库、LLM 提供商                  │
├──────────────────────────────────────────────────────┤
│                 langchain-core                       │
│  基础抽象：BaseChatModel / BaseTool / Runnable         │
└──────────────────────────────────────────────────────┘
```

| 包 | 职责 | 例子 |
|----|------|------|
| `langchain-core` | 接口与基础抽象 | `BaseChatModel`, `BaseTool`, `Runnable` |
| `langchain` | 高层组装 | `create_react_agent`, `ChatPromptTemplate` |
| `langchain-community` | 社区集成 | `WebBaseLoader`, `Chroma` |
| `langgraph` | 状态图编排 | 多步 Agent、条件分支、人机协作 |

---

## 二、核心概念

### 2.1 Runnable 协议（LCEL 基石）

一切组件都实现 `Runnable`，通过 `|` 管道串联：

```python
chain = prompt | llm | output_parser    # 数据从左流到右
```

```python
class Runnable:
    def invoke(input) -> output           # 同步
    def stream(input) -> Iterator         # 流式
    def batch(inputs) -> list             # 批量
```

### 2.2 六大组件

```
PromptTemplate          ChatModel               Tool
┌──────────────┐   ┌──────────────┐    ┌──────────────┐
│ 格式化输入     │ → │ LLM 推理      │ →  │ 外部动作       │
│ 系统指令      │   │ 返回消息       │    │ 搜索/计算/API  │
└──────────────┘   └──────────────┘    └──────────────┘

    Message               Agent
┌──────────────┐   ┌──────────────┐
│ 对话原子      │ ← │ 决策循环       │
│ System/Human │   │ 观察→思考→行动 │
│ AI/Tool      │   └──────────────┘
└──────────────┘

DocumentLoader         VectorStore         Retriever
┌──────────────┐   ┌──────────────┐    ┌──────────────┐
│ 加载文档       │ → │ 向量嵌入存储    │ →  │ 语义检索       │
│ PDF/Web/TXT  │   │ 相似度搜索      │    │ 返回相关文档    │
└──────────────┘   └──────────────┘    └──────────────┘
```

### 2.3 四种消息类型

```python
SystemMessage    # 系统指令（角色设定、规则）
HumanMessage     # 用户输入
AIMessage        # LLM 回复（可含 tool_calls）
ToolMessage      # 工具执行结果（关联 tool_call_id）
```

---

## 三、Agent 运行机制

### 3.1 ReAct 循环

```
用户输入
  ↓
┌─────────────────────────┐
│ 构建上下文                 │
│ SystemMessage + Tool描述  │←──────────────┐
│ + 历史消息 + HumanMessage  │               │
└──────────┬──────────────┘               │
           ↓                              │
┌─────────────────────────┐               │
│ LLM 推理 (bind_tools)    │               │
└──────────┬──────────────┘               │
           ↓                              │
     ┌─────┴─────┐                        │
     │ 返回内容？  │                        │
     └─────┬─────┘                        │
  工具调用   │    文本回复                   │
     ↓      │       ↓                      │
┌────────┐  │  ┌──────────┐               │
│执行Tool │  │  │ 最终答案   │               │
│结果回传 ───┘  │ 结束循环   │               │
└────────┘     └──────────┘               │
```

### 3.2 消息流示例

```
第1轮: [System, Human("北京天气？")]
  → LLM → AIMessage(tool_calls=[get_weather("北京")])
  → 执行 get_weather → ToolMessage("北京: 25°C, 晴")

第2轮: [System, Human, AI(tool_calls), Tool(result)]
  → LLM → AIMessage("北京今天晴天，25°C。")
  → 无工具调用 → 最终答案
```

### 3.3 两种 Agent 模式

| 模式 | 实现 | 特点 |
|------|------|------|
| **Tool Calling Agent** | `create_tool_calling_agent` | 依赖 LLM 原生 function calling |
| **ReAct Agent** | `create_react_agent`（推荐） | LangGraph 实现，有状态，自动管理消息 |

```python
from langgraph.prebuilt import create_react_agent

agent = create_agent(
    model=llm,
    tools=[calculator, get_time],
    checkpointer=MemorySaver(),              # 记忆持久化
    state_modifier=SystemMessage(content="..."),  # 系统指令
)
result = agent.invoke({"messages": [HumanMessage(content="...")]})
```

---

## 四、项目结构

```
langchain-agent/
├── README.md                   # 本文档
├── requirements.txt            # 依赖
├── .env                        # API Key（不提交 Git）
├── .gitignore
│
├── src/
│   ├── main.py                 # 入口：交互对话循环
│   │
│   ├── agent/
│   │   └── agent.py            # create_react_agent() 封装
│   │
│   ├── tools/
│   │   └── tools.py            # @tool 装饰器定义工具
│   │
│   ├── prompts/
│   │   └── prompts.py          # 系统提示词模板
│   │
│   ├── memory/
│   │   └── memory.py           # MemorySaver / SqliteSaver
│   │
│   └── utils/
│       └── config.py           # 加载 .env 配置
│
├── data/                       # RAG 文档
│
└── tests/
    └── test_agent.py           # 冒烟测试
```

### 模块职责

| 模块 | 文件 | 一句话 |
|------|------|--------|
| 入口 | `main.py` | 初始化 → 交互循环 → 输出结果 |
| Agent | `agent.py` | 拼装 LLM + Tools + Memory → 一个 Agent |
| Tools | `tools.py` | 注册外部能力：计算、搜索、API |
| Prompts | `prompts.py` | 控制系统指令，定义 Agent 角色 |
| Memory | `memory.py` | 对话历史持久化，跨轮记忆 |
| Config | `config.py` | 读 `.env`，统一提供配置 |

---

## 五、数据流全景

```
.env  ──→  Config  ──→  LLM
                         │
Prompt ──→  Agent ──→  ReAct 循环
                         │
              ┌──────────┴──────────┐
              ↓                     ↓
         有 Tool 调用           无 Tool 调用
              ↓                     ↓
         执行 Tool ──→ 回传结果     最终答案 → 用户
              ↓
         Memory 持久化
```

---

## 六、学习路线

```
阶段1  环境搭建 + Chain 管道     → prompt | llm 跑通
阶段2  注册 Tool                → llm.bind_tools()
阶段3  组装 Agent               → create_agent()
阶段4  添加 Memory              → SqliteSaver 持久化
阶段5  接入 RAG                 → 文档加载 → 向量存储 → 检索增强
阶段6  进阶：多 Agent / LangGraph → 多 Agent 协作
```

## 部署步骤

### 1. 环境要求

- **Python 3.10+**
- 建议使用虚拟环境

### 2. 创建虚拟环境 & 安装依赖

```bash
# 进入项目目录
cd langchain-agent

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 安装 Playwright 浏览器

`web_tool_read` 工具依赖 Playwright 驱动 Chromium：

```bash
playwright install chromium
```

### 4. 配置环境变量

编辑项目根目录的 `.env` 文件：

```env
OPENAI_API_KEY=你的API_KEY
MODEL_NAME=deepseek-v4-pro        # 或其他兼容 OpenAI 协议的模型
BASE_URL=https://api.deepseek.com  # API 地址
TEMPERATURE=0.0                    # 可选，默认 0
```

当前已配置的是 DeepSeek API，你也可以换成其他兼容 OpenAI 接口的提供商。

### 5. 运行

```bash
python src/main.py
```

进入交互循环后：

```
you>> 现在几点了？
正在调用工具：get_current_time
2025-01-15 14:30:00

you>> q    # 输入 q / quit / exit 退出
再见
```

---

## 项目架构速览

```
用户输入 → main.py (交互循环)
              ↓
         agent.py (create_react_agent)
              ↓
    ┌─────────┼─────────┐
   LLM      Tools     Memory
(DeepSeek) (get_current_time,  (MemorySaver)
           read_file,
           write_file,
           web_tool_read)
```

| 文件 | 职责 |
|------|------|
| `src/main.py` | 入口，交互式对话循环 + 流式输出 |
| `src/agent/agent.py` | `create_react_agent` 封装 |
| `src/tools/tools.py` | 四个工具：时间、文件读写、网页抓取 |
| `src/utlist/config.py` | 加载 `.env` 配置 |
| `src/memory/memory.py` | 对话记忆持久化 |
| `src/prompts/prompts.py` | 系统提示词模板 |

---

## 常见问题

| 问题 | 解决 |
|------|------|
| `ModuleNotFoundError: src.utlist` | 确保在项目根目录运行 `python src/main.py` |
| Playwright 报错 | 执行 `playwright install chromium` |
| API 连接失败 | 检查 `.env` 中的 `BASE_URL` 和 `API_KEY` 是否正确 |
| Chromium 启动失败 | Linux 服务器需安装依赖：`playwright install-deps chromium` |

---

**总结：** 本质就是一个 Python 脚本项目，核心三步：`pip install -r requirements.txt` → 配置 `.env` → `python src/main.py`。如果没有其他问题，可以直接跑起来了！