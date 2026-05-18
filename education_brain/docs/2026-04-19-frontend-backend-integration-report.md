# 2026-04-19 前后端联调记录

## 本次范围

- 后端项目：`education_brain/knowledge`
- 前端项目：`education_brain_front`
- 目标：在不修改业务逻辑代码的前提下，验证本地联调是否具备启动条件，并整理阻塞项

## 本次实际验证

- 已确认后端 Python 虚拟环境存在：`education_brain/knowledge/.venv`
- 已确认前端当前没有 `node_modules`
- 已确认前端 `npm run dev` / `npm run build` 当前都会失败
- 已确认宿主机上 MongoDB / Milvus / MinIO Docker 容器处于运行状态
- 已确认当前 Codex 沙箱无法完成真实的本地 HTTP 联调

## 环境层阻塞

### 1. 当前沙箱无法做真实 socket / localhost 联调

在本次 Codex 沙箱里：

- `curl http://127.0.0.1:8000/health` 失败，无法连接本地服务
- Python 直接创建 socket 会报 `PermissionError: [Errno 1] Operation not permitted`
- 这意味着即使 Uvicorn 打印了 `running on http://127.0.0.1:8000`，当前沙箱里也不能据此完成真实端口连通验证

结论：

- 这里可以做代码、配置、接口契约和启动链路检查
- 但不能把“在当前 Codex 沙箱里 HTTP 联调成功”作为可交付结果

### 2. 当前沙箱外网关闭，前端依赖无法在这里安装

本次环境里存在：

- `CODEX_SANDBOX_NETWORK_DISABLED=1`
- `curl` 访问 npm / PyPI 均失败

直接结果：

- 不能在这里执行前端依赖下载
- 如果要装前端依赖，需要你在正常终端里执行

### 3. 前端当前没有依赖，Vite 无法启动

已复现：

```bash
cd /home/ccr/dev/LearningProject/education_brain_front
npm run dev
```

输出：

```text
> @figma/my-make-file@0.0.1 dev
> vite

sh: 1: vite: not found
```

同样，`npm run build` 也报 `vite: not found`

直接原因：

- `education_brain_front` 下没有 `node_modules`
- 当前也没有 lockfile，安装结果会依赖当下 registry 解析版本

## 代码与接口联调阻塞

即使你把前端依赖装好，当前代码状态下也还不能直接联通后端，主要有下面几类问题。

### 1. 前端仍然强制走 mock

文件：`education_brain_front/src/app/api/http.ts`

当前代码：

- `const BASE_URL = ''`
- `const useMock = true`

这意味着：

- 页面默认不会请求真实后端
- 即使后端启动正常，前端现在也仍会优先走 mock 数据

### 2. 前端没有接入真实后端 base URL 或 Vite 代理

当前前端真实请求路径仍是相对路径：

- `/chat/...`
- `/search/...`
- `/ingest/...`

但：

- `BASE_URL` 没有真正读取 `VITE_API_BASE_URL`
- `vite.config.ts` 里也没有把这些路径代理到 `http://127.0.0.1:8000`

这意味着：

- 如果后续只是把 `useMock` 改成 `false`，浏览器请求仍会默认打到前端自身域名，例如 `http://localhost:5173/chat/query`
- 而不是后端 `http://localhost:8000/chat/query`

### 3. 后端 CORS 当前未显式配置

后端配置入口：`education_brain/knowledge/core/config.py`

当前默认值：

- `cors_allow_origins = []`

而 `education_brain/knowledge/.env` 里目前没有看到 `CORS_ALLOW_ORIGINS`

这意味着：

- 如果前端后续通过绝对地址直接访问 `http://127.0.0.1:8000`
- 浏览器大概率会遇到跨域问题

### 4. 聊天接口契约不一致

前端当前实现：

- `chatQuery()` 调的是 `POST /chat/query`
- 请求体发的是 `{ session_id, question, mode, doc_type }`
- 然后再拿返回的 `task_id` 去建立 SSE

后端当前实现：

- 同步入口：`POST /chat/query`
- 流式提交入口：`POST /chat/query/stream`
- 后端请求体字段是 `{ query, session_id }`

直接不一致点：

- 前端把 `question` 发给了后端，但后端要的是 `query`
- 前端把流式入口做成了“先调同步接口，再连 SSE”，但后端要求先调 `/chat/query/stream`
- 前端类型里保留了 `mode`，但后端当前返回模型里没有这个字段

### 5. 聊天历史接口路径与返回结构不一致

前端当前实现：

- `GET /chat/history/{session_id}`
- 期待返回：`{ session_id, items: [...] }`

后端当前实现：

- `GET /chat/history?session_id=...&limit=...`
- 返回：`{ session_id, messages: [...] }`

直接不一致点：

- 路径不一致
- 返回字段 `items` / `messages` 不一致

### 6. Chat intent 枚举不一致

前端类型：

- `course_intro`
- `question_search`
- `doc_search`
- `knowledge_qa`

后端当前实现和文档：

- `course_intro`
- `question_search`
- `knowledge`

直接结果：

- 前端聊天页当前把用户和助手消息都硬编码成 `knowledge_qa`
- 与后端真实 intent 不一致

### 7. 课程查询接口参数和响应结构不一致

前端当前调用：

- 参数使用 `page_size`
- 类型里期待 `pagination`
- 课程字段期待 `series_title`

后端当前实现：

- 参数使用 `size`
- 响应顶层返回 `{ total, page, size, items }`
- 课程标题字段是 `title`，不是 `series_title`

### 8. 题目查询接口参数和响应结构不一致

前端当前调用：

- 参数使用 `page_size`
- 传了 `show_quality_flags`
- 类型里期待 `pagination`
- 前端题型枚举使用 `single_choice` / `multiple_choice`

后端当前实现：

- 参数使用 `size`
- 没有 `show_quality_flags`
- 响应顶层返回 `{ total, page, size, items }`
- 后端题型是中文值，如 `单选题`、`多选题`

### 9. 文档检索接口参数不一致

前端当前调用：

- `GET /search/documents?query=...&doc_type=...&top_k=5`

后端当前实现：

- `GET /search/documents?query=...&doc_type=...&limit=5`

### 10. 导入接口契约差异最大

前端当前实现：

- 文档导入请求体发 `file_paths`
- 还会发 `source_mappings`
- 期待提交响应里有 `task_type`、`status`、`sub_task_count`
- 期待任务详情里有 `progress` 对象和 `progress_logs[].time`

后端当前实现：

- 文档导入请求体字段是 `file_path`
- 提交响应模型只有 `{ task_id }`
- 任务详情直接返回 Mongo 文档
- 日志字段是 `progress_logs[].timestamp`
- 当前任务文档没有前端类型里定义的 `progress` 聚合对象

## 当前可执行结论

当前不能直接说“前后端已经联通”，原因不是一个，而是三层叠加：

1. 当前 Codex 沙箱不允许真实 localhost socket 联调
2. 前端依赖未安装，Vite 现在起不来
3. 即使依赖装好，前后端接口契约也还没有真正对齐

## 建议你在本机终端先执行

### 1. 安装前端依赖

```bash
cd /home/ccr/dev/LearningProject/education_brain_front
npm install
```

### 2. 启动后端

建议先不用 `main.py` 的热重载，直接单进程启动，便于联调定位：

```bash
cd /home/ccr/dev/LearningProject/education_brain
/home/ccr/dev/LearningProject/education_brain/knowledge/.venv/bin/python -m uvicorn knowledge.api.app:app --host 127.0.0.1 --port 8000 --app-dir /home/ccr/dev/LearningProject/education_brain
```

### 3. 启动前端

```bash
cd /home/ccr/dev/LearningProject/education_brain_front
npm run dev -- --host 127.0.0.1 --port 5173
```

## 下一步建议

等你在本机把前后端都启动起来后，下一轮可以直接做这两件事：

1. 先对齐“能否打到真实后端”
2. 再对齐具体接口字段与返回结构

本次我没有改业务逻辑代码，只完成了环境、启动链路和接口契约层面的联调排查。
