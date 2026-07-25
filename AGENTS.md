# 企业知识库客服 Agent

## 项目概述

基于 LangChain/LangGraph 架构的企业知识库客服系统。支持 RAG 文档检索、多轮对话、流式输出，提供 Web 界面供用户交互。

核心功能：
- 企业文档知识库管理（支持 .txt/.md 文件）
- 基于 RAG 的智能问答
- 流式对话输出（SSE）
- 多工具调用（文件读写、网页抓取、时间查询等）
- GitHub OAuth 登录认证

## 技术栈

- **后端**：Python 3 + FastAPI
- **Agent 框架**：LangChain + LangGraph
- **向量数据库**：ChromaDB
- **Embedding 模型**：shibing624/text2vec-base-chinese（HuggingFace）
- **LLM**：OpenAI 兼容接口（通过 .env 配置）
- **前端**：原生 HTML/CSS/JavaScript
- **包管理**：uv（Python）、pip（requirements.txt）

## 目录结构

```
/workspace/projects/
├── src/
│   ├── main.py              # 命令行版本入口
│   ├── server.py            # FastAPI Web 服务入口
│   ├── agent/               # Agent 模块（待扩展）
│   ├── memory/              # 记忆模块（待扩展）
│   ├── prompts/             # 提示词模块（待扩展）
│   ├── tools/
│   │   ├── tools.py         # 工具定义（时间、文件读写、网页抓取）
│   │   └── rag.py           # RAG 工具（文档加载、切片、向量化、检索）
│   ├── models/
│   │   └── user.py          # 用户数据库模型
│   ├── auth/
│   │   └── github_oauth.py  # GitHub OAuth 认证
│   └── utlist/
│       └── config.py        # 配置加载（.env）
├── static/
│   └── index.html           # 前端页面（含登录）
├── data/                    # 知识库文档目录
│   ├── *.txt, *.md          # 文档文件
│   └── chroma_db/           # ChromaDB 向量索引缓存
├── user_data/               # 用户数据（已加入 .gitignore）
│   └── users.db             # SQLite 用户数据库
├── test/                    # 测试目录
├── requirements.txt         # Python 依赖
└── .env                     # 环境变量配置（需自行创建）
```

## 关键入口 / 核心模块

### 入口文件
- **Web 服务**：`src/server.py` - FastAPI 应用，提供 `/api/chat`（流式聊天）、`/api/kb/status`（知识库状态）等接口
- **命令行**：`src/main.py` - 交互式命令行版本

### 核心模块
- **Agent 创建**：`src/server.py` 中的 `create_agent()` 调用
- **工具集**：`src/tools/tools.py` - 定义 ALL_TOOLS 列表
- **RAG 检索**：`src/tools/rag.py` - 文档向量化与检索逻辑
- **配置管理**：`src/utlist/config.py` - 从 .env 加载 LLM 配置

### API 接口
- `POST /api/chat` - 流式聊天（SSE）
- `GET /api/kb/status` - 知识库状态查询
- `POST /api/kb/upload` - 上传文档
- `POST /api/kb/rebuild` - 重建索引
- `GET /api/auth/github` - 发起 GitHub OAuth 登录
- `GET /api/auth/github/callback` - GitHub OAuth 回调
- `GET /api/auth/me` - 获取当前登录用户信息
- `POST /api/auth/logout` - 登出
- `GET /` - 前端页面

## 运行与预览

### 环境配置
1. 创建 `.env` 文件，配置以下变量：
   ```
   MODEL_NAME=your-model-name
   OPENAI_API_KEY=your-api-key
   BASE_URL=your-base-url
   TEMPERATURE=0.0
   
   # GitHub OAuth 配置
   GITHUB_CLIENT_ID=your-github-client-id
   GITHUB_CLIENT_SECRET=your-github-client-secret
   GITHUB_REDIRECT_URI=http://localhost:5000/api/auth/github/callback
   ```

2. 安装依赖：
   ```bash
   uv pip install -r requirements.txt
   ```

3. 准备知识库文档：
   - 将 .txt 或 .md 文件放入 `data/` 目录

### GitHub OAuth 配置
1. 前往 [GitHub Developer Settings](https://github.com/settings/developers)
2. 点击 "New OAuth App" 创建应用
3. 填写应用信息：
   - Application name: 你的应用名称
   - Homepage URL: http://localhost:5000
   - Authorization callback URL: http://localhost:5000/api/auth/github/callback
4. 创建后获取 Client ID 和 Client Secret，填入 `.env` 文件

### 启动服务
```bash
# 使用 uvicorn 启动 FastAPI 服务
uvicorn src.server:app --host 0.0.0.0 --port 5000
```

### 预览
- 访问前端页面即可使用知识库客服功能
- 支持上传文档、重建索引、多轮对话

## 预览与部署配置

### 预览链路
- **项目类型**：web（有前端界面 + 后端服务）
- **预览入口**：`scripts/coze-preview-run.sh`
- **构建脚本**：`scripts/coze-preview-build.sh`
- **运行脚本**：`scripts/coze-preview-run.sh`
- **端口**：5000
- **绑定地址**：0.0.0.0

### 部署配置
- **部署类型**：service（HTTP 服务）
- **部署表面**：web
- **构建脚本**：`scripts/setup.sh`（安装依赖）
- **运行脚本**：`scripts/http_run.sh -p 5000`（启动服务）
- **运行时**：python-3.12

### 脚本说明
- 预览脚本和部署脚本均基于脚本位置推导项目根目录（`SCRIPT_DIR` → `PROJECT_DIR`）
- 运行脚本具备幂等性：每次执行先清理 5000 端口残留进程
- 所有脚本使用 `set -Eeuo pipefail` 确保错误处理

## 用户偏好与长期约束

- 使用中文进行所有交互
- Python 项目使用 uv 管理虚拟环境和依赖
- 前端保持原生 HTML/CSS/JS，不引入框架
- LLM 集成默认使用流式返回
- 知识库文档支持 .txt 和 .md 格式

## 常见问题和预防

### 1. HuggingFace 模型下载失败
- 已配置镜像源：`HF_ENDPOINT=https://hf-mirror.com`
- 已启用离线模式：`HF_HUB_OFFLINE=1`
- 首次运行需要下载 embedding 模型，确保网络畅通

### 2. ChromaDB 索引问题
- 索引缓存在 `data/chroma_db/` 目录
- 如索引损坏，可通过前端「重建索引」功能或调用 `/api/kb/rebuild` 接口重建

### 3. LLM 连接失败
- 检查 `.env` 文件中的 API_KEY 和 BASE_URL 是否正确
- 确认模型名称与服务商支持一致

### 4. Playwright 网页抓取
- web_tool_read 工具使用 Playwright，需要安装浏览器驱动
- 生产环境建议使用 headless 模式
