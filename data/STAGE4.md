# 阶段4：Memory 记忆持久化

## 一、为什么需要 Memory

没有 Memory 时，每轮对话是独立的，LLM 记不住之前说过什么：

```
第1轮：我叫小明
     → Agent：你好小明
第2轮：我叫什么？
     → Agent：我不知道你叫什么  ❌
```

加了 Memory 后，Agent 自动记住历史。

## 二、MemorySaver vs SqliteSaver

| | MemorySaver | SqliteSaver |
|------|------|------|
| 存储位置 | 内存 | 磁盘 SQLite 文件 |
| 持久化 | 进程退出即丢失 | 永久保存 |
| 速度 | 快 | 稍慢 |
| 场景 | 开发 / 测试 | 生产环境 |

```python
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()   # 开发用

# from langgraph.checkpoint.sqlite import SqliteSaver
# memory = SqliteSaver(sqlite3.connect("data/agent_memory.db"))   # 生产用
```

## 三、thread_id 用户隔离

同一个 Agent 服务多用户时，靠 `thread_id` 区分各自记忆：

```python
# 用户 A
{"configurable": {"thread_id": "user-alice"}}

# 用户 B
{"configurable": {"thread_id": "user-bob"}}
```

不同 `thread_id` 的记忆完全隔离，互不干扰。

## 四、工作原理

```
agent.invoke(消息, config={thread_id: "user-1"})
    ↓
LangGraph 从 checkpointer 查找 thread_id="user-1" 的历史状态
    ↓
拼上历史消息 → LLM 推理 → 工具执行
    ↓
本轮结束 → checkpointer 保存新状态到 thread_id="user-1"
```

## 五、传递给 create_agent

```python
agent = create_agent(
    model=llm,
    tools=ALL_TOOLS,
    checkpointer=MemorySaver(),    # ★ 这里
    system_prompt="...",
)
```

`create_agent` 内部把 checkpointer 接入 LangGraph 的状态管理系统，调用时自动存取。

## 六、验证 Memory 是否生效

```
you>> 我叫小明
Agent> 你好小明！

you>> 我刚才说我叫什么
Agent> 你说你叫小明。  ✅ 记住了
```

## 七、完整对比

| | 阶段1 Chain | 阶段2 手动工具 | 阶段3 Agent | 阶段4 Agent+Memory |
|------|------|------|------|------|
| 多轮对话 | 手动管理 messages | 手动管理 messages | 手动传 thread | 自动 |
| 工具调用 | ❌ | 手动 while | 自动 | 自动 |
| 记忆持久化 | ❌ | ❌ | ❌ | ✅ |
| 多用户隔离 | ❌ | ❌ | ❌ | ✅ thread_id |
