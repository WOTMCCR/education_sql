# 文档数据重置与重新导入指引

> 状态：运维 / 数据重置操作文档
>
> 该文档不属于前端联调主文档，仅在需要清理并重建文档数据时使用。

这个文档用于解决两类问题：

1. 文档数据重复导入后，MongoDB / Milvus / MinIO 中残留旧数据，影响检索与测试。
2. 需要在一个干净状态下重新导入课程文档与项目文档，再继续 Step 8 之类的联调工作。

本文档只针对“文档导入链路”相关数据，不会清理课程目录和题库数据。

## 一、会清理哪些数据

### 1. MongoDB

会清理以下集合：

- `knowledge_document`
- `knowledge_chunk`
- `source_mapping`
- `ingest_task`

说明：

- `knowledge_document` 存文档级元数据
- `knowledge_chunk` 存文档分块内容
- `source_mapping` 存文档与课程/项目的映射关系
- `ingest_task` 存导入任务历史

### 2. Milvus

会清理以下 collection：

- `edu_chunks`

说明：

- 该值来自 [config.py](/home/ccr/dev/LearningProject/education_brain/knowledge/core/config.py:64) 的 `milvus_collection`
- 当前默认 collection 名为 `edu_chunks`

### 3. MinIO

可选清理以下对象：

- bucket: `education-knowledge`
- prefix: `documents/`

说明：

- 这一步不是检索必需
- 如果不清，只会留下旧图片对象，不会直接影响向量检索结果

## 二、不会清理哪些数据

以下集合默认不动：

- `course_series`
- `course_module`
- `question_bank`
- `question_item`

这些属于课程目录和题库结构化数据，与文档重复导入问题不是同一层。

## 三、重置步骤

### 步骤 1：停止服务

如果本地正在运行 Uvicorn，先停止它。

例如：

```bash
cd /home/ccr/dev/LearningProject/education_brain
knowledge/.venv/bin/python -m uvicorn knowledge.api.app:app --reload --host 0.0.0.0 --port 8000
```

按 `Ctrl+C` 停掉即可。

### 步骤 2：清理 MongoDB 文档相关集合

```bash
cd /home/ccr/dev/LearningProject/education_brain

knowledge/.venv/bin/python - <<'PY'
from knowledge.core.clients import get_mongo_db

db = get_mongo_db()
for name in ["knowledge_document", "knowledge_chunk", "source_mapping", "ingest_task"]:
    db[name].drop()
    print("dropped mongo collection:", name)
PY
```

### 步骤 3：清理 Milvus 文档向量 collection

```bash
cd /home/ccr/dev/LearningProject/education_brain

knowledge/.venv/bin/python - <<'PY'
from knowledge.core.clients import get_milvus
from knowledge.core.config import get_settings

client = get_milvus()
s = get_settings()

if client.has_collection(s.milvus_collection):
    client.drop_collection(s.milvus_collection)
    print("dropped milvus collection:", s.milvus_collection)
else:
    print("milvus collection not found:", s.milvus_collection)
PY
```

### 步骤 4：可选清理 MinIO 旧图片

```bash
cd /home/ccr/dev/LearningProject/education_brain

knowledge/.venv/bin/python - <<'PY'
from knowledge.core.clients import get_minio
from knowledge.core.config import get_settings

client = get_minio()
s = get_settings()

objects = list(client.list_objects(s.minio_bucket, prefix="documents/", recursive=True))
for obj in objects:
    client.remove_object(s.minio_bucket, obj.object_name)

print("removed minio objects:", len(objects))
PY
```

## 四、重新启动服务

```bash
cd /home/ccr/dev/LearningProject/education_brain
knowledge/.venv/bin/python -m uvicorn knowledge.api.app:app --reload --host 0.0.0.0 --port 8000
```

## 五、重新导入文档

### 1. 全量导入课程文档

```bash
curl -s -X POST http://localhost:8000/ingest/documents \
  -H "Content-Type: application/json" \
  -d '{"doc_type":"course_doc"}'
```

### 2. 全量导入项目文档

```bash
curl -s -X POST http://localhost:8000/ingest/documents \
  -H "Content-Type: application/json" \
  -d '{"doc_type":"project_doc"}'
```

接口返回后会得到一个 `task_id`。

### 3. 轮询任务状态

```bash
curl -s http://localhost:8000/ingest/tasks/<task_id>
```

如果返回：

- `status = "completed"`：表示该批导入成功
- `status = "partial_success"`：表示部分文件失败
- `status = "failed"`：表示整批失败

## 六、导入后快速验收

### 1. 验证 MongoDB 中文档数量

```bash
cd /home/ccr/dev/LearningProject/education_brain

knowledge/.venv/bin/python - <<'PY'
from knowledge.core.clients import get_mongo_db
db = get_mongo_db()

print("knowledge_document =", db["knowledge_document"].count_documents({}))
print("knowledge_chunk    =", db["knowledge_chunk"].count_documents({}))
print("doc_types          =", db["knowledge_document"].distinct("doc_type"))
PY
```

### 2. 验证课程文档检索

注意：中文查询不要直接裸写进 URL，使用 `--data-urlencode`。

```bash
curl -sG "http://localhost:8000/search/documents" \
  --data-urlencode "query=神经网络反向传播" \
  --data-urlencode "doc_type=course_doc" \
  --data-urlencode "limit=3"
```

### 3. 验证项目文档检索

```bash
curl -sG "http://localhost:8000/search/documents" \
  --data-urlencode "query=项目架构设计" \
  --data-urlencode "doc_type=project_doc" \
  --data-urlencode "limit=3"
```

### 4. 验证回表字段

```bash
curl -sG "http://localhost:8000/search/documents" \
  --data-urlencode "query=Python" \
  --data-urlencode "limit=1"
```

重点看返回里是否有：

- `chunk_text`
- `section_path`
- `doc_title`
- `source_file`
- `distance`

## 七、当前项目中的已知现实情况

1. 文档重复导入会生成新的 `doc_id`
   所以如果不先清理，再全量导入，就会把旧数据继续保留在 MongoDB 和 Milvus 中。

2. `project_doc` 最容易出现重复命中
   因为你已经多次重跑过项目文档导入。

3. `knowledge_chunk` 本身没有 `doc_type` 字段
   如果要按课程/项目统计 chunk 数量，需要先从 `knowledge_document` 取 `doc_id`，再按 `doc_id` 去 `knowledge_chunk` 统计。

4. MinIO 中旧图片不一定影响检索
   但会造成对象存储里残留旧资源，所以建议在需要“干净环境联调”时一起清。

## 八、推荐工作流

每次准备做较大阶段联调时，建议按这个顺序：

1. 停服务
2. 清理 MongoDB 文档相关集合
3. 清理 Milvus 文档 collection
4. 可选清理 MinIO `documents/`
5. 重启服务
6. 先全量导入 `course_doc`
7. 再全量导入 `project_doc`
8. 用 `/search/documents` 做课程和项目各一条真实检索

如果这 8 步都通过，再继续 Step 8，会明显稳很多。
