"""企业知识库客服--FastAPI服务端"""

import json
import os
import time
import secrets
import logging
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("server.log", encoding="utf-8")],
)
logger = logging.getLogger(__name__)
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse, RedirectResponse
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
from src.models.documents import save_document, delete_document, get_documents, get_all_contents

#Fast--API
app = FastAPI(title="知识库客服")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


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

# Agent 上下文（内存模式，对话历史已通过 conversations 表持久化）
memory = MemorySaver()

agent = create_agent(
    model=llm,
    tools=ALL_TOOLS,
    checkpointer=memory,
    system_prompt = """你是企业知识库客服助手。根据文档库内容回答用户问题。

规则：
- 优先使用 search_docs 搜索本地知识库
- 先搜索知识库再回答，找不到就说未找到
- 不能跳出知识库目录找文档，找不到就说暂时没有找到相关文档或内容
- 知识库没有的内容，诚实说不知道
- 用中文回复，简洁专业， 200 字左右
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
    
    # 设置 httpOnly cookie，前端 JS 不可访问，防 XSS
    response = RedirectResponse(url="/")
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=False,        # 本地开发用 False，上线改 True（HTTPS）
        samesite="lax",
        max_age=7 * 24 * 3600,  # 7 天
    )
    return response


@app.get("/api/auth/me")
async def get_current_user(request: Request):
    """获取当前登录用户信息"""
    user = _get_user(request)
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
    """退出"""
    response = JSONResponse({"status": "ok"})
    response.delete_cookie("session_id")
    return response


def _get_user(request: Request):
    """从 httpOnly cookie 中获取当前用户"""
    sid = request.cookies.get("session_id")
    if not sid:
        return None
    return get_user_by_session(sid)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = (time.time() - start) * 1000
    user = _get_user(request)
    who = user["username"] if user else "anonymous"
    logger.info(f"{request.method} {request.url.path} | {who} | {elapsed:.0f}ms")
    return response


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
# 简易限流：每用户每分钟最多 10 次请求
_rate_buckets = defaultdict(list)

def _check_rate(user_id: int, limit: int = 10, window: int = 60) -> bool:
    now = time.time()
    bucket = _rate_buckets[user_id]
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


@app.post("/api/chat")
async def chat(request: Request):
    """流式聊天接口（SSE）"""
    user = _get_user(request)
    if not user:
        return JSONResponse({"error": "请先登录"}, status_code=401)

    if not _check_rate(user["id"]):
        return JSONResponse({"error": "请求太频繁，请稍后再试"}, status_code=429)

    data = await request.json()
    user_input = data.get("message", "")
    thread_id = data.get("thread_id", "default")

    thread = {"configurable": {"thread_id": thread_id}, "recursion_limit": 15}

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
        if ai_text:
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
    docs = get_documents()
    return {
        "files": [d["filename"] for d in docs],
        "file_count": len(docs),
        "has_index": Path("user_data/chroma_db").exists(),
    }


@app.post("/api/kb/rebuild")
async def kb_rebuild(request: Request):
    """手动重建知识库索引"""
    if not _get_user(request):
        return JSONResponse({"error": "请先登录"}, status_code=401)
    result = init_retriever(force_rebuild=True)
    return {"status": "ok", "message": result}


ALLOWED_EXT = {".txt", ".md", ".csv", ".json"}
MAX_SIZE_MB = 5

@app.post("/api/kb/upload")
async def kb_upload(request: Request, file: UploadFile = File(...)):
    """上传文档到知识库（存 SQLite，不依赖文件系统）"""
    if not _get_user(request):
        return JSONResponse({"error": "请先登录"}, status_code=401)

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        return JSONResponse({"error": f"不支持的文件类型：{ext}"}, status_code=400)

    content = await file.read()
    if len(content) > MAX_SIZE_MB * 1024 * 1024:
        return JSONResponse({"error": f"文件过大，最大 {MAX_SIZE_MB}MB"}, status_code=400)

    text = content.decode("utf-8", errors="replace")
    save_document(file.filename, text)
    return {"status": "ok", "filename": file.filename}


@app.delete("/api/kb/files/{filename}")
async def kb_delete(filename: str, request: Request):
    """删除知识库文档"""
    if not _get_user(request):
        return JSONResponse({"error": "请先登录"}, status_code=401)
    delete_document(filename)
    return {"status": "ok", "deleted": filename}


app.mount("/", StaticFiles(directory="static", html=True),name = "static")
import uvicorn
if __name__ == "__main__" :
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
    print("已关闭")
