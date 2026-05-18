# Smart Chat Tone And Routing Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make intelligent chat feel more like a teaching assistant for course/question lookups and less rigid for knowledge answers, without changing the frontend contract.

**Architecture:** Keep structured search intents deterministic through formatter templates, and improve only the `knowledge` answer-generation contract through prompt changes. Strengthen intent routing for explicit course-seeking phrases so course requests do not accidentally fall into generic knowledge QA.

**Tech Stack:** FastAPI backend, pytest, deterministic formatter helpers, Ollama-backed LLM prompts

---

### Task 1: Lock Down Expected Formatter Behavior

**Files:**
- Modify: `knowledge/tests/test_chat_formatter.py`
- Test: `knowledge/tests/test_chat_formatter.py`

- [ ] **Step 1: Write failing tests for course and question assistant copy**

Add tests that expect:
- course summaries to start with direct assistant guidance
- no-result course summaries to suggest next actions
- question summaries to acknowledge requested question type
- no-result question summaries to suggest relaxing filters

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=/home/ccr/dev/LearningProject/education_brain /home/ccr/dev/LearningProject/education_brain/knowledge/.venv/bin/python -m pytest /home/ccr/dev/LearningProject/education_brain/knowledge/tests/test_chat_formatter.py -q`
Expected: FAIL because the formatter still uses rigid summary strings.

- [ ] **Step 3: Implement minimal formatter changes**

Update `knowledge/service/chat_formatter.py` to provide deterministic assistant-style copy for course and question lookup summaries.

- [ ] **Step 4: Run test to verify it passes**

Run the same pytest command.
Expected: PASS

### Task 2: Strengthen Course Intent Routing

**Files:**
- Modify: `knowledge/tests/test_chat_routes.py`
- Modify: `knowledge/service/intent_classifier.py`
- Test: `knowledge/tests/test_chat_routes.py`

- [ ] **Step 1: Write a failing routing test**

Add a test that `大模型开发课程` or similar explicit course-seeking input resolves to `course_intro`.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=/home/ccr/dev/LearningProject/education_brain /home/ccr/dev/LearningProject/education_brain/knowledge/.venv/bin/python -m pytest /home/ccr/dev/LearningProject/education_brain/knowledge/tests/test_chat_routes.py -q`
Expected: FAIL because the current regex rules do not catch the phrase reliably enough.

- [ ] **Step 3: Implement minimal rule updates**

Adjust `knowledge/service/intent_classifier.py` rule patterns so explicit `课程/课/班` discovery phrases map to `course_intro` before generic knowledge fallback.

- [ ] **Step 4: Run test to verify it passes**

Run the same pytest command.
Expected: PASS

### Task 3: Improve Knowledge Answer Contract

**Files:**
- Modify: `knowledge/tests/test_chat_stream.py`
- Modify: `knowledge/prompt/query_prompt.py`
- Modify: `knowledge/service/chat_sync.py` only if a formatting helper is needed
- Test: `knowledge/tests/test_chat_stream.py`

- [ ] **Step 1: Write a failing contract test**

Add a test that inspects the knowledge-answer prompt or generated answer flow and checks for the expected structure:
- direct explanation first
- source-backed section
- optional model-supplement section

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=/home/ccr/dev/LearningProject/education_brain /home/ccr/dev/LearningProject/education_brain/knowledge/.venv/bin/python -m pytest /home/ccr/dev/LearningProject/education_brain/knowledge/tests/test_chat_stream.py -q`
Expected: FAIL because the current prompt still instructs rigid inline citation behavior.

- [ ] **Step 3: Implement minimal prompt changes**

Update `knowledge/prompt/query_prompt.py` so knowledge answers:
- do not open with retrieval disclaimers
- group source evidence in a separate section
- clearly label supplementation beyond direct source coverage

- [ ] **Step 4: Run test to verify it passes**

Run the same pytest command.
Expected: PASS

### Task 4: Wire Formatter Updates Into Structured Intents

**Files:**
- Modify: `knowledge/service/chat_sync.py`
- Modify: `knowledge/service/chat_formatter.py`
- Test: `knowledge/tests/test_chat_routes.py`

- [ ] **Step 1: Write or extend a failing route-level test**

Add assertions that structured search responses still populate `summary`, `answer`, and `items`, but now use the new assistant-style text.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=/home/ccr/dev/LearningProject/education_brain /home/ccr/dev/LearningProject/education_brain/knowledge/.venv/bin/python -m pytest /home/ccr/dev/LearningProject/education_brain/knowledge/tests/test_chat_routes.py -q`
Expected: FAIL because `handle_question` still builds rigid raw lines.

- [ ] **Step 3: Implement minimal integration changes**

Move question summary generation into formatter helpers and keep the `ChatResponse` payload shape backward compatible.

- [ ] **Step 4: Run test to verify it passes**

Run the same pytest command.
Expected: PASS

### Task 5: Full Verification And Smoke Check

**Files:**
- No code changes required unless verification finds a regression

- [ ] **Step 1: Run targeted backend tests**

Run:
`PYTHONPATH=/home/ccr/dev/LearningProject/education_brain /home/ccr/dev/LearningProject/education_brain/knowledge/.venv/bin/python -m pytest /home/ccr/dev/LearningProject/education_brain/knowledge/tests/test_chat_formatter.py /home/ccr/dev/LearningProject/education_brain/knowledge/tests/test_chat_routes.py /home/ccr/dev/LearningProject/education_brain/knowledge/tests/test_chat_stream.py -q`

Expected: PASS

- [ ] **Step 2: Run a real chat smoke check**

Submit a real `POST /chat/query/stream` request for:
- one course-seeking query
- one question-seeking query
- one knowledge query

Expected:
- course query returns `course_intro`
- question query returns `question_search`
- knowledge query streams a natural answer instead of rigid disclaimer-led text

- [ ] **Step 3: Review diff and summarize backend-only impact**

Check `git diff -- knowledge/...` and verify no unrelated files were changed by this task.
