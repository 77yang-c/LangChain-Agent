"""企业知识库客服--FastAPI服务端"""

import json
import secrets
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, RedirectResponse
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
from src.models.user import upsert_user, create_session, get_user_by_session
from src.auth.github_oauth import get_github_auth_url, exchange_code_for_token, get_github_user, get_github_user_email
from src.models.conversation import save_message, get_conversations, get_messages

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

# ========= 认证相关 =========

# 存储 state 用于 CSRF 防护（生产环境应使用 Redis）
oauth_states = {}

@app.get("/api/auth/github")
async def github_login():
    """发起 GitHub OAuth 登录"""
    state = secrets.token_urlsafe(16)
    oauth_states[state] = True  # 简单存储，生产环境应设置过期时间
    
    auth_url = get_github_auth_url(state)
    return {"auth_url": auth_url}


@app.get("/api/auth/github/callback")
async def github_callback(code: str, state: str):
    """GitHub OAuth 回调"""
    # 验证 state
    if state not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state")
    
    del oauth_states[state]
    
    # 用 code 换取 access_token
    access_token = await exchange_code_for_token(code)
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to get access token")
    
    # 获取用户信息
    user_info = await get_github_user(access_token)
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to get user info")
    
    # 获取邮箱（可能为空）
    email = user_info.get("email")
    if not email:
        email = await get_github_user_email(access_token)
    
    # 存储用户信息
    user_id = upsert_user(
        github_id=user_info["id"],
        username=user_info["login"],
        avatar_url=user_info.get("avatar_url", ""),
        email=email,
        access_token=access_token,
    )
    
    # 创建会话
    session_id = create_session(user_id)
    
    # 重定向到前端，带上 session_id
    # 生产环境应该使用 httpOnly cookie
    frontend_url = f"/?session={session_id}"
    return RedirectResponse(url=frontend_url)


@app.get("/api/auth/me")
async def get_current_user(request: Request):
    """获取当前登录用户信息"""
    session_id = request.headers.get("X-Session-Id") or request.query_params.get("session")
    
    if not session_id:
        return {"logged_in": False, "user": None}
    
    user = get_user_by_session(session_id)
    if not user:
        return {"logged_in": False, "user": None}
    
    return {
        "logged_in": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "avatar_url": user["avatar_url"],
            "email": user["email"],
        }
    }


@app.post("/api/auth/logout")
async def logout(request: Request):
    """登出"""
    return {"status": "ok"}


def _get_user(request: Request):
    """从请求中获取当前用户，未登录返回 None"""
    sid = request.headers.get("X-Session-Id") or request.query_params.get("session")
    if not sid:
        return None
    return get_user_by_session(sid)


# ========= 对话历史 API =========

@app.get("/api/conversations")
async def list_conversations(request: Request):
    """获取当前用户的对话列表"""
    user = _get_user(request)
    if not user:
        return {"conversations": []}
    convs = get_conversations(user["id"])
    for c in convs:
        c["title"] = c["title"] or "未命名对话"
    return {"conversations": convs}


@app.get("/api/conversations/{thread_id}")
async def get_conversation_messages(thread_id: str, request: Request):
    """获取某个对话的消息历史"""
    user = _get_user(request)
    if not user:
        return {"messages": []}
    msgs = get_messages(user["id"], thread_id)
    return {"messages": msgs}


# ========= 聊天接口 =========

#api
@app.post("/api/chat")
async def chat(request: Request):
    """流式聊天接口（SSE）"""
    data = await request.json()
    user_input = data.get("message", "")
    thread_id = data.get("thread_id", "default")
    user = _get_user(request)

    thread = {"configurable": {"thread_id": thread_id}}

    # 保存用户消息
    if user:
        save_message(user["id"], thread_id, "human", user_input)

    async def stream():
        ai_text = ""
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
                        ai_text += chunk.content
                        yield f"data: {json.dumps({'text': chunk.content}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

        # 保存 AI 回复
        if user and ai_text:
            save_message(user["id"], thread_id, "ai", ai_text)

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
