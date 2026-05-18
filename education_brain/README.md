# Education Brain - 教育知识库后端

基于 RAG 技术的企业级智能教育系统后端，提供课程/题库/文档导入、向量检索、智能问答等能力。

## 技术栈

- **框架**: FastAPI + Uvicorn
- **LLM**: OpenAI API（也支持本地 Ollama）
- **向量数据库**: Milvus + BGE-M3 嵌入模型
- **文档数据库**: MongoDB
- **对象存储**: MinIO（图片等静态资源）
- **Python**: 3.10 ~ 3.12

## Quick Start

### 1. 启动依赖服务

确保以下服务已运行：

| 服务 | 默认地址 | 用途 |
|------|---------|------|
| MongoDB | `localhost:27017` | 课程、题库、文档存储 |
| Milvus | `localhost:19530` | 向量检索 |
| MinIO | `localhost:9000` | 图片/文件存储 |

### 2. 安装 Python 依赖

```bash
cd education_brain/knowledge

# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -r requirements.txt
```

### 3. 配置环境变量

复制并编辑 `.env`：

```bash
cp .env.example .env   # 如有模板
# 或直接编辑 knowledge/.env
```

**关键配置项：**

```bash
# LLM — 二选一：

# 方式 A: OpenAI 官方 API（需在 shell 中 export OPENAI_API_KEY）
LLM_MODEL=gpt-4o-mini
ANSWER_MODEL=gpt-4o-mini

# 方式 B: 本地 Ollama
# OPENAI_BASE_URL=http://localhost:11434/v1
# OPENAI_API_KEY=ollama
# LLM_MODEL=deepseek-r1:14b
# ANSWER_MODEL=qwen3.5:latest
```

### 4. 准备数据文件

将教学资料放入 `data/数据/` 目录：

```
data/数据/
├── 课程介绍.md        # 课程目录（系列、模块信息）
├── 题目资料.md        # 题库（选择题、填空题等）
├── 课程文档/          # .docx 课程文档
│   ├── xxx技术之Python1.0.docx
│   └── ...
└── 项目文档/          # .docx / .md 项目文档
    └── ...
```

### 5. 启动服务

```bash
cd education_brain/knowledge
python main.py
```

服务启动于 `http://127.0.0.1:8000`，支持热重载。

### 6. 验证

```bash
# 健康检查
curl http://127.0.0.1:8000/health

# API 文档
open http://127.0.0.1:8000/docs
```

## API 概览

### 数据导入（异步，返回 task_id 轮询进度）

```
POST /ingest/catalog       # 导入课程目录
POST /ingest/questions     # 导入题库
POST /ingest/documents     # 导入文档（支持文件夹路径）
GET  /ingest/tasks/{id}    # 查询导入任务进度
GET  /ingest/browse        # 浏览服务器数据目录
```

### 检索

```
GET /search/courses        # 课程检索
GET /search/questions      # 题目检索
GET /search/documents      # 文档语义搜索
```

### 智能问答

```
POST /chat/query           # 提交问题
GET  /chat/stream/{id}     # SSE 流式获取回答
GET  /chat/history         # 获取对话历史
```

## 项目结构

```
knowledge/
├── api/routes/            # FastAPI 路由
│   ├── ingest.py          # 导入接口
│   ├── search.py          # 检索接口
│   └── chat.py            # 问答接口
├── core/
│   ├── config.py          # 配置管理（pydantic-settings）
│   ├── clients.py         # 外部服务客户端（MongoDB/Milvus/MinIO/OpenAI）
│   └── llm.py             # LLM 调用封装（同步 + 异步流式）
├── models/                # 数据模型
├── processor/             # 文档处理管道
│   ├── catalog_parser.py  # 课程目录解析
│   ├── question_parser.py # 题库解析
│   ├── docx_converter.py  # .docx → Markdown
│   ├── markdown_parser.py # Markdown 结构化
│   ├── chunker.py         # 智能分块
│   ├── embedder.py        # BGE-M3 向量化
│   └── milvus_store.py    # Milvus 写入
├── service/               # 业务服务
│   └── intent_classifier.py # 意图分类
├── main.py                # 入口
└── .env                   # 环境配置
```
