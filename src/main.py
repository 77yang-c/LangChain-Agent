"""
阶段1：第一条 LCEL 管道
chain = prompt | llm | output_parser
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_deepseek.chat_models import ChatDeepSeek
from langchain_openai import ChatOpenAI
from src.utlist.config import get_config

from langchain_core.prompts import ChatMessagePromptTemplate, MessagesPlaceholder
#1. prompt模板
prompt = ChatPromptTemplate.from_messages([
    ("system","你是一个有用的助手，请用中文回答，尽量简洁不啰嗦。"),
    MessagesPlaceholder(variable_name="messages")
])

#2 LLM
config = get_config()
llm = ChatOpenAI(
    model=config.model_name,
    openai_api_key=config.openai_api_key,
    base_url=config.base_url,
    temperature=config.temperature,
)

#3 输出解析器，将ai输出转化为字符串
parser = StrOutputParser()

#4 管道串联
chain = prompt | llm | parser

#5 运行
if __name__ == "__main__":

    #对话历史
    messages = []

    while True:
        user_input = input("you>")

        #把用户消息加入历史
        messages.append(("human",user_input))        

        if user_input.lower() in ("quit","exit","q"):
            print("再见")
            break


        print("Agent:>", end="", flush=True)
        full_response = ""

        for chunk in chain.stream({"messages":messages}):
            print(chunk, end="", flush=True)
            full_response += chunk
        print()

        #把ai回复加入历史
        messages.append(("assistant", full_response))