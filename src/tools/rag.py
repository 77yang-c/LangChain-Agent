"""RAG 工具：文档加载 -> 切片 -> 向量化 -> 检索（API 向量化）"""

from pathlib import Path
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_core.tools import tool
from src.utlist.config import get_config

_retriever = None


def _get_embeddings():
    """通过智谱 API 做向量化"""
    config = get_config()
    return OpenAIEmbeddings(
        model="embedding-3",
        api_key=config.openai_api_key,
        base_url=config.base_url,
    )


def init_retriever(docs_dir: str = "data", force_rebuild: bool = False):
    """初始化检索引擎，优先从 ChromaDB 缓存加载"""
    global _retriever

    chroma_dir = Path(docs_dir) / "chroma_db"

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

    doc = []
    for ext in ("*.txt", "*.md"):
        for f in Path(docs_dir).rglob(ext):
            if "chroma_db" in str(f):
                continue
            loader = TextLoader(str(f), encoding="utf-8")
            doc.extend(loader.load())

    if not doc:
        _retriever = None
        return "未找到文档"

    sp = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = sp.split_documents(doc)

    vec = Chroma.from_documents(
        chunks,
        _get_embeddings(),
        persist_directory=str(chroma_dir),
    )
    _retriever = vec.as_retriever(search_kwargs={"k": 3})
    return f"已索引 {len(chunks)} 个文档片段"


@tool
def search_docs(query: str) -> str:
    """搜索本地文档库，查找与问题相关的内容。query 为搜索关键词或问题。"""
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
