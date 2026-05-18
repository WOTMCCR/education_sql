# Fix：课程搜索精度 + LLM 答案生成超时

> 状态：阶段性问题修复记录
>
> 本文档用于说明某一阶段的定位和修复过程，不作为当前接口契约文档。

> 对应 Step 8 重构计划联调中发现的两个问题，独立于主重构阶段，可先行修复。

## 问题 A：课程搜索精度不足

### 现象

"有哪些 Python 相关课程" 和 "Python courses" 都返回了 "数据分析求职班"。
用户预期看到 Python 主题课程，但实际结果是一个数据分析课（只因其下属模块 "SQL/Python数据处理基础" 含有 Python 字样）。

### 根因

当前 `search.py` 的课程查询逻辑（L38-56）：

```
keyword → 查 course_module（module_title / module_desc 匹配）
        → 收集匹配模块的 series_code
        → 与 series 自身 title/description 匹配结果合并
        → 全部平等返回，不区分匹配来源
```

问题在于 **series 级匹配与 module 级匹配权重相同**。用户搜 "Python"：

- course_series：title/description 均无 "Python" → 0 条直接匹配
- course_module："SQL/Python数据处理基础" 命中 → 拉入其父系列 "数据分析求职班"

结果：用户得到一个与 Python 只有间接关系的课程，无法判断相关性。

### 修复方案

在 `course_search.py` service 中引入 **匹配层级（match_level）**，区分直接匹配和间接匹配：

#### 1. 匹配层级定义

| match_level | 含义 | 匹配来源 |
|-------------|------|----------|
| `"title"` | 系列名称直接包含关键词 | `course_series.title` |
| `"description"` | 系列描述包含关键词 | `course_series.description` |
| `"category"` | 分类路径包含关键词 | `course_series.category_path` |
| `"module"` | 下属模块包含关键词 | `course_module.module_title / module_desc` |

#### 2. 排序规则

按匹配层级排序，直接匹配优先：

```
title > description > category > module
```

同一层级内按原有顺序（MongoDB 自然序）。

#### 3. 实现要点

```python
def search_courses(keyword: str, ...) -> CourseSearchResult:
    # 分层查询，标记 match_level
    results = []

    if keyword:
        regex = {"$regex": re.escape(keyword), "$options": "i"}

        # 第一层：series 自身匹配
        for series in db["course_series"].find({"title": regex}):
            results.append((series, "title"))
        for series in db["course_series"].find({"description": regex, "title": {"$not": regex}}):
            results.append((series, "description"))
        for series in db["course_series"].find({"category_path": regex, "title": {"$not": regex}, "description": {"$not": regex}}):
            results.append((series, "category"))

        # 第二层：module 匹配（排除已命中的 series）
        found_codes = {s["series_code"] for s, _ in results}
        module_codes = db["course_module"].distinct("series_code", {
            "$or": [{"module_title": regex}, {"module_desc": regex}],
            "series_code": {"$nin": list(found_codes)},
        })
        for series in db["course_series"].find({"series_code": {"$in": module_codes}}):
            results.append((series, "module"))

    # 每条结果附带 match_level 字段
    ...
```

#### 4. chat 路径的话术区分

`chat_formatter.py` 根据 `match_level` 生成不同摘要：

- 有 title/description/category 级匹配：
  > "以下是 Python 相关课程："

- 只有 module 级匹配：
  > "没有直接以 Python 为主题的课程，但以下课程包含 Python 相关模块："

- 无任何匹配：
  > "未找到与 Python 相关的课程。请尝试其他关键词。"

#### 5. 返回结构扩展

`/search/courses` 的每条 item 新增 `match_level` 字段：

```json
{
  "series_code": "data_analysis_and_visualization_foundation",
  "title": "数据分析求职班",
  "match_level": "module",
  "matched_modules": ["SQL/Python数据处理基础"]
}
```

前端可据此做 UI 区分（如 module 级匹配灰显或折叠）。

#### 6. 改动文件

- 新增 `knowledge/service/course_search.py`（Phase B 产物，提前实现匹配层级）
- 修改 `knowledge/api/routes/search.py`（委托给 service）
- 修改 `knowledge/api/routes/chat.py`（`_handle_course` 委托给 service）
- 新增 `knowledge/tests/test_course_search.py`

#### 7. 与主重构计划的关系

此修复即 **Phase B 的课程 service 抽离**，但聚焦于匹配精度。
可作为 Phase B 的第一步单独落地，不依赖 Phase A（意图槽位改造）。

---

## 问题 B：knowledge_qa 答案生成超时

### 现象

`/chat/query` 对知识问答请求返回 200，`result_type="answer"`，但日志中出现：

```
答案生成 失败: Request timed out.
```

返回内容是降级后的检索内容拼接，不是 LLM 生成的回答。

### 根因

三个因素叠加：

1. **模型选择不当**：`ANSWER_MODEL` 为空，fallback 到 `LLM_MODEL=deepseek-r1:14b`。
   deepseek-r1 是 reasoning model，每次请求先在 `<think>` 标签内生成大量内部推理（这些 token 消耗时间但不出现在最终输出中），延迟远高于普通指令模型。

2. **超时太短**：`openai_timeout_seconds` 默认 30 秒，对 14B reasoning model + 12000 字符上下文严重不足。
   实测 deepseek-r1:14b 在本地 Ollama 上生成一段 500 字回答通常需要 45-90 秒。

3. **超时配置不分场景**：全局只有一个 `openai_timeout_seconds`，但不同 LLM 调用场景需求差异大：

   | 场景 | 典型耗时 | 合理超时 |
   |------|----------|----------|
   | 意图分类（max_tokens=20） | 2-5s | 10s |
   | 查询改写（max_tokens~100） | 3-8s | 15s |
   | HyDE 假设文档（max_tokens~200） | 5-15s | 20s |
   | 答案生成（长文本） | 30-90s | 120s |

### 修复方案

分两步：**快速缓解**（改配置） + **结构性修复**（改代码）。

#### Step 1：快速缓解（仅改 .env）

```env
# 指定非推理模型做答案生成（如果本地有拉取）
ANSWER_MODEL=qwen2.5:14b

# 提高全局超时到 120 秒（临时方案）
OPENAI_TIMEOUT_SECONDS=120
```

如果本地没有 qwen2.5，先只改超时：

```env
OPENAI_TIMEOUT_SECONDS=120
```

这样 deepseek-r1:14b 至少有足够时间完成生成。代价是意图分类等轻量调用也要等 120 秒才超时，但实际不会触发（它们正常都在 10 秒内返回）。

#### Step 2：结构性修复（改代码）

##### 2.1 Config 新增分场景超时

`knowledge/core/config.py`：

```python
# ── LLM 超时（秒）──
openai_timeout_seconds: float = 30.0       # 默认超时（意图分类、查询改写等轻量调用）
answer_timeout_seconds: float = 120.0      # 答案生成专用超时
```

##### 2.2 LLM 调用支持自定义超时

`knowledge/core/llm.py` 的 `chat_completion_text` 新增 `timeout` 参数：

```python
def chat_completion_text(
    *,
    model: str,
    messages: list[dict[str, str]],
    purpose: str,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    timeout: float | None = None,          # 新增：调用方可覆盖超时
) -> str | None:
    settings = get_settings()
    effective_timeout = timeout or settings.openai_timeout_seconds
    ...
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "timeout": effective_timeout,       # 使用有效超时
    }
```

##### 2.3 答案生成节点使用专用超时

`knowledge/processor/query_pipeline/nodes/answer_generate.py`：

```python
answer = chat_completion_text(
    model=s.effective_answer_model,
    messages=[...],
    purpose="答案生成",
    temperature=0.3,
    timeout=s.answer_timeout_seconds,       # 使用答案生成专用超时
)
```

##### 2.4 熔断冷却时间调整

当前 `llm_failure_cooldown_seconds=3`，超时触发后 3 秒内所有 LLM 调用都跳过。
如果用户连续发两条消息，第二条的意图分类也会被跳过（误伤）。

建议：将冷却从全局改为**按 purpose 分组**，或至少区分"答案生成超时"和"其他调用超时"。

简单做法：answer_generate 超时后**不触发全局熔断**（因为超时是预期中的，不代表 Ollama 不可用）：

```python
# answer_generate.py 中自行 catch，不走全局熔断
try:
    answer = chat_completion_text(...)
except Exception:
    answer = None   # 降级但不影响其他调用
```

实际上当前 `chat_completion_text` 已经 catch 了所有异常并返回 None，但同时触发了全局熔断。修复方式是让调用方可以选择不触发熔断：

```python
def chat_completion_text(
    ...
    trigger_cooldown: bool = True,          # 新增：是否触发熔断冷却
) -> str | None:
```

#### 改动文件

- `knowledge/core/config.py` — 新增 `answer_timeout_seconds`
- `knowledge/core/llm.py` — `chat_completion_text` 支持 `timeout` 和 `trigger_cooldown` 参数
- `knowledge/processor/query_pipeline/nodes/answer_generate.py` — 传入专用超时，不触发全局熔断
- `knowledge/.env` — 新增 `ANSWER_TIMEOUT_SECONDS=120`，建议设置 `ANSWER_MODEL`
- `knowledge/tests/test_llm.py` — 补充分超时场景测试

#### 与主重构计划的关系

此修复对应 **Phase D（收紧 knowledge_qa 管线）** 的一部分，但不依赖 Phase A-C，可独立先行。

---

## 执行建议

两个问题的修复互不依赖，可按风险从低到高排序：

| 优先级 | 修复 | 耗时预估 | 风险 |
|--------|------|----------|------|
| **P0** | 问题 B Step 1：改 .env 超时配置 | 5 分钟 | 无（纯配置） |
| **P1** | 问题 B Step 2：拆分超时 + 熔断改造 | 1-2 小时 | 低（内部接口变更，有测试覆盖） |
| **P2** | 问题 A：课程搜索匹配层级 | 2-3 小时 | 低（新增 service，不改现有接口契约） |

建议先做 P0 验证 knowledge_qa 能正常生成答案，再做 P1 和 P2。
