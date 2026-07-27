"""RAG 工具：从 SQLite 加载文档 -> 切片 -> API 向量化 -> 检索"""

from pathlib import Path
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_core.tools import tool
from langchain_core.documents import Document
from src.utlist.config import get_config
from src.models.documents import get_all_contents

_retriever = None


def _get_embeddings():
    config = get_config()
    return OpenAIEmbeddings(
        model=config.embedding_model,
        api_key=config.embedding_api_key or config.openai_api_key,
        base_url=config.embedding_base_url or config.base_url,
    )


def init_retriever(force_rebuild: bool = False):
    """从 SQLite 加载文档，构建向量索引"""
    global _retriever

    chroma_dir = Path("user_data") / "chroma_db"

    if chroma_dir.exists() and not force_rebuild:
        try:
            vec = Chroma(
                persist_directory=str(chroma_dir),
                embedding_function=_get_embeddings(),
            )
            _retriever = vec.as_retriever(search_kwargs={"k": 3})
            count = vec._collection.count()
            return f"从缓存加载，共 {count} 个文档片段"
        except:
            pass

    # 从数据库读取所有文档
    rows = get_all_contents()
    if not rows:
        _retriever = None
        return "未找到文档，请先上传"

    # 转为 langchain Document
    docs = []
    for r in rows:
        docs.append(Document(page_content=r["content"], metadata={"source": r["filename"]}))

    sp = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = sp.split_documents(docs)

    vec = Chroma.from_documents(
        chunks,
        _get_embeddings(),
        persist_directory=str(chroma_dir),
    )
    _retriever = vec.as_retriever(search_kwargs={"k": 3})
    return f"已索引 {len(chunks)} 个文档片段"


@tool
def search_docs(query: str) -> str:
    """搜索本地文档库，查找与问题相关的内容。"""
    global _retriever

    if _retriever is None:
        result = init_retriever()
        if _retriever is None:
            return result

    docs = _retriever.invoke(query)

    if not docs:
        return "未找到相关内容"

    results = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "未知")
        results.append(f"[{i}] 来源：{source}\n{doc.page_content}")

    return "\n\n---\n\n".join(results)
