"""
阶段1：第一条 LCEL 管道
chain = prompt | llm | output_parser


阶段二：tool定义

阶段三： create_react_agent 一条龙
"""
from langgraph.checkpoint.memory import MemorySaver #导入记忆模块
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

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

agent = create_agent(
    model=llm,
    tools=ALL_TOOLS,
    checkpointer=memory,
    system_prompt="你是一个有用的助手，用中文回答，尽量简洁。"
)

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
           if hasattr(chunk, "content") and chunk.content:
               print(chunk.content, end="", flush=True)
        print()