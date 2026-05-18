# Smart Chat Tone And Routing Design

**Date:** 2026-04-19

**Scope:** Backend-only changes for the intelligent chat feature in `knowledge`

## Goal

Make chat feel like a teaching assistant instead of a rigid retrieval engine while preserving source-grounded behavior for knowledge answers.

## User Decisions

- The system should support two styles at once.
- Course and question requests should feel like assistant guidance.
- Knowledge answers should remain evidence-based.
- When sources are partial, the assistant should explain clearly and distinguish source-backed content from model supplementation.

## Current Problems

1. `knowledge` answers are overly rigid.
   They often start with source disclaimers and interleave citations directly inside sentences, which makes answers read like retrieval dumps.
2. `course_intro` and `question_search` replies are too mechanical.
   They list results, but do not actively respond like an assistant fulfilling the user’s request.
3. Intent routing is too weak around course-seeking phrases such as `XX课程`.
   Some course-discovery requests can fall through to `knowledge`, causing concept explanations where users expected course lookup.

## Design

### 1. Dual-track answer behavior

Two response tracks will be kept intentionally separate:

- `course_intro` and `question_search`
  Use deterministic formatter-based assistant copy. No LLM generation is needed for these structured lookups.
- `knowledge`
  Use LLM answer generation with a stricter answer contract:
  - Start with a direct, natural explanation
  - Then show source-backed points
  - Then optionally show model supplementation with explicit labeling

### 2. Structured search reply style

For `course_intro`:

- Start by directly fulfilling the request, for example:
  - `先给你筛到 3 门更贴近 Python 的课程：`
  - `没找到完全同名课程，但这些课程和“大模型开发”最接近：`
- Keep the current structured items payload unchanged.
- Make no-result messages suggest the next action instead of cold rejection.

For `question_search`:

- Start by acknowledging the user request, for example:
  - `先给你 5 道多选题：`
  - `先给你 5 道和 Python 相关的题目：`
- If filters are too narrow, no-result copy should suggest relaxing conditions:
  - keep keyword only
  - switch question type
  - try another nearby term

### 3. Knowledge answer contract

`knowledge` answers should follow this structure:

1. `直接回答`
   Explain the concept naturally, without opening with `基于资料` or `资料中未包含`.
2. `资料依据`
   Summarize what the retrieved materials directly support.
3. `模型补充`
   Only when needed. Mark it clearly as supplementation beyond direct course material support.

Citation usage changes:

- Avoid inserting `[来源: ...]` into every sentence.
- Prefer grouped citation lines at the end of a bullet or section.
- Keep the machine-readable `citations` payload unchanged for the frontend.

### 4. Intent-routing adjustment

The rule-based classifier should more aggressively map explicit course-seeking phrases to `course_intro`, including:

- `XX课程`
- `大模型开发课程`
- `有没有相关课`
- `推荐一些 ... 课程`

Question-seeking phrases should continue to take priority over `knowledge`.

### 5. Logging policy

Existing fallback logs such as `返回空 content，尝试走 Ollama /api/chat no-think 回退` can remain for now because they are useful during integration.
This round does not redesign logging levels unless the implementation shows obvious noise worth trimming.

## Files Expected To Change

- `knowledge/prompt/query_prompt.py`
- `knowledge/service/intent_classifier.py`
- `knowledge/service/chat_formatter.py`
- `knowledge/service/chat_sync.py`
- `knowledge/tests/test_chat_formatter.py`
- `knowledge/tests/test_chat_routes.py`
- `knowledge/tests/test_chat_stream.py` only if needed

## Testing Strategy

- Add formatter tests for assistant-style course and question summaries.
- Add route/classifier tests for `大模型开发课程` style course discovery.
- Add prompt contract tests at the answer-generation level to verify the new structure and wording expectations.
- Run targeted pytest files and one real `/chat/query/stream` smoke check.
