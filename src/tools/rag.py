"""RAG工具：文档加载->切片->向量化->检索"""

from pathlib import Path
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_community.embeddings import HuggingFaceEmbeddings

from langchain_core.tools import tool

_retriever = None

def init_retriever(docs_dir : str = "data"):
    """初始化文档检索引擎，扫描 data/ 目录下所有 .txt .md 文件"""
    global _retriever

    embeddings = HuggingFaceEmbeddings(
    model_name="shibing624/text2vec-base-chinese",   # 中文，本地运行，免费
    )


    #加载所有文件
    doc = []
    for ext in ("*.txt", "*.md"):
        for f in Path(docs_dir).rglob(ext):
            loader = TextLoader(str(f), encoding= "utf-8")
            doc.extend(loader.load())

    if not doc:
        _retriever = None
        return "no file in data"

    #切片
    sp = RecursiveCharacterTextSplitter(
        chunk_size = 500,
        chunk_overlap = 50
    )
    chunks = sp.split_documents(doc)

    #向量化+存储
    vec = Chroma.from_documents(
        chunks,
        embeddings,
        persist_directory="data/chroma_db",
    )
    _retriever = vec.as_retriever(search_kwargs = {"k":3})
    return f"已索引 {len(chunks)} 个文档片段"




@tool
def search_docs(query: str) -> str :
    """搜索本地文档库，查找与问题相关的内容。query 为搜索关键词或问题。"""
    global _retriever
    if _retriever is None:
        init_retriever()
        if _retriever is None:
            return "文档库为空，请先在 data/ 目录下放入文档。"

    docs = _retriever.invoke(query)

    if not docs:
        return "未找到相关内容"

    #拼接结果检查
    results = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "未知")
        results.append(f"[{i}]来源：{source}\n{doc.page_content}")
    return "\n\n---\n\n".join(results)
