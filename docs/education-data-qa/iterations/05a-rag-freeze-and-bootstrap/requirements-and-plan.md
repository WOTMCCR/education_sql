# Iteration 05A：旧 RAG 清理收束与数据生成入口标准化

## 背景

当前教育问数主线依赖的是生成业务数据和 meta/metric 资产：

```text
init_db
  -> generate.main --profile smoke
  -> build_meta.py --recreate
  -> MySQL meta tables + Qdrant metric/column + ES dimension values
  -> data_qa
```

旧文档 RAG 依赖 doc chunk、MinIO、Milvus 和 Mongo document store。Iteration 04 已决定直接删除旧 RAG，不做兼容保留；05A 只负责确认删除收束，并把数据准备入口固定到 `generate + build_meta`。

## 目标

- 确认旧文档 RAG 主链路已删除且无残留 import/路由。
- 固定数据生成和 meta/metric 构建命令。
- 明确 `bootstrap` 是重依赖完整准备验证，只在 CI/CD、发布前或手动执行。

## 非目标

- 不实现 `meta_qa`。
- 不迁移 Milvus 数据。
- 不恢复旧课程文档上传问答能力。

## 数据准备标准流程

```bash
cd data_ge/edu-data
uv run init_db.py
uv run -m generate.main --profile smoke

cd ../../education_brain
PYTHONPATH=. knowledge/.venv/bin/python -m knowledge.analytics.build_meta \
  --config ../data_ge/edu-data/meta/education_meta.yaml --recreate
SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh
```

`SMOKE_STAGE=bootstrap` 可以把上述流程串起来，但它可能耗时数分钟，不进入本地默认 `SMOKE_STAGE=all`。

## 清理边界

- MongoDB：只维护 `chat_history` 和可选 `chat_session_summary`。
- Milvus：不参与 `data_qa`、不参与后续 `meta_qa`。
- MinIO：不参与教育问数主路径。
- doc chunking：不作为数据问数或指标说明的知识来源。
- `mode=knowledge`：不作为兼容路径保留；`/chat/query` 只接受已定义的显式 mode。

## 验收

- 运行 `generate` 后，核心业务表有真实行数。
- 运行 `build_meta` 后，`/analytics/health` healthy。
- Qdrant 可召回 `paid_revenue` 和关键字段。
- ES 可召回真实校区或课程取值。
- 主文档不再要求 Mongo/Milvus/MinIO 作为 `data_qa` 前置依赖。
- 应用启动不再 import `knowledge.processor`、`intent_classifier`、`chat_sync` 或旧 stream RAG 模块。
