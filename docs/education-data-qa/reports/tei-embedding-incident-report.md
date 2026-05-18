# TEI Embedding 服务故障分析报告

**日期**：2026-05-18
**环境**：WSL2 (6.6.87.2-microsoft-standard-WSL2) / 24 vCPU / No GPU
**涉及组件**：Text Embeddings Inference (TEI) Docker 容器
**当前状态**：已修复（升级到 cpu-1.9）

---

## 1. 问题概述

Iteration 01 开发期间，TEI `cpu-1.8` 容器能正常启动并报告 `Ready`，但接收到真实 `/embed` 请求后触发 Rust panic，进程重启。Docker `restart: unless-stopped` 策略会让容器再次拉起，因此表面上 `/health` 可用，但 embedding 请求返回 `Empty reply from server`。开发期间曾临时使用 `ANALYTICS_EMBEDDING_MODE=local_hash`（基于 SHA256 的确定性伪向量）绕过，丧失了语义召回能力。

## 2. 故障链

```text
[触发条件] 模型目录缺少 onnx/model.onnx
  → TEI 无法使用 ORT (ONNX Runtime) 后端
  → 降级到 Candle (纯 Rust) CPU 后端
  → TEI cpu-1.8 的 Candle/router 组合在当前 WSL CPU 环境真实请求下触发 queue panic
  → 进程重启，客户端收到 Empty reply
  → [修复] 升级到 TEI cpu-1.9，同样缺 ONNX 的情况下 Candle 后端可稳定返回 1024 维向量
```

## 3. 根因详解

### 3.1 TEI 的双后端架构

TEI 内部有两条推理路径，按优先级尝试：

| 优先级 | 后端 | 依赖文件 | CPU 推理速度 | 稳定性 |
|--------|------|---------|-------------|--------|
| 1 | **ORT (ONNX Runtime)** | `onnx/model.onnx` | ~100ms/文本 | 稳定 |
| 2 | **Candle (纯 Rust)** | `pytorch_model.bin` 或 `.safetensors` | 与模型/版本/CPU 有关 | `cpu-1.8` 在当前环境不稳定，`cpu-1.9` 已验证稳定 |

当 ORT 后端因文件缺失无法启动时，TEI 会降级到 Candle。日志中的 ERROR 级别记录了这一降级，但不会阻止服务启动：

```
ERROR: Could not start ORT backend: File at /models/bge-large-zh-v1.5/onnx/model.onnx does not exist
INFO:  Starting Bert model on Cpu    ← 降级到 Candle
```

### 3.2 模型目录状态

```text
bge-large-zh-v1.5/
├── pytorch_model.bin          ← 1.3GB，PyTorch 格式权重
├── config.json
├── tokenizer.json
├── vocab.txt
├── 1_Pooling/
└── (无 onnx/ 目录)            ← 缺失
```

BGE-large-zh-v1.5 本地目录当前只包含 PyTorch 权重，不含 ONNX 格式。缺少 ONNX 会解释为什么 TEI 使用 Candle，但不能单独解释 panic：升级到 `cpu-1.9` 后，仍然缺少 `onnx/model.onnx`，但真实 `/embed` 已稳定可用。

### 3.3 TEI cpu-1.8 的 queue panic

在 `cpu-1.8` 下，单条 `/embed` 请求即可触发 `Full(..)` panic。当前证据能确认这是 TEI `cpu-1.8` 在本机 WSL CPU + Candle 路径下的稳定性问题；是否由推理耗时、队列容量或 router/backend 协调逻辑直接导致，需要以 TEI 上游实现和 issue 为准，不能只归因于“推理太慢”。TEI panic 信息中对此标注了 `This is a bug`：

```rust
// core/src/queue.rs:87
Queue background task dropped the receiver or the receiver is too behind. This is a bug.
```

### 3.4 版本差异

| 版本 | Candle CPU 表现 | 结果 |
|------|----------------|------|
| cpu-1.8 | 容器 Ready，但真实 `/embed` 返回 Empty reply 并触发 queue panic | 无法使用 |
| cpu-1.9 | 同样 Candle 路径；单条 smoke 约 129ms，meta 构建日志中多为数十到数百 ms，长文本可到 1s+ | 正常工作 |

`cpu-1.9` 在当前环境中即使没有 ONNX 文件也能稳定完成推理，queue panic 不再出现。这里应记录为“版本升级修复/规避了该稳定性问题”，不要把 ONNX 缺失视为唯一根因。

## 4. 修复措施

### 已执行

升级 TEI 镜像从 `cpu-1.8` 到 `cpu-1.9`：

```yaml
# infra/education-data-qa/docker-compose.yaml
embedding:
  image: ghcr.io/huggingface/text-embeddings-inference:cpu-1.9  # was cpu-1.8
```

升级后验证：
- `/embed` 请求正常返回 1024 维向量
- 单条 smoke 推理约 129ms；完整 meta 构建期间请求耗时从数十 ms 到 1s+ 不等（Candle CPU）
- 连续多次请求无 panic
- 日志中仍有 ORT 缺失的 ERROR，但 Candle 后端稳定工作

### 建议后续优化

**导出 ONNX 模型**（可选实验项，进一步降低延迟并消除 ORT 缺失日志）：

```bash
pip install optimum[onnxruntime]
optimum-cli export onnx \
  --model /home/ccr/local-docker/nl2sql-env/embedding/bge-large-zh-v1.5 \
  /home/ccr/local-docker/nl2sql-env/embedding/bge-large-zh-v1.5/onnx/
```

导出后需要重新启动 TEI，并通过 `/info` 与容器日志确认 ORT 后端被识别、`Could not start ORT backend` 日志消失。ONNX 导出产物的文件名和目录结构要以 TEI 实际识别结果为准，不能只假设 `optimum-cli` 的默认输出一定匹配。

## 5. local_hash 降级方案评估

Iteration 01 期间使用的 `hash_embedding` 函数（`education_brain/knowledge/analytics/meta_store.py`）：

```python
def hash_embedding(text: str, dimensions: int = 1024) -> list[float]:
    """基于 SHA256 的确定性伪向量"""
    vector = [0.0] * dimensions
    tokens = [text[i : i + size] for size in (1, 2, 3) for i in range(max(0, len(text) - size + 1))]
    for token in tokens or [text]:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]
```

| 维度 | hash_embedding | 真实 embedding (BGE) |
|------|---------------|---------------------|
| 原理 | 字符 n-gram 哈希分散到固定维度 | 预训练 Transformer 编码语义 |
| 精确匹配（"收入" → "收入金额"） | 部分可用（字符重叠） | 可用 |
| 同义召回（"营收" → "收入金额"） | 不可用 | 可用 |
| 跨语言（"revenue" → "收入"） | 不可用 | 可用 |
| 确定性 | 完全确定 | 模型确定 |
| 适用场景 | 冒烟测试、链路验证 | 生产召回 |

**结论**：local_hash 是合格的链路打通工具，但不能用于真实语义召回。TEI 修复后应将 `ANALYTICS_EMBEDDING_MODE` 切换为 `tei`（或保留 `local_hash` 作为 CI 测试 fallback）。

## 6. 项目内 Embedding 能力全景

当前项目存在两套独立的 embedding 体系：

```text
education_brain_fullstack/
├── education_brain/knowledge/
│   ├── core/clients.py          ← get_bge_m3(): pymilvus BGEM3EmbeddingFunction
│   │                               模型: BGE-M3 (2.2GB), 进程内加载
│   │                               输出: dense + sparse 双向量
│   │                               存储: Milvus
│   │                               用途: RAG 知识库检索
│   │
│   └── analytics/meta_store.py  ← embed_texts(): TEI HTTP API 或 local_hash
│                                    模型: BGE-large-zh-v1.5 (1.3GB), Docker 服务
│                                    输出: dense 向量 (1024维)
│                                    存储: Qdrant
│                                    用途: 问数元数据语义召回
│
└── infra/education-data-qa/
    └── docker-compose.yaml      ← TEI 容器定义
```

### 对比

| 维度 | RAG pipeline | 问数 pipeline |
|------|-------------|--------------|
| 模型 | BGE-M3 (BAAI/bge-m3) | BGE-large-zh-v1.5 |
| 模型大小 | 2.2GB | 1.3GB |
| 加载方式 | Python 进程内 (pymilvus) | Docker 容器 (TEI HTTP) |
| 向量类型 | dense (1024d) + sparse | dense only (1024d) |
| 向量存储 | Milvus | Qdrant |
| 设备要求 | GPU 推荐，CPU 可用 | CPU only (当前环境) |
| 独立性 | 嵌入 FastAPI 进程 | 独立容器，HTTP 解耦 |

### 为什么不复用 RAG 的 BGE-M3

1. **耦合风险**：RAG pipeline 当前围绕 BGE-M3 的 dense + sparse 输出和 Milvus 写入 schema 组织。问数只需要 dense 向量，直接复用会把问数元数据召回耦合到 RAG pipeline 的数据契约。
2. **内存开销**：BGE-M3 占 2.2GB 内存。如果 FastAPI 进程同时服务 RAG 和问数，两个模型共存需要 3.5GB+。TEI 容器隔离内存，互不影响。
3. **生命周期差异**：RAG 和问数可能独立部署、独立扩缩。进程内共享模型会使两者的部署边界模糊。

## 7. Embedding 选型建议

### 当前（学习项目阶段）

维持 TEI cpu-1.9 + BGE-large-zh-v1.5 方案：
- TEI 已修复，短文本推理延迟可接受
- 与 Qdrant 的 1024 维 collection 天然对齐
- 无额外成本（本地推理）
- `ANALYTICS_EMBEDDING_MODE` 已从 `local_hash` 切换为 `tei`
- 可选：导出 ONNX 模型进一步优化

### 未来（如果需要更高质量）

| 方案 | 优点 | 缺点 | 适合场景 |
|------|------|------|---------|
| **TEI + BGE-large-zh-v1.5** | 零成本、本地可控、已集成 | 中文语义质量中等 | 当前学习项目 |
| **OpenAI embedding API** | 质量高、延迟低、无本地资源占用 | 有 API 成本、依赖网络；具体模型需实现时复核官方文档 | 需要高质量同义召回 |
| **TEI + BGE-M3** | 中文质量优秀 | 模型 2.2GB、CPU 推理更慢 | 需要离线+高质量 |
| **Python 进程内 sentence-transformers** | 无需 Docker、依赖已在 pyproject.toml | 首次加载慢、占进程内存 | 极简部署 |

### ANALYTICS_EMBEDDING_MODE 三档设计

当前代码已支持 `local_hash` 和 `tei` 两种模式。可考虑保留三档切换能力：

```python
# config.py
analytics_embedding_mode: str = "tei"  # tei | openai | local_hash
```

- `tei`：生产/开发默认，调本地 TEI 容器
- `openai`：高质量备选，调远程 API（当前未实现，需配置 API key、model 和批量调用逻辑）
- `local_hash`：CI 测试专用，不依赖任何外部服务

## 8. 待办事项

- [x] 将 `ANALYTICS_EMBEDDING_MODE` 默认值从 `local_hash` 切回 `tei`
- [x] 用真实 embedding 重新执行 `build_meta`，覆盖写入 Qdrant 向量
- [ ] 发布前如需清理历史 point，再执行一次 `build_meta --recreate`
- [ ] 验证语义召回质量：搜"营收"能否召回 `paid_revenue`，搜"退了多少"能否召回 `refund_amount`
- [ ] 可选：导出 ONNX 模型消除 TEI 启动时的 ERROR 日志
- [ ] 可选：增加 `openai` embedding mode 作为备选

## 9. 参考资料

- Hugging Face TEI CPU 文档：https://huggingface.co/docs/text-embeddings-inference/en/local_cpu
- Hugging Face TEI Quick Tour：https://huggingface.co/docs/text-embeddings-inference/en/quick_tour
- 相关上游 issue：https://github.com/huggingface/text-embeddings-inference/issues/744
