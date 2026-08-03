"""企业知识库客服--FastAPI服务端"""

import json
import os
import time
import secrets
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("server.log", encoding="utf-8")],
)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, AIMessageChunk

from src.utlist.config import get_config
from src.tools.tools import SAFE_TOOLS
from src.tools.rag import init_retriever, set_kb_user, reset_kb_user, has_user_index, clear_user_index
from src.models.user import upsert_user, create_session, get_user_by_session
from src.auth.github_oauth import get_github_auth_url, exchange_code_for_token, get_github_user, get_github_user_email
from src.models.conversation import save_message, get_conversations, get_messages
from src.models.documents import save_document, delete_document, get_documents
from src.models.security import save_oauth_state, consume_oauth_state, check_rate_limit

app = FastAPI(title="知识库客服")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


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
    tools=SAFE_TOOLS,
    checkpointer=memory,
    system_prompt="""你是企业知识库客服助手。根据文档库内容回答用户问题。

规则：
- 优先使用 search_docs 搜索本地知识库
- 先搜索知识库再回答，找不到就说未找到
- 只能通过 search_docs 检索知识库，不能读写任意文件
- 知识库没有的内容，诚实说不知道
- 用中文回复，简洁专业，200 字左右
""",
)


def _require_user(request: Request) -> dict:
    user = _get_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def _get_user(request: Request):
    """从 httpOnly cookie 中获取当前用户"""
    sid = request.cookies.get("session_id")
    if not sid:
        return None
    return get_user_by_session(sid)


def _agent_thread_id(user_id: int, thread_id: str) -> str:
    """Agent checkpointer 的 thread 必须带用户前缀，防止跨用户串会话"""
    return f"u{user_id}:{thread_id}"


def _safe_filename(name: str | None) -> str | None:
    if not name:
        return None
    base = Path(name).name
    if not base or base in (".", ".."):
        return None
    return base


def _set_session_cookie(response, session_id: str) -> None:
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=config.cookie_secure,
        samesite="lax",
        max_age=7 * 24 * 3600,
    )


def _clear_session_cookie(response) -> None:
    response.delete_cookie(
        key="session_id",
        httponly=True,
        secure=config.cookie_secure,
        samesite="lax",
    )


# ========= 认证相关 =========

@app.get("/api/auth/github")
async def github_login():
    """发起 GitHub OAuth 登录"""
    state = secrets.token_urlsafe(16)
    save_oauth_state(state)
    return {"auth_url": get_github_auth_url(state)}


@app.get("/api/auth/github/callback")
async def github_callback(code: str, state: str):
    """GitHub OAuth 回调"""
    if not consume_oauth_state(state):
        raise HTTPException(status_code=400, detail="Invalid state")

    access_token = await exchange_code_for_token(code)
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to get access token")

    user_info = await get_github_user(access_token)
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to get user info")

    email = user_info.get("email")
    if not email:
        email = await get_github_user_email(access_token)

    user_id = upsert_user(
        github_id=user_info["id"],
        username=user_info["login"],
        avatar_url=user_info.get("avatar_url", ""),
        email=email,
        access_token=access_token,
    )

    session_id = create_session(user_id)
    response = RedirectResponse(url="/")
    _set_session_cookie(response, session_id)
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
        },
    }


@app.post("/api/auth/logout")
async def logout(request: Request):
    """退出"""
    response = JSONResponse({"status": "ok"})
    _clear_session_cookie(response)
    return response


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
    user = _require_user(request)
    convs = get_conversations(user["id"])
    for c in convs:
        c["title"] = c["title"] or "未命名对话"
    return {"conversations": convs}


@app.get("/api/conversations/{thread_id}")
async def get_conversation_messages(thread_id: str, request: Request):
    """获取某个对话的消息历史（仅本人）"""
    user = _require_user(request)
    msgs = get_messages(user["id"], thread_id)
    return {"messages": msgs}


# ========= 聊天接口 =========

@app.post("/api/chat")
async def chat(request: Request):
    """流式聊天接口（SSE）"""
    user = _require_user(request)

    if not check_rate_limit(user["id"]):
        return JSONResponse({"error": "请求太频繁，请稍后再试"}, status_code=429)

    data = await request.json()
    user_input = data.get("message", "")
    thread_id = data.get("thread_id", "default")
    if not isinstance(user_input, str) or not user_input.strip():
        return JSONResponse({"error": "消息不能为空"}, status_code=400)
    if not isinstance(thread_id, str) or not thread_id.strip() or len(thread_id) > 128:
        return JSONResponse({"error": "无效的会话 ID"}, status_code=400)

    agent_cfg = {
        "configurable": {"thread_id": _agent_thread_id(user["id"], thread_id)},
        "recursion_limit": 15,
    }

    save_message(user["id"], thread_id, "human", user_input)

    async def stream():
        ai_text = ""
        errored = False
        token = set_kb_user(user["id"])
        try:
            for chunk, _ in agent.stream(
                {"messages": [("human", user_input)]},
                config=agent_cfg,
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
            errored = True
            logger.warning(f"Agent error: {e}")
            yield f"data: {json.dumps({'error': '请求太复杂，请简化问题后重试'}, ensure_ascii=False)}\n\n"
        finally:
            reset_kb_user(token)

        if ai_text and not errored:
            save_message(user["id"], thread_id, "ai", ai_text)

        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# --- 知识库管理（按用户隔离）---

ALLOWED_EXT = {".txt", ".md", ".csv", ".json"}
MAX_SIZE_MB = 5


@app.get("/api/kb/status")
async def kb_status(request: Request):
    """查看当前用户的知识库状态"""
    user = _require_user(request)
    docs = get_documents(user["id"])
    return {
        "files": [d["filename"] for d in docs],
        "file_count": len(docs),
        "has_index": has_user_index(user["id"]),
    }


@app.post("/api/kb/rebuild")
async def kb_rebuild(request: Request):
    """手动重建当前用户的知识库索引"""
    user = _require_user(request)
    result = init_retriever(user["id"], force_rebuild=True)
    return {"status": "ok", "message": result}


@app.post("/api/kb/upload")
async def kb_upload(request: Request, file: UploadFile = File(...)):
    """上传文档到当前用户知识库"""
    user = _require_user(request)

    filename = _safe_filename(file.filename)
    if not filename:
        return JSONResponse({"error": "无效的文件名"}, status_code=400)

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        return JSONResponse({"error": f"不支持的文件类型：{ext}"}, status_code=400)

    content = await file.read()
    if len(content) > MAX_SIZE_MB * 1024 * 1024:
        return JSONResponse({"error": f"文件过大，最大 {MAX_SIZE_MB}MB"}, status_code=400)

    text = content.decode("utf-8", errors="replace")
    save_document(user["id"], filename, text)
    # 文档变更后旧索引失效
    clear_user_index(user["id"])
    return {"status": "ok", "filename": filename}


@app.delete("/api/kb/files/{filename}")
async def kb_delete(filename: str, request: Request):
    """删除当前用户知识库文档"""
    user = _require_user(request)
    safe = _safe_filename(filename)
    if not safe:
        return JSONResponse({"error": "无效的文件名"}, status_code=400)

    if not delete_document(user["id"], safe):
        return JSONResponse({"error": "文件不存在"}, status_code=404)

    clear_user_index(user["id"])
    return {"status": "ok", "deleted": safe}


app.mount("/", StaticFiles(directory="static", html=True), name="static")

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
