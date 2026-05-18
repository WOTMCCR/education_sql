# Education Brain - 教育知识库前端

教育知识库系统的 Web 前端，提供数据导入、课程/题库/文档检索、AI 智能问答等功能界面。

## 技术栈

- **框架**: React 18 + React Router 7
- **构建**: Vite 6
- **样式**: Tailwind CSS 4 + Radix UI + shadcn 组件
- **Node**: 18+

## Quick Start

### 1. 确保后端已运行

前端依赖后端 API，请先启动后端服务（默认 `http://127.0.0.1:8000`）。

### 2. 安装依赖

```bash
cd education_brain_front
npm install
```

### 3. 启动开发服务器

```bash
npm run dev
```

打开 `http://localhost:5173` 即可使用。

### 4. 构建生产版本

```bash
npm run build
# 产物在 dist/ 目录
```

## 环境变量

在项目根目录创建 `.env` 文件可覆盖默认配置：

```bash
# 后端 API 地址（默认 http://127.0.0.1:8000）
VITE_API_BASE_URL=http://127.0.0.1:8000

# 启用 mock 数据（离线开发时使用）
VITE_USE_MOCK=false

# 启用 HTTP 调试日志
VITE_DEBUG_HTTP=false
```

## 功能页面

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | 智能问答 | AI 对话，支持流式输出 + 引用来源 |
| `/courses` | 课程检索 | 浏览已导入的课程系列和模块 |
| `/questions` | 题目检索 | 按题型、关键词搜索题目 |
| `/documents` | 文档搜索 | 语义搜索文档内容 |
| `/ingest/catalog` | 课程导入 | 导入课程目录文件 |
| `/ingest/questions` | 题库导入 | 导入题库文件 |
| `/ingest/documents` | 文档导入 | 导入文档，支持选择文件夹批量导入 |

## 项目结构

```
src/
├── main.tsx                   # 入口
├── app/
│   ├── App.tsx                # 根组件
│   ├── routes.tsx             # 路由配置
│   ├── pages/
│   │   ├── chat-page.tsx      # 智能问答
│   │   ├── courses-page.tsx   # 课程检索
│   │   ├── questions-page.tsx # 题目检索
│   │   ├── documents-page.tsx # 文档搜索
│   │   └── ingest-page.tsx    # 数据导入（课程/题库/文档）
│   ├── api/
│   │   ├── http.ts            # HTTP 客户端封装
│   │   ├── ingest.ts          # 导入 API
│   │   ├── browse.ts          # 文件浏览 API
│   │   ├── course.ts          # 课程检索 API
│   │   ├── question.ts        # 题目检索 API
│   │   ├── document.ts        # 文档搜索 API
│   │   └── chat.ts            # 问答 API
│   ├── components/
│   │   ├── ui/                # shadcn 基础组件（Dialog, Button, ScrollArea...）
│   │   ├── layout.tsx         # 侧边栏导航
│   │   ├── file-browser-dialog.tsx  # 服务端文件浏览器
│   │   ├── status-badge.tsx   # 任务状态标签
│   │   └── empty-state.tsx    # 空状态占位
│   ├── types/index.ts         # TypeScript 类型定义
│   └── mock/                  # Mock 数据（离线开发用）
└── assets/                    # 静态资源
```
