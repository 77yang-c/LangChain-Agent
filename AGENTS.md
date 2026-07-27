# 企业知识库客服 Agent

## 项目概述

基于 LangChain / LangGraph 框架构建的智能知识库客服系统。支持文档 RAG 检索、流式对话、多轮记忆、GitHub OAuth 登录，提供类 ChatGPT 的 Web 对话界面。

**在线地址**：`https://smtp-pot-name-barcelona.trycloudflare.com`

## 技术栈

| 层 | 技术 |
|------|------|
| Agent 框架 | LangChain + LangGraph（`create_agent`） |
| Web 服务 | FastAPI + Uvicorn（SSE 流式） |
| LLM | DeepSeek（`deepseek-v4-pro`），OpenAI 兼容协议 |
| Embedding | 智谱 GLM（`embedding-3`），API 调用，不下载模型 |
| 向量库 | ChromaDB（本地持久化） |
| 文档存储 | SQLite（`user_data/users.db`） |
| 用户认证 | GitHub OAuth + httpOnly Cookie |
| 前端 | 原生 HTML/CSS/JS（零框架） |
| 部署 | VPS + Cloudflare Tunnel（HTTPS） |

## 目录结构

```
langchain-agent/
├── src/
│   ├── server.py              # FastAPI Web 服务主入口
│   ├── main.py                # 命令行版 Agent（学习用）
│   ├── agent/agent.py         # Agent 封装（预留）
│   ├── prompt/prompt.py       # 提示词模板（预留）
│   ├── memory/memory.py       # 记忆模块（预留）
│   ├── tools/
│   │   ├── tools.py           # 工具定义：时间、文件读写
│   │   └── rag.py             # RAG：SQLite 加载 → 切片 → API 向量化 → ChromaDB
│   ├── models/
│   │   ├── user.py            # 用户 + 会话表
│   │   ├── conversation.py    # 对话历史 + 消息表
│   │   └── documents.py       # 知识库文档表
│   ├── auth/github_oauth.py   # GitHub OAuth
│   └── utlist/config.py       # .env 配置加载（主模型 + Embedding 分离）
├── static/index.html          # Web 前端（含登录、侧边栏、Markdown 渲染）
├── user_data/                 # 持久化数据（.gitignore）
│   ├── users.db               # SQLite（user, session, conversation, message, document）
│   └── chroma_db/             # ChromaDB 向量缓存
├── STAGE1~5.md                # 学习笔记
├── requirements.txt
├── .env                       # 环境变量（不提交）
└── .gitignore
```

## API 接口

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| `GET` | `/api/health` | 健康检查 | 无 |
| `GET` | `/api/auth/github` | GitHub OAuth 入口 | 无 |
| `GET` | `/api/auth/github/callback` | OAuth 回调 | 无 |
| `GET` | `/api/auth/me` | 当前用户信息 | Cookie |
| `POST` | `/api/auth/logout` | 登出 | Cookie |
| `GET` | `/api/conversations` | 对话列表 | Cookie |
| `GET` | `/api/conversations/{id}` | 对话消息 | Cookie |
| `POST` | `/api/chat` | 流式聊天（SSE） | Cookie + 限流 |
| `GET` | `/api/kb/status` | 知识库状态 | Cookie |
| `POST` | `/api/kb/upload` | 上传文档 | Cookie |
| `POST` | `/api/kb/rebuild` | 重建向量索引 | Cookie |
| `DELETE` | `/api/kb/files/{name}` | 删除文档 | Cookie |

## 上线安全加固

1. session → httpOnly Cookie（防 XSS）
2. 聊天/上传接口强制鉴权（未登录 401）
3. 文件上传限制：类型白名单 + 5MB 上限 + 防路径穿越
4. 频率限制：每用户每分钟最多 10 次聊天
5. 请求日志：stdout + server.log 双写

## 部署步骤

### 1. VPS 环境

```bash
sudo apt update && sudo apt install -y python3 python3-pip git
git clone https://github.com/77yang-c/LangChain-Agent.git
cd LangChain-Agent
pip install -r requirements.txt
```

### 2. 配置

```bash
cat > .env << 'EOF'
MODEL_NAME=deepseek-v4-pro
OPENAI_API_KEY=sk-xxx
BASE_URL=https://api.deepseek.com
EMBEDDING_MODEL=embedding-3
EMBEDDING_API_KEY=xxx
EMBEDDING_BASE_URL=https://open.bigmodel.cn/api/paas/v4
GITHUB_CLIENT_ID=xxx
GITHUB_CLIENT_SECRET=xxx
GITHUB_REDIRECT_URI=https://xxx.trycloudflare.com/api/auth/github/callback
EOF
```

### 3. 启动

```bash
nohup python3 -m src.server &
```

### 4. 内网穿透（HTTPS 免备案）

```bash
wget https://gh.idayer.com/https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O cloudflared
chmod +x cloudflared
nohup ./cloudflared tunnel --url http://localhost:8000 > tunnel.log 2>&1 &
```

### 5. 更新 GitHub OAuth

https://github.com/settings/developers → Callback URL 改为 Cloudflare 域名

## 使用流程

```
上传 .txt/.md 文档 → 点「重建索引」→ 开始提问
```

- 上传文档存 SQLite，不受 Git 部署影响
- 重建索引调用 Embedding API 向量化，缓存到 ChromaDB
- 对话历史持久化，切换会话可恢复

## 已知限制

- 免费 Cloudflare Tunnel 每次重启域名会变
- MemorySaver 重启丢失 Agent 上下文（对话记录仍在）
- 关键词匹配精度不如向量检索（但零费用方案够用）
