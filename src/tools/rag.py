"""RAG 工具：按用户从 SQLite 加载文档 -> 切片 -> API 向量化 -> 检索"""

import logging
import shutil
from contextvars import ContextVar
from pathlib import Path

from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_core.tools import tool
from langchain_core.documents import Document
from src.utlist.config import get_config
from src.models.documents import get_all_contents

logger = logging.getLogger(__name__)

# 当前请求的知识库用户（由 chat / kb API 注入）
_kb_user_id: ContextVar[int | None] = ContextVar("kb_user_id", default=None)
_retrievers: dict[int, object] = {}


def set_kb_user(user_id: int):
    """设置当前请求的知识库用户，返回 token 供 reset"""
    return _kb_user_id.set(user_id)


def reset_kb_user(token) -> None:
    _kb_user_id.reset(token)


def _chroma_dir(user_id: int) -> Path:
    return Path("user_data") / "chroma_db" / f"user_{user_id}"


def _get_embeddings():
    config = get_config()
    return OpenAIEmbeddings(
        model=config.embedding_model,
        api_key=config.embedding_api_key or config.openai_api_key,
        base_url=config.embedding_base_url or config.base_url,
    )


def clear_user_index(user_id: int) -> None:
    """删除用户向量缓存并清掉内存中的 retriever"""
    _retrievers.pop(user_id, None)
    chroma_dir = _chroma_dir(user_id)
    if chroma_dir.exists():
        shutil.rmtree(chroma_dir, ignore_errors=True)


def init_retriever(user_id: int, force_rebuild: bool = False) -> str:
    """从 SQLite 加载该用户文档，构建向量索引"""
    chroma_dir = _chroma_dir(user_id)

    if force_rebuild:
        clear_user_index(user_id)

    if chroma_dir.exists() and not force_rebuild:
        try:
            vec = Chroma(
                persist_directory=str(chroma_dir),
                embedding_function=_get_embeddings(),
            )
            _retrievers[user_id] = vec.as_retriever(search_kwargs={"k": 10})
            count = vec._collection.count()
            return f"从缓存加载，共 {count} 个文档片段"
        except Exception as e:
            logger.warning(f"加载用户 {user_id} 向量缓存失败: {e}")
            clear_user_index(user_id)

    rows = get_all_contents(user_id)
    if not rows:
        _retrievers.pop(user_id, None)
        return "未找到文档，请先上传"

    docs = [
        Document(page_content=r["content"], metadata={"source": r["filename"]})
        for r in rows
    ]

    sp = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = sp.split_documents(docs)

    chroma_dir.parent.mkdir(parents=True, exist_ok=True)
    vec = Chroma.from_documents(
        chunks,
        _get_embeddings(),
        persist_directory=str(chroma_dir),
    )
    _retrievers[user_id] = vec.as_retriever(search_kwargs={"k": 10})
    return f"已索引 {len(chunks)} 个文档片段"


def has_user_index(user_id: int) -> bool:
    return _chroma_dir(user_id).exists()


@tool
def search_docs(query: str) -> str:
    """搜索本地文档库，查找与问题相关的内容。"""
    user_id = _kb_user_id.get()
    if user_id is None:
        return "未登录，无法搜索知识库"

    if user_id not in _retrievers:
        result = init_retriever(user_id)
        if user_id not in _retrievers:
            return result

    docs = _retrievers[user_id].invoke(query)

    if not docs:
        return "未找到相关内容"

    seen = set()
    results = []
    for doc in docs:
        source = doc.metadata.get("source", "未知")
        if source in seen:
            continue
        seen.add(source)
        results.append(f"[{len(results)+1}] 来源：{source}\n{doc.page_content}")
        if len(results) >= 3:
            break

    return "\n\n---\n\n".join(results)
