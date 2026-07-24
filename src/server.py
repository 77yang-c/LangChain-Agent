"""企业知识库客服--FastAPI服务端"""

import json
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, AIMessageChunk

from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, AIMessageChunk

from src.utlist.config import get_config
from src.tools.tools import ALL_TOOLS
from src.tools.rag import init_retriever

#Fast--API
app = FastAPI(title="知识库客服")

# Agent复用
#1 LLM 
config = get_config()
llm = ChatOpenAI(
    model=config.model_name,
    api_key=config.openai_api_key,
    base_url=config.base_url,
    temperature=config.temperature,
    streaming=True,
)

#Memory（跨轮记忆，thread_id隔离不同的用户）
memory = MemorySaver()

agent = create_agent(
    model=llm,
    tools=ALL_TOOLS,
    checkpointer=memory,
    system_prompt = """你是企业知识库客服助手。根据文档库内容回答用户问题。

规则：
- 优先使用 search_docs 搜索本地知识库
- 知识库没有的内容，诚实说不知道
- 用中文回复，简洁专业
"""
,
)

#api
@app.post("/api/chat")
async def chat(request: Request):
    """流式聊天接口（SSE）"""
    data = await request.json()
    user_input = data.get("message","")
    thread_id = data.get("thread_id","default")

    thread = {"configurable":{"thread_id":thread_id}}

    async def stream():
        try:
            for chunk, _ in agent.stream(
                {"messages": [("human", user_input)]},
                config=thread,
                stream_mode="messages",
            ):
                if isinstance(chunk, (AIMessage, AIMessageChunk)):
                    if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                        for tc in chunk.tool_calls:
                            if tc.get("name"):
                                yield f"data: {json.dumps({'tool': tc['name']}, ensure_ascii=False)}\n\n"

                    if chunk.content:
                        yield f"data: {json.dumps({'text': chunk.content}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# --- 知识库管理 ---

@app.get("/api/kb/status")
async def kb_status():
    """查看知识库状态"""
    files = [str(f) for f in Path("data").rglob("*.*")
             if f.suffix in (".txt", ".md") and "chroma_db" not in str(f)]
    return {
        "files": files,
        "file_count": len(files),
        "has_index": Path("data/chroma_db").exists(),
    }


@app.post("/api/kb/rebuild")
async def kb_rebuild():
    """手动重建知识库索引"""
    result = init_retriever(force_rebuild=True)
    return {"status": "ok", "message": result}


@app.post("/api/kb/upload")
async def kb_upload(file: UploadFile = File(...)):
    """上传文档到知识库"""
    content = await file.read()
    save_path = Path("data") / file.filename
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(content)
    return {"status": "ok", "filename": file.filename}


app.mount("/", StaticFiles(directory="static", html=True),name = "static")
import uvicorn
if __name__ == "__main__" :
    uvicorn.run(app, host="0.0.0.0", port=8000)
    print("已关闭")

                        