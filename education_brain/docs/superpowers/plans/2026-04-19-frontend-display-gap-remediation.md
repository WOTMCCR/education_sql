# Frontend Display Gap Remediation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the five display-level gaps called out from `docs/需求文档.md` by enriching backend payloads where required and wiring the frontend to expose richer course detail, search provenance, and chat history management.

**Architecture:** Treat this as a contract-first vertical slice across two sibling apps: `education_brain` owns data shape and APIs, `education_brain_front` owns presentation and interaction. Start by auditing real source data and existing payloads, then extend backend contracts with the minimum new fields/endpoints, and only after that adapt the frontend API layer and UI. Keep all new logic focused, heavily tested on the backend, and reuse existing frontend page/component patterns instead of introducing a parallel design system.

**Tech Stack:** FastAPI, Pydantic, MongoDB-backed service layer, React 18, React Router 7, Vite 6, node built-in test runner.

---

## Backend Change Summary

Backend changes are required for 4 of the 5 requested display gaps:

1. **Course detail completeness**: current `CourseSeries` / parser / search response do not expose `先修要求` / `项目实战内容` / `课程定位`.
2. **Course search filters**: current route only supports `keyword` / `audience` / `goal`; explicit `项目名` / `知识点` filters are missing.
3. **Document provenance**: current document search response returns `series_code` and `project_name`, but not `series_title` / richer course-facing provenance for display.
4. **Question provenance**: current question search returns raw `question_item` records and does not expose course attribution or bank display metadata in one response.
5. **Chat history management**: current chat API only supports `GET /chat/history`; session list / delete / clear are missing.

Pure frontend work is only sufficient for the visual sections, filter controls, and history UI once the backend contracts exist.

## Working Assumptions

- `education_brain` is the active git repo. `education_brain_front` is not a standalone git repo in the current workspace snapshot, so do backend commits normally and verify frontend changes locally.
- Source-of-truth requirements are in `docs/需求文档.md`.
- The course catalog source file may or may not already contain `先修要求` / `项目实战内容` / `课程定位`. The plan begins with an audit step so the parser change matches reality instead of inventing fields blindly.
- Frontend page work should preserve the existing sidebar/routes in `education_brain_front/src/app/routes.tsx` and the current visual language.

### Task 1: Audit Real Data Shapes Before Extending Contracts

**Files:**
- Read: `education_brain/docs/需求文档.md`
- Read: `education_brain/data/数据/课程介绍.md`
- Read: `education_brain/data/数据/题目资料.md`
- Read: `education_brain/knowledge/service/course_search.py`
- Read: `education_brain/knowledge/service/question_search.py`
- Read: `education_brain/knowledge/service/document_search.py`
- Read: `education_brain/knowledge/service/chat_history.py`
- Write: `education_brain/docs/2026-04-19-display-gap-data-audit.md`

- [ ] **Step 1: Capture the exact course catalog fields available in source data**

Run:

```bash
cd /home/ccr/dev/LearningProject/education_brain
rg -n "先修|项目实战|课程定位|知识点|项目名" data/数据/课程介绍.md
```

Expected: either matching lines showing those labels exist, or an empty result that proves the parser must derive/fallback those sections.

- [ ] **Step 2: Capture the exact question source fields available in source data**

Run:

```bash
cd /home/ccr/dev/LearningProject/education_brain
rg -n "题库编码|题型|题干|答案|解析" data/数据/题目资料.md | head -40
```

Expected: concrete evidence of what metadata is available directly from the source file.

- [ ] **Step 3: Record the current backend payload gaps in a short audit note**

Write `docs/2026-04-19-display-gap-data-audit.md` with a table like:

```md
| Area | Source data available | Current API returns | Gap |
|------|------------------------|---------------------|-----|
| Course detail | title, audience, goal_tags, ... | no prerequisites/project practice | backend schema needed |
```

- [ ] **Step 4: Verify current API responses against the audit**

Run:

```bash
cd /home/ccr/dev/LearningProject/education_brain
curl -sS 'http://127.0.0.1:8000/search/courses?page=1&size=1' | python3 -m json.tool | sed -n '1,120p'
curl -sS 'http://127.0.0.1:8000/search/questions?page=1&size=1' | python3 -m json.tool | sed -n '1,120p'
curl -sS 'http://127.0.0.1:8000/search/documents?query=Python&limit=1' | python3 -m json.tool | sed -n '1,120p'
curl -sS 'http://127.0.0.1:8000/chat/history?session_id=session_web_001&limit=5' | python3 -m json.tool | sed -n '1,120p'
```

Expected: concrete JSON snapshots confirming what the frontend can consume today.

- [ ] **Step 5: Commit the audit note**

```bash
cd /home/ccr/dev/LearningProject/education_brain
git add docs/2026-04-19-display-gap-data-audit.md
git commit -m "docs: audit display gap data contracts"
```

### Task 2: Extend Course Schema and Search Filters for Rich Detail Display

**Files:**
- Modify: `education_brain/knowledge/models/course.py`
- Modify: `education_brain/knowledge/processor/catalog_parser.py`
- Modify: `education_brain/knowledge/processor/catalog_store.py`
- Modify: `education_brain/knowledge/service/course_search.py`
- Modify: `education_brain/knowledge/api/routes/search.py`
- Test: `education_brain/knowledge/tests/test_catalog_parser.py`
- Test: `education_brain/knowledge/tests/test_course_search.py`

- [ ] **Step 1: Write the failing parser/search tests for richer course detail**

Add tests that assert the enriched series shape includes optional display fields and new filters:

```python
def test_parse_catalog_keeps_optional_course_detail_fields(tmp_path):
    file_path = tmp_path / "课程介绍.md"
    file_path.write_text(
        "## Python 基础班\n"
        "- **系列编码**: python-101\n"
        "- **课程定位**: 零基础入门\n"
        "- **先修要求**: 计算机基础, 逻辑思维\n"
        "- **项目实战内容**: 命令行工具, 文件处理器\n"
        "- **知识点**: Python, 数据类型\n"
        ,
        encoding="utf-8",
    )
    series_list, _ = parse_catalog(file_path)
    assert series_list[0].course_positioning == "零基础入门"
    assert series_list[0].prerequisites == ["计算机基础", "逻辑思维"]
    assert series_list[0].project_practice == ["命令行工具", "文件处理器"]
    assert series_list[0].knowledge_points == ["Python", "数据类型"]
```

```python
def test_search_courses_supports_project_and_knowledge_point_filters(monkeypatch):
    result = search_courses(project_name="命令行工具", knowledge_point="数据类型", page=1, size=10)
    assert result["items"][0]["project_practice"] == ["命令行工具", "文件处理器"]
```

- [ ] **Step 2: Run the focused backend tests and verify they fail for the expected reason**

Run:

```bash
cd /home/ccr/dev/LearningProject/education_brain
. knowledge/.venv/bin/activate
python -m pytest knowledge/tests/test_catalog_parser.py knowledge/tests/test_course_search.py -q
```

Expected: FAIL because the new fields/filters do not exist yet.

- [ ] **Step 3: Add the minimum course model fields and parser support**

Implement optional fields in `knowledge/models/course.py`:

```python
class CourseSeries(BaseModel):
    series_code: str
    title: str
    description: str = ""
    category_path: str = ""
    audience: list[str] = Field(default_factory=list)
    goal_tags: list[str] = Field(default_factory=list)
    grade_tags: list[str] = Field(default_factory=list)
    course_positioning: str = ""
    prerequisites: list[str] = Field(default_factory=list)
    project_practice: list[str] = Field(default_factory=list)
    knowledge_points: list[str] = Field(default_factory=list)
```

Extend `_SERIES_FIELD_MAP` / `_LIST_FIELDS` in `catalog_parser.py` to parse those optional labels only when present.

- [ ] **Step 4: Extend course search filtering and payload shape**

In `knowledge/service/course_search.py`, update the query builder and keyword matcher:

```python
def _build_base_query(*, audience: str, goal: str, project_name: str, knowledge_point: str) -> dict:
    filters = []
    if audience:
        filters.append({"audience": audience})
    if goal:
        filters.append({"goal_tags": goal})
    if project_name:
        filters.append({"project_practice": project_name})
    if knowledge_point:
        filters.append({"knowledge_points": knowledge_point})
    ...
```

In `knowledge/api/routes/search.py`, add query params:

```python
project_name: str = Query(default="", description="项目实战内容筛选")
knowledge_point: str = Query(default="", description="知识点筛选")
```

- [ ] **Step 5: Re-run the focused tests and then the broader search suite**

Run:

```bash
cd /home/ccr/dev/LearningProject/education_brain
. knowledge/.venv/bin/activate
python -m pytest knowledge/tests/test_catalog_parser.py knowledge/tests/test_course_search.py knowledge/tests/test_health.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit the backend course contract work**

```bash
cd /home/ccr/dev/LearningProject/education_brain
git add knowledge/models/course.py knowledge/processor/catalog_parser.py knowledge/processor/catalog_store.py knowledge/service/course_search.py knowledge/api/routes/search.py knowledge/tests/test_catalog_parser.py knowledge/tests/test_course_search.py
git commit -m "feat: enrich course detail payloads and filters"
```

### Task 3: Enrich Document and Question Provenance for Display

**Files:**
- Modify: `education_brain/knowledge/service/document_search.py`
- Modify: `education_brain/knowledge/service/question_search.py`
- Modify: `education_brain/knowledge/api/routes/search.py`
- Test: `education_brain/knowledge/tests/test_document_search.py`
- Test: `education_brain/knowledge/tests/test_question_search.py`

- [ ] **Step 1: Write failing tests for richer provenance fields**

Add tests that expect:

```python
def test_document_search_returns_series_title_and_source_path(monkeypatch):
    results = search_documents(query="PyTorch", doc_type="course_doc", limit=1)
    assert results[0]["series_title"] == "深度学习基础班"
    assert results[0]["source_path"].endswith(".docx")
```

```python
def test_question_search_returns_bank_name_and_course_attribution(monkeypatch):
    result = search_questions(keyword="数据类型", page=1, size=10)
    item = result["items"][0]
    assert item["bank_name"] == "通用程序设计题库"
    assert item["series_code"] == "general_purpose_programming_foundation"
    assert item["series_title"] == "通用编程入门班"
```

- [ ] **Step 2: Run the focused provenance tests and verify they fail**

Run:

```bash
cd /home/ccr/dev/LearningProject/education_brain
. knowledge/.venv/bin/activate
python -m pytest knowledge/tests/test_document_search.py knowledge/tests/test_question_search.py -q
```

Expected: FAIL because the provenance fields are not yet assembled.

- [ ] **Step 3: Extend document search assembly with course-facing provenance**

In `knowledge/service/document_search.py`, batch-load `course_series` titles and include them in the assembled result:

```python
series_map = {
    doc["series_code"]: doc
    for doc in db["course_series"].find({"series_code": {"$in": series_codes}}, {"_id": 0, "series_code": 1, "title": 1})
}

results.append({
    "series_code": mapping.get("series_code", ""),
    "series_title": series_map.get(mapping.get("series_code", ""), {}).get("title", ""),
    "project_name": mapping.get("project_name", ""),
    "source_file": source_file,
    "source_path": doc_meta.get("source_path", ""),
    ...
})
```

- [ ] **Step 4: Extend question search with bank display metadata and course attribution**

In `knowledge/service/question_search.py`, join against `question_bank`, `source_mapping`, and `course_series` after loading the raw items:

```python
bank_map = {...}
mapping_map = {...}
series_map = {...}

enriched_items.append({
    **item,
    "bank_name": bank_map.get(item["bank_code"], {}).get("bank_name", ""),
    "series_code": mapping.get("series_code", ""),
    "series_title": series_map.get(mapping.get("series_code", ""), {}).get("title", ""),
})
```

- [ ] **Step 5: Re-run the focused tests and then the API search smoke tests**

Run:

```bash
cd /home/ccr/dev/LearningProject/education_brain
. knowledge/.venv/bin/activate
python -m pytest knowledge/tests/test_document_search.py knowledge/tests/test_question_search.py -q
bash knowledge/tests/smoke_test_api.sh
```

Expected: PASS; smoke test should still report search endpoints as valid.

- [ ] **Step 6: Commit the provenance enrichment**

```bash
cd /home/ccr/dev/LearningProject/education_brain
git add knowledge/service/document_search.py knowledge/service/question_search.py knowledge/tests/test_document_search.py knowledge/tests/test_question_search.py
git commit -m "feat: enrich search provenance for display"
```

### Task 4: Add Chat Session Management Endpoints

**Files:**
- Modify: `education_brain/knowledge/service/chat_history.py`
- Modify: `education_brain/knowledge/api/routes/chat.py`
- Modify: `education_brain/knowledge/models/chat.py`
- Test: `education_brain/knowledge/tests/test_chat_history.py`
- Test: `education_brain/knowledge/tests/test_chat_routes.py`

- [ ] **Step 1: Write failing tests for session list and delete/clear behavior**

Add tests like:

```python
def test_list_sessions_returns_latest_activity_and_title(monkeypatch):
    sessions = chat_history.list_sessions(limit=20)
    assert sessions[0]["session_id"] == "s1"
    assert sessions[0]["title"] == "Python 怎么连接 MySQL？"
    assert "updated_at" in sessions[0]
```

```python
def test_clear_history_deletes_one_session(monkeypatch):
    deleted = chat_history.clear_history("s1")
    assert deleted == 2
```

```python
def test_chat_routes_expose_session_management_endpoints(client):
    assert client.get("/chat/sessions").status_code == 200
    assert client.delete("/chat/history/s1").status_code == 200
```

- [ ] **Step 2: Run the history/session tests and verify they fail**

Run:

```bash
cd /home/ccr/dev/LearningProject/education_brain
. knowledge/.venv/bin/activate
python -m pytest knowledge/tests/test_chat_history.py knowledge/tests/test_chat_routes.py -q
```

Expected: FAIL because the service/route helpers do not exist yet.

- [ ] **Step 3: Implement session listing and clear/delete in the history service**

In `knowledge/service/chat_history.py`, add focused helpers:

```python
def list_sessions(limit: int = 20) -> list[dict]:
    pipeline = [
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": "$session_id",
            "updated_at": {"$first": "$created_at"},
            "latest_message": {"$first": "$content"},
            "latest_role": {"$first": "$role"},
            "message_count": {"$sum": 1},
        }},
        {"$limit": limit},
    ]
    ...
```

```python
def clear_history(session_id: str) -> int:
    result = db["chat_history"].delete_many({"session_id": session_id})
    return result.deleted_count
```

Use latest user message content, falling back to latest message content, as the display title snippet.

- [ ] **Step 4: Expose the new endpoints in `knowledge/api/routes/chat.py`**

Add:

```python
@router.get("/sessions")
async def chat_sessions(limit: int = Query(default=20, ge=1, le=100)):
    sessions = await asyncio.to_thread(list_sessions, limit)
    return {"sessions": sessions}

@router.delete("/history/{session_id}")
async def clear_chat_history(session_id: str):
    deleted = await asyncio.to_thread(clear_history, session_id)
    return {"session_id": session_id, "deleted": deleted}
```

- [ ] **Step 5: Re-run the history tests and the chat smoke subset**

Run:

```bash
cd /home/ccr/dev/LearningProject/education_brain
. knowledge/.venv/bin/activate
python -m pytest knowledge/tests/test_chat_history.py knowledge/tests/test_chat_routes.py -q
curl -sS 'http://127.0.0.1:8000/chat/sessions?limit=5' | python3 -m json.tool | sed -n '1,120p'
```

Expected: PASS; the new endpoint returns `sessions`.

- [ ] **Step 6: Commit the chat session management backend**

```bash
cd /home/ccr/dev/LearningProject/education_brain
git add knowledge/service/chat_history.py knowledge/api/routes/chat.py knowledge/models/chat.py knowledge/tests/test_chat_history.py knowledge/tests/test_chat_routes.py
git commit -m "feat: add chat session management endpoints"
```

### Task 5: Update Frontend Types and API Adapters to Match the New Contracts

**Files:**
- Modify: `education_brain_front/src/app/types/index.ts`
- Modify: `education_brain_front/src/app/api/course.ts`
- Modify: `education_brain_front/src/app/api/question.ts`
- Modify: `education_brain_front/src/app/api/document.ts`
- Modify: `education_brain_front/src/app/api/chat.ts`
- Create: `education_brain_front/src/app/lib/chat-sessions.js`
- Test: `education_brain_front/src/app/lib/pagination.test.mjs`
- Test: `education_brain_front/src/app/lib/chat-sessions.test.mjs`

- [ ] **Step 1: Write the failing frontend helper tests for session title formatting**

Create `src/app/lib/chat-sessions.test.mjs`:

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { buildSessionTitle } from './chat-sessions.js'

test('buildSessionTitle trims long user messages for sidebar display', () => {
  assert.equal(buildSessionTitle('Python 怎么连接 MySQL 并配置连接池？'), 'Python 怎么连接 MySQL 并配置连接池？')
})
```

- [ ] **Step 2: Run the frontend helper tests and verify the new one fails**

Run:

```bash
cd /home/ccr/dev/LearningProject/education_brain_front
npm test
```

Expected: FAIL because `chat-sessions.js` does not exist yet.

- [ ] **Step 3: Extend the typed contracts**

In `src/app/types/index.ts`, add the new display fields:

```ts
export interface CourseSeriesItem {
  ...
  course_positioning: string
  prerequisites: string[]
  project_practice: string[]
  knowledge_points: string[]
}

export interface QuestionItem {
  ...
  series_code?: string
  series_title?: string
}

export interface DocumentChunk {
  ...
  series_title?: string
  source_path?: string
}

export interface ChatSessionSummary {
  session_id: string
  title: string
  updated_at: string
  message_count: number
}
```

- [ ] **Step 4: Update API adapters to preserve the new backend fields**

Examples:

```ts
// src/app/api/course.ts
course_positioning: item.course_positioning || '',
prerequisites: Array.isArray(item.prerequisites) ? item.prerequisites : [],
project_practice: Array.isArray(item.project_practice) ? item.project_practice : [],
knowledge_points: Array.isArray(item.knowledge_points) ? item.knowledge_points : [],
```

```ts
// src/app/api/chat.ts
export async function getChatSessions(limit = 20) {
  return http<{ sessions: ChatSessionSummary[] }>('GET', '/chat/sessions', { params: { limit } })
}

export async function clearChatHistory(sessionId: string) {
  return http<{ session_id: string; deleted: number }>('DELETE', `/chat/history/${sessionId}`)
}
```

- [ ] **Step 5: Create the small chat session helper and make tests pass**

Create `src/app/lib/chat-sessions.js`:

```js
export function buildSessionTitle(rawTitle) {
  const value = String(rawTitle || '').trim()
  if (!value) return '新对话'
  return value.length > 24 ? `${value.slice(0, 24)}...` : value
}
```

- [ ] **Step 6: Re-run frontend helper tests**

Run:

```bash
cd /home/ccr/dev/LearningProject/education_brain_front
npm test
```

Expected: PASS.

### Task 6: Finish the Frontend Display Work on Search Pages

**Files:**
- Modify: `education_brain_front/src/app/pages/courses-page.tsx`
- Modify: `education_brain_front/src/app/pages/questions-page.tsx`
- Modify: `education_brain_front/src/app/pages/documents-page.tsx`
- Create: `education_brain_front/src/app/components/source-metadata.tsx`

- [ ] **Step 1: Add a small reusable metadata display component**

Create `src/app/components/source-metadata.tsx`:

```tsx
interface SourceMetadataProps {
  label: string
  value?: string | null
}

export function SourceMetadata({ label, value }: SourceMetadataProps) {
  if (!value) return null
  return (
    <div className="text-xs text-muted-foreground">
      <span className="mr-1">{label}:</span>
      <span>{value}</span>
    </div>
  )
}
```

- [ ] **Step 2: Extend the course page filters and detail sections**

Update `courses-page.tsx` to include fields for:

```tsx
const [projectName, setProjectName] = useState('')
const [knowledgePoint, setKnowledgePoint] = useState('')
const [audience, setAudience] = useState('')
const [goalTag, setGoalTag] = useState('')
```

Pass them to `getCourses(...)`, and in the detail drawer add sections:

```tsx
{selected.positioning && <DetailSection title="课程定位" items={[selected.positioning]} />}
{selected.prerequisites.length > 0 && <DetailSection title="先修要求" items={selected.prerequisites} />}
{selected.projectPractice.length > 0 && <DetailSection title="项目实战" items={selected.projectPractice} />}
{selected.knowledgePoints.length > 0 && <DetailSection title="知识点" items={selected.knowledgePoints} />}
```

- [ ] **Step 3: Extend the question page provenance display**

In `questions-page.tsx`, add a compact provenance row under the tags:

```tsx
<div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
  <span>题目编码：{q.id}</span>
  {q.seriesTitle && <span>课程归属：{q.seriesTitle}</span>}
  <span>题库编码：{q.bankCode}</span>
</div>
```

- [ ] **Step 4: Extend the document page provenance display**

In `documents-page.tsx`, show richer sources:

```tsx
<div className="grid gap-1 rounded-md bg-muted/30 p-3">
  <SourceMetadata label="课程" value={chunk.series_title} />
  <SourceMetadata label="项目" value={chunk.source_mapping.project_name} />
  <SourceMetadata label="文件" value={chunk.source_file} />
  <SourceMetadata label="路径" value={chunk.source_path} />
</div>
```

- [ ] **Step 5: Build the frontend and verify the search pages compile cleanly**

Run:

```bash
cd /home/ccr/dev/LearningProject/education_brain_front
npm run build
```

Expected: PASS.

### Task 7: Finish Chat History Management in the Frontend

**Files:**
- Modify: `education_brain_front/src/app/pages/chat-page.tsx`
- Modify: `education_brain_front/src/app/api/chat.ts`
- Modify: `education_brain_front/src/app/types/index.ts`

- [ ] **Step 1: Replace localStorage-only session IDs with backend-backed session summaries**

In `chat-page.tsx`, replace:

```tsx
const [sessions, setSessions] = useState<string[]>(...)
```

with:

```tsx
const [sessions, setSessions] = useState<ChatSessionSummary[]>([])
```

Load them from `getChatSessions()` on mount and after sending/deleting.

- [ ] **Step 2: Add sidebar display fields and actions**

Render each session with title + last updated time:

```tsx
<div className="flex flex-col text-left">
  <span className="truncate">{buildSessionTitle(session.title)}</span>
  <span className="text-[11px] text-muted-foreground">
    {new Date(session.updated_at).toLocaleString()}
  </span>
</div>
```

Add delete/clear action buttons:

```tsx
<button onClick={() => handleDeleteSession(session.session_id)}>删除</button>
<button onClick={() => handleClearActiveSession()}>清空当前会话</button>
```

- [ ] **Step 3: Handle destructive actions safely in UI state**

Implement:

```tsx
const handleDeleteSession = async (sessionId: string) => {
  await clearChatHistory(sessionId)
  const next = sessions.filter((item) => item.session_id !== sessionId)
  setSessions(next)
  if (activeSession === sessionId) {
    setActiveSession(next[0]?.session_id || `session_web_${Date.now()}`)
    setMessages([])
  }
}
```

- [ ] **Step 4: Rebuild the frontend and do a manual smoke walkthrough**

Run:

```bash
cd /home/ccr/dev/LearningProject/education_brain_front
npm run build
```

Then manually verify:

1. Open `/`
2. See server-backed session list
3. Delete a non-active session
4. Clear the active session
5. Send a message and confirm the session list refreshes

Expected: all actions work without console errors.

### Task 8: Final Verification and Documentation Refresh

**Files:**
- Modify: `education_brain/docs/api-reference.md`
- Modify: `education_brain/docs/env-setup.md`
- Modify: `education_brain/AGENTS.md`

- [ ] **Step 1: Update API docs for the new display contracts**

Document:
- new `/search/courses` filters: `project_name`, `knowledge_point`
- new course response fields
- new question provenance fields
- new document provenance fields
- new chat endpoints: `GET /chat/sessions`, `DELETE /chat/history/{session_id}`

- [ ] **Step 2: Run the backend and frontend verification commands**

Run:

```bash
cd /home/ccr/dev/LearningProject/education_brain
. knowledge/.venv/bin/activate
python -m pytest knowledge/tests/test_catalog_parser.py knowledge/tests/test_course_search.py knowledge/tests/test_document_search.py knowledge/tests/test_question_search.py knowledge/tests/test_chat_history.py knowledge/tests/test_chat_routes.py -q

cd /home/ccr/dev/LearningProject/education_brain_front
npm test
npm run build
```

Expected: all PASS.

- [ ] **Step 3: Do an end-to-end smoke pass in a browser**

Verify:
1. Course search can filter by audience/goal/project/knowledge point and detail drawer shows new sections.
2. Question search shows coding/provenance metadata.
3. Document search shows richer source info.
4. Chat sidebar lists sessions with title/time and supports delete/clear.

- [ ] **Step 4: Commit the backend doc updates**

```bash
cd /home/ccr/dev/LearningProject/education_brain
git add docs/api-reference.md docs/env-setup.md AGENTS.md
git commit -m "docs: describe enriched display contracts"
```

## Implementation Notes for the Assigned Engineer

- Follow `@test-driven-development` strictly for backend behavior changes. Do not add backend implementation code before the focused failing test exists.
- Keep frontend-only logic small and reusable. If a display rule can be tested as a pure helper, extract it into `src/app/lib/*.js` and cover it with the node test runner.
- Do not invent course detail content in the frontend. If the source catalog does not contain a field, the backend should return an empty value and the frontend should omit that section cleanly.
- Do not bolt course attribution into the frontend by guessing from strings. Use explicit backend fields like `series_code`, `series_title`, `project_name`, and `source_file`.
- Preserve current route structure and existing page layout. This is a display enrichment pass, not a redesign.

