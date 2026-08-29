"""
阶段1：第一条 LCEL 管道
chain = prompt | llm | output_parser


阶段二：tool定义

阶段三： create_react_agent 一条龙
"""
import sys
from pathlib import Path

# 让 `python src/main.py` 直接运行也能解析 `src.*` 包导入（不依赖启动目录/PYTHONPATH）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.checkpoint.memory import MemorySaver #导入记忆模块
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, AIMessageChunk

from src.utlist.config import get_config
from src.tools.tools import ALL_TOOLS


#1 LLM 
config = get_config()
llm = ChatOpenAI(
    model=config.model_name,
    openai_api_key=config.openai_api_key,
    base_url=config.base_url,
    temperature=config.temperature,
)

#Memory（跨轮记忆，thread_id隔离不同的用户）
memory = MemorySaver()

agent = create_react_agent(
    model=llm,
    tools=ALL_TOOLS,
    checkpointer=memory,
    prompt = """你是一个智能助手，可以使用工具完成用户的任务。

## 工具使用原则

- 用户询问知识类问题、文档内容、项目相关问题时，优先使用 search_docs 搜索本地文档库
- 用户明确要求读取某个具体文件时，才使用 read_file
- 用户要打开网页、搜索互联网时，使用 web_tool_read
- 用户问时间时，使用 get_current_time
- 用户要创建或保存文件时，使用 write_file

## 规则

- 用中文回复
- 尽量简洁
- 工具参数要填完整，不要留空
"""
,
)

import signal
#运行
if __name__ == "__main__":
    thread = {"configurable":{"thread_id":"user-1"}}

    while True:
        user_input = input("you>>")
        if user_input.lower() in ("q","quit","exit"):
            print("再见")
            break

        #流式输出
        stream_model = "messages"
        for chunk,metadata in agent.stream(
            {"messages":[("human",user_input)]},
            config=thread,
            stream_mode="messages",
        ):
           if isinstance(chunk , (AIMessageChunk)):
               if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                   for tc in chunk.tool_calls:
                       if tc.get("name"):
                            print(f"正在调用工具：{tc['name']}")
                            print("\n")
           if isinstance(chunk, (AIMessage, AIMessageChunk)) and chunk.content:
               print(chunk.content, end="", flush=True)
        print("\n")