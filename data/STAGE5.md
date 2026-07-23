# RAG（Retrieval-Augmented Generation）——让 Agent 能查文档、搜本地知识库回答问题。

## 原理
```
文档（PDF/TXT/MD）
    ↓  加载
文本
    ↓  切片（每段 500 字）
chunk1  chunk2  chunk3  ...
    ↓  向量化（embedding）
[0.1, 0.3, ...] [0.2, 0.5, ...] [0.8, 0.1, ...]
    ↓  存入
VectorStore（Chroma）
    ↓  用户提问 "xx 项目的部署方式？"
用户问题向量化 → 相似度搜索 → 找到最相关的 chunk
    ↓
拼入 Prompt → LLM 回答

```
## 步骤：
1. 安装依赖
```
pip install langchain-chroma langchain-community chromadb

```
