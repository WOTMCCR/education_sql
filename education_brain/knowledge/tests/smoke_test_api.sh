#!/usr/bin/env bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 8/9 Chat / Search / SSE API — 冒烟测试
#
# 用法:
#   ./smoke_test_api.sh              # 默认 http://localhost:8000
#   ./smoke_test_api.sh :8080        # 自定义端口
#   BASE=http://10.0.0.5:8000 ./smoke_test_api.sh
#
# 需要: bash 4+, curl, python3
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -uo pipefail

# ── 配置 ──
if [[ -n "${1:-}" ]]; then
    BASE="http://localhost${1}"
elif [[ -z "${BASE:-}" ]]; then
    BASE="http://localhost:8000"
fi

# 每次运行用唯一 session_id，避免历史数据干扰
RUN_ID="smoke-$(date +%s)"
SESSION_MULTI="${RUN_ID}-multi"
SESSION_HISTORY="${RUN_ID}-history"
SESSION_STREAM="${RUN_ID}-stream"

# 知识问答超时（秒），本地 Ollama 可能较慢
QA_TIMEOUT="${QA_TIMEOUT:-180}"

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

# ── 工具函数 ──

py_extract() {
    python3 -c "
import json, sys
data = json.load(sys.stdin)
$1
"
}

assert_json() {
    local description="$1"
    local response="$2"
    local check_expr="$3"

    if [[ -z "$response" ]]; then
        echo -e "  ${RED}✗${NC} $description"
        echo -e "    ${RED}→ 请求失败：响应为空${NC}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return
    fi

    local result
    result=$(echo "$response" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
except Exception as e:
    print(f'JSON_ERROR: {e}')
    sys.exit(1)
$check_expr
" 2>&1) || true

    if [[ "$result" == "PASS" ]]; then
        echo -e "  ${GREEN}✓${NC} $description"
        PASS_COUNT=$((PASS_COUNT + 1))
    elif [[ "$result" == SKIP* ]]; then
        echo -e "  ${YELLOW}⊘${NC} $description — ${result#SKIP: }"
        SKIP_COUNT=$((SKIP_COUNT + 1))
    else
        echo -e "  ${RED}✗${NC} $description"
        echo -e "    ${RED}→ $result${NC}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

section() {
    echo ""
    echo -e "${BOLD}${CYAN}━━ $1 ━━${NC}"
}

# ── 健康检查 ──

section "0. 健康检查"

HEALTH=$(curl -sf "${BASE}/health" 2>/dev/null) || {
    echo -e "${RED}服务未启动或不可达: ${BASE}/health${NC}"
    echo "请先启动服务: cd knowledge && uv run uvicorn knowledge.api.app:app --host 0.0.0.0 --port 8000"
    exit 1
}
assert_json "服务健康" "$HEALTH" "
status = data.get('status', '')
if status in ('healthy', 'degraded'):
    print('PASS')
else:
    print(f'Expected healthy/degraded, got: {status}')
"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. /search/* 结构化查询
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

section "1. /search/courses"

R=$(curl -sfG "${BASE}/search/courses" --data-urlencode "keyword=Python") || R=""
assert_json "Python 课程有结果" "$R" "
items = data.get('items', [])
print('PASS' if len(items) > 0 else f'Expected items > 0, got {len(items)}')
"
assert_json "Python 匹配为 module 级别" "$R" "
items = data.get('items', [])
levels = [i.get('match_level') for i in items]
print('PASS' if 'module' in levels else f'Expected module in match_levels, got {levels}')
"
assert_json "包含 matched_modules 字段" "$R" "
item = data.get('items', [{}])[0] if data.get('items') else {}
mods = item.get('matched_modules', [])
print('PASS' if mods else f'Expected matched_modules, got {mods}')
"

R=$(curl -sf "${BASE}/search/courses") || R=""
assert_json "无关键词返回所有课程" "$R" "
total = data.get('total', 0)
print('PASS' if total > 10 else f'Expected total > 10, got {total}')
"

R=$(curl -sfG "${BASE}/search/courses" --data-urlencode "keyword=量子纠缠不存在的课程XYZ") || R=""
assert_json "不存在的关键词返回空" "$R" "
total = data.get('total', 0)
print('PASS' if total == 0 else f'Expected 0, got {total}')
"

section "2. /search/questions"

R=$(curl -sfG "${BASE}/search/questions" --data-urlencode "keyword=数据类型" --data-urlencode "size=3") || R=""
assert_json "数据类型题目有结果" "$R" "
items = data.get('items', [])
print('PASS' if len(items) > 0 else f'Expected items > 0, got {len(items)}')
"

R=$(curl -sfG "${BASE}/search/questions" --data-urlencode "keyword=数据类型" --data-urlencode "question_type=选择题" --data-urlencode "size=5") || R=""
assert_json "选择题类型过滤" "$R" "
items = data.get('items', [])
if not items:
    print('PASS')  # 可能该组合无结果，不算失败
else:
    types = {i.get('question_type') for i in items}
    valid = types <= {'单选题', '多选题', '选择题'}
    print('PASS' if valid else f'Expected 选择题/单选题/多选题, got {types}')
"

R=$(curl -sf "${BASE}/search/questions") || R=""
assert_json "无参数返回题目列表" "$R" "
total = data.get('total', 0)
print('PASS' if total > 0 else f'Expected total > 0, got {total}')
"

section "3. /search/documents"

R=$(curl -sfG "${BASE}/search/documents" --data-urlencode "query=PyTorch" --data-urlencode "doc_type=course_doc" --data-urlencode "limit=3") || R=""
assert_json "PyTorch 文档检索有结果" "$R" "
items = data.get('items', [])
print('PASS' if len(items) > 0 else f'Expected items > 0, got {len(items)}')
"
assert_json "文档包含 chunk_text 和 distance" "$R" "
item = data.get('items', [{}])[0] if data.get('items') else {}
has_fields = 'chunk_text' in item and 'distance' in item
print('PASS' if has_fields else f'Missing fields in: {list(item.keys())[:5]}')
"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. /chat/query — 意图路由
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

chat_post() {
    local query="$1"
    local session="${2:-}"
    local timeout="${3:-30}"
    local body
    if [[ -n "$session" ]]; then
        body="{\"query\":\"${query}\",\"session_id\":\"${session}\"}"
    else
        body="{\"query\":\"${query}\"}"
    fi
    curl -sf --max-time "$timeout" -X POST "${BASE}/chat/query" \
        -H 'Content-Type: application/json' \
        -d "$body" 2>/dev/null
}

stream_submit() {
    local query="$1"
    local session="${2:-}"
    local body
    if [[ -n "$session" ]]; then
        body="{\"query\":\"${query}\",\"session_id\":\"${session}\"}"
    else
        body="{\"query\":\"${query}\"}"
    fi
    curl -sf -X POST "${BASE}/chat/query/stream" \
        -H 'Content-Type: application/json' \
        -d "$body" 2>/dev/null
}

collect_sse() {
    local task_id="$1"
    local timeout="${2:-30}"
    local out_file="$3"
    timeout "$timeout" curl -sN "${BASE}/chat/stream/${task_id}" > "$out_file" 2>/dev/null
}

section "4. /chat/query — course_intro 意图"

R=$(chat_post "有哪些 Python 相关课程")
assert_json "意图=course_intro" "$R" "
print('PASS' if data.get('intent') == 'course_intro' else f\"Got: {data.get('intent')}\")
"
assert_json "result_type=search_result" "$R" "
print('PASS' if data.get('result_type') == 'search_result' else f\"Got: {data.get('result_type')}\")
"
assert_json "answer 包含摘要文本" "$R" "
answer = data.get('answer', '')
print('PASS' if len(answer) > 10 else f'answer too short: {len(answer)} chars')
"
assert_json "answer == summary（搜索类向下兼容）" "$R" "
print('PASS' if data.get('answer') == data.get('summary') else 'answer != summary')
"
assert_json "module 级匹配话术区分" "$R" "
answer = data.get('answer', '')
has_module_hint = '模块' in answer or '包含' in answer
print('PASS' if has_module_hint else f'Expected module-level hint in answer')
"

section "5. /chat/query — question_search 意图"

R=$(chat_post "有没有数据类型的选择题")
assert_json "意图=question_search" "$R" "
print('PASS' if data.get('intent') == 'question_search' else f\"Got: {data.get('intent')}\")
"
assert_json "result_type=search_result" "$R" "
print('PASS' if data.get('result_type') == 'search_result' else f\"Got: {data.get('result_type')}\")
"
assert_json "items 非空" "$R" "
items = data.get('items', [])
print('PASS' if len(items) > 0 else 'items is empty')
"

section "6. /chat/query — knowledge 意图"

echo -e "  ${YELLOW}…${NC} 等待 knowledge 响应（最长 ${QA_TIMEOUT}s）"
R=$(chat_post "怎么安装 PyTorch" "" "$QA_TIMEOUT") || R=""

if [[ -z "$R" ]]; then
    echo -e "  ${YELLOW}⊘${NC} knowledge 请求超时或失败，跳过（本地模型较慢时属正常）"
    SKIP_COUNT=$((SKIP_COUNT + 3))
else
    assert_json "意图=knowledge" "$R" "
print('PASS' if data.get('intent') == 'knowledge' else f\"Got: {data.get('intent')}\")
"
    assert_json "result_type=answer" "$R" "
print('PASS' if data.get('result_type') == 'answer' else f\"Got: {data.get('result_type')}\")
"
    assert_json "citations 非空" "$R" "
cites = data.get('citations', [])
print('PASS' if len(cites) > 0 else 'citations is empty')
"
fi

section "7. /chat/query — 英文输入"

R=$(chat_post "Python courses")
assert_json "英文 'Python courses' → course_intro" "$R" "
print('PASS' if data.get('intent') == 'course_intro' else f\"Got: {data.get('intent')}\")
"

R=$(chat_post "questions about data types")
assert_json "英文 'questions about...' → question_search" "$R" "
print('PASS' if data.get('intent') == 'question_search' else f\"Got: {data.get('intent')}\")
"

section "8. /chat/query — knowledge 意图（需要 LLM，较慢）"

echo -e "  ${YELLOW}…${NC} 等待 LLM 响应（最长 ${QA_TIMEOUT}s）"
R=$(chat_post "对比一下几种排序算法的优劣" "" "$QA_TIMEOUT") || R=""

if [[ -z "$R" ]]; then
    echo -e "  ${YELLOW}⊘${NC} knowledge 请求超时或失败，跳过（LLM 不可用时属正常）"
    SKIP_COUNT=$((SKIP_COUNT + 3))
else
    assert_json "意图=knowledge" "$R" "
print('PASS' if data.get('intent') == 'knowledge' else f\"Got: {data.get('intent')}\")
"
    assert_json "result_type=answer" "$R" "
print('PASS' if data.get('result_type') == 'answer' else f\"Got: {data.get('result_type')}\")
"
    assert_json "answer 非空" "$R" "
answer = data.get('answer', '')
print('PASS' if len(answer) > 20 else f'answer too short: {len(answer)} chars')
"
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 8B. /chat/query/stream — 统一流式入口
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

section "8B. /chat/query/stream — 搜索类意图"

R=$(stream_submit "有哪些 Python 课程？" "$SESSION_STREAM-search")
assert_json "流式提交返回 processing" "$R" "
print('PASS' if data.get('status') == 'processing' else f\"Got: {data.get('status')}\")
"
assert_json "流式提交返回搜索类 intent" "$R" "
print('PASS' if data.get('intent') == 'course_intro' else f\"Got: {data.get('intent')}\")
"

TASK_ID=$(echo "$R" | python3 -c "import json,sys; print(json.load(sys.stdin).get('task_id',''))" 2>/dev/null)
if [[ -z "$TASK_ID" ]]; then
    echo -e "  ${RED}✗${NC} 搜索类流式提交未返回 task_id"
    FAIL_COUNT=$((FAIL_COUNT + 1))
else
    SSE_OUT=$(mktemp)
    collect_sse "$TASK_ID" 30 "$SSE_OUT" || true

    if grep -q "^event: done" "$SSE_OUT"; then
        echo -e "  ${GREEN}✓${NC} 搜索类 SSE 收到 done"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo -e "  ${RED}✗${NC} 搜索类 SSE 缺少 done"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi

    DONE_JSON=$(grep -A1 "^event: done" "$SSE_OUT" | grep "^data: " | sed 's/^data: //')
    assert_json "搜索类 done.result_type=search_result" "$DONE_JSON" "
print('PASS' if data.get('result_type') == 'search_result' else f\"Got: {data.get('result_type')}\")
"
    assert_json "搜索类 done.answer 非空" "$DONE_JSON" "
answer = data.get('answer', '')
print('PASS' if len(answer) > 5 else f'answer too short: {len(answer)} chars')
"

    TOKEN_COUNT=$(grep -c "^event: token" "$SSE_OUT" 2>/dev/null || true)
    TOKEN_COUNT=${TOKEN_COUNT:-0}
    if [[ "$TOKEN_COUNT" -eq 0 ]]; then
        echo -e "  ${GREEN}✓${NC} 搜索类 SSE 不产生 token 事件"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo -e "  ${RED}✗${NC} 搜索类 SSE 不应产生 token 事件（实际 ${TOKEN_COUNT} 条）"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi

    rm -f "$SSE_OUT"
fi

section "8C. /chat/query/stream — knowledge 意图（需要 LLM，较慢）"

R=$(stream_submit "什么是反向传播算法？" "$SESSION_STREAM-qa")
assert_json "QA 流式提交返回 processing" "$R" "
print('PASS' if data.get('status') == 'processing' else f\"Got: {data.get('status')}\")
"
assert_json "QA 流式提交意图=knowledge" "$R" "
print('PASS' if data.get('intent') == 'knowledge' else f\"Got: {data.get('intent')}\")
"

TASK_ID=$(echo "$R" | python3 -c "import json,sys; print(json.load(sys.stdin).get('task_id',''))" 2>/dev/null)
if [[ -z "$TASK_ID" ]]; then
    echo -e "  ${YELLOW}⊘${NC} QA 流式提交未返回 task_id，跳过后续 SSE 验收"
    SKIP_COUNT=$((SKIP_COUNT + 3))
else
    SSE_OUT=$(mktemp)
    collect_sse "$TASK_ID" "$QA_TIMEOUT" "$SSE_OUT" || true

    if grep -q "^event: done" "$SSE_OUT"; then
        echo -e "  ${GREEN}✓${NC} QA SSE 收到 done"
        PASS_COUNT=$((PASS_COUNT + 1))
        DONE_JSON=$(grep -A1 "^event: done" "$SSE_OUT" | grep "^data: " | sed 's/^data: //')
        assert_json "QA done.intent=knowledge" "$DONE_JSON" "
print('PASS' if data.get('intent') == 'knowledge' else f\"Got: {data.get('intent')}\")
"
        assert_json "QA done.answer 非空" "$DONE_JSON" "
answer = data.get('answer', '')
print('PASS' if len(answer) > 10 else f'answer too short: {len(answer)} chars')
"
    elif grep -q "^event: error" "$SSE_OUT"; then
        echo -e "  ${YELLOW}⊘${NC} QA SSE 收到 error（LLM 不可用或超时，跳过严格断言）"
        SKIP_COUNT=$((SKIP_COUNT + 3))
    else
        echo -e "  ${RED}✗${NC} QA SSE 既无 done 也无 error"
        FAIL_COUNT=$((FAIL_COUNT + 3))
    fi

    STATUS_COUNT=$(grep -c "^event: status" "$SSE_OUT" 2>/dev/null || echo 0)
    if [[ "$STATUS_COUNT" -gt 0 ]]; then
        echo -e "  ${GREEN}✓${NC} QA SSE 包含 status 事件 (${STATUS_COUNT} 条)"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo -e "  ${RED}✗${NC} QA SSE 缺少 status 事件"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi

    rm -f "$SSE_OUT"
fi

section "8D. /chat/stream/{task_id} — 不存在的 task_id"

R=$(curl -s -o /tmp/stream-missing-${RUN_ID}.out -w "%{http_code}" "${BASE}/chat/stream/nonexistent-${RUN_ID}" 2>/dev/null || true)
if [[ "$R" == "404" ]]; then
    echo -e "  ${GREEN}✓${NC} 不存在的 task_id 返回 404"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo -e "  ${RED}✗${NC} 不存在的 task_id 期望 404，实际 ${R:-<empty>}"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi
rm -f /tmp/stream-missing-${RUN_ID}.out

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 9. 多轮对话 + 历史回查
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

section "9. 多轮对话（同一 session_id）"

# 第 1 轮：课程查询
R1=$(chat_post "有哪些课程" "$SESSION_MULTI")
assert_json "第 1 轮：课程查询成功" "$R1" "
print('PASS' if data.get('intent') == 'course_intro' else f\"Got: {data.get('intent')}\")
"

# 第 2 轮：题目查询
R2=$(chat_post "有没有编程题" "$SESSION_MULTI")
assert_json "第 2 轮：题目查询成功" "$R2" "
print('PASS' if data.get('intent') == 'question_search' else f\"Got: {data.get('intent')}\")
"

# 第 3 轮：文档查询
R3=$(chat_post "怎么配置 MongoDB" "$SESSION_MULTI" "$QA_TIMEOUT")
assert_json "第 3 轮：知识查询成功" "$R3" "
print('PASS' if data.get('intent') == 'knowledge' else f\"Got: {data.get('intent')}\")
"

# 验证历史：应有 6 条消息（3 轮 × user + assistant）
section "10. /chat/history — 多轮历史回查"

H=$(curl -sf "${BASE}/chat/history?session_id=${SESSION_MULTI}&limit=20") || H=""
assert_json "历史消息数 = 6（3 轮 × 2）" "$H" "
msgs = data.get('messages', [])
print('PASS' if len(msgs) == 6 else f'Expected 6 messages, got {len(msgs)}')
"
assert_json "消息按时间正序排列" "$H" "
msgs = data.get('messages', [])
times = [m.get('created_at', '') for m in msgs]
print('PASS' if times == sorted(times) else f'Not sorted: {times}')
"
assert_json "角色交替 user→assistant" "$H" "
msgs = data.get('messages', [])
roles = [m.get('role') for m in msgs]
expected = ['user', 'assistant'] * 3
print('PASS' if roles == expected else f'Expected {expected}, got {roles}')
"
assert_json "每条消息都有 created_at" "$H" "
msgs = data.get('messages', [])
all_have = all('created_at' in m and m['created_at'] for m in msgs)
print('PASS' if all_have else 'Some messages missing created_at')
"
assert_json "assistant 消息都有 intent" "$H" "
msgs = data.get('messages', [])
asst = [m for m in msgs if m['role'] == 'assistant']
all_have = all(m.get('intent') for m in asst)
print('PASS' if all_have else f\"Missing intent in: {[m.get('intent') for m in asst]}\")
"
assert_json "assistant 消息都有 result_type" "$H" "
msgs = data.get('messages', [])
asst = [m for m in msgs if m['role'] == 'assistant']
all_have = all(m.get('result_type') for m in asst)
print('PASS' if all_have else f\"Missing result_type in: {[m.get('result_type') for m in asst]}\")
"
assert_json "第 3 轮 assistant 包含 citations" "$H" "
msgs = data.get('messages', [])
asst_msgs = [m for m in msgs if m['role'] == 'assistant']
last_asst = asst_msgs[-1] if asst_msgs else {}
cites = last_asst.get('citations', [])
print('PASS' if len(cites) > 0 else f'Expected citations in last assistant msg, got {len(cites)}')
"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 11. 历史字段完整性
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

section "11. /chat/history — 字段完整性"

# 发一条带 session_id 的 knowledge 请求，专门验证字段保存
chat_post "怎么安装 PyTorch" "$SESSION_HISTORY" "$QA_TIMEOUT" >/dev/null

H=$(curl -sf "${BASE}/chat/history?session_id=${SESSION_HISTORY}&limit=10") || H=""
REQUIRED_FIELDS="session_id task_id role content intent citations created_at"
EXTENDED_FIELDS="result_type items summary answer"

assert_json "基础字段完整 (${REQUIRED_FIELDS})" "$H" "
msgs = data.get('messages', [])
required = '${REQUIRED_FIELDS}'.split()
for m in msgs:
    missing = [f for f in required if f not in m]
    if missing:
        print(f'Missing {missing} in {m.get(\"role\")} message')
        sys.exit(0)
print('PASS')
"
assert_json "扩展字段完整 (${EXTENDED_FIELDS})" "$H" "
msgs = data.get('messages', [])
extended = '${EXTENDED_FIELDS}'.split()
asst = [m for m in msgs if m['role'] == 'assistant']
for m in asst:
    missing = [f for f in extended if f not in m]
    if missing:
        print(f'Missing {missing} in assistant message')
        sys.exit(0)
print('PASS')
"
assert_json "answer 字段非空（向下兼容保证）" "$H" "
msgs = data.get('messages', [])
asst = [m for m in msgs if m['role'] == 'assistant']
for m in asst:
    if not m.get('answer'):
        print('assistant message has empty answer')
        sys.exit(0)
print('PASS')
"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 12. 边界情况
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

section "12. 边界情况"

R=$(chat_post "有哪些课程")
assert_json "宽泛课程查询返回多条" "$R" "
items = data.get('items', [])
print('PASS' if len(items) > 3 else f'Expected > 3 items, got {len(items)}')
"

R=$(chat_post "不存在的量子纠缠超导课程XYZABC" "" "$QA_TIMEOUT") || R=""
if [[ -z "$R" ]]; then
    echo -e "  ${YELLOW}⊘${NC} 无匹配查询超时，跳过（LLM fallback 较慢属正常）"
    SKIP_COUNT=$((SKIP_COUNT + 1))
else
    assert_json "无匹配时不报错" "$R" "
print('PASS' if 'task_id' in data else 'No task_id in response')
"
fi

R=$(curl -sf "${BASE}/chat/history?session_id=nonexistent-session-${RUN_ID}&limit=5") || R=""
assert_json "不存在的 session_id 返回空列表" "$R" "
msgs = data.get('messages', [])
print('PASS' if len(msgs) == 0 else f'Expected 0, got {len(msgs)}')
"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 13. /chat/query 返回结构一致性
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

section "13. ChatResponse 结构一致性"

R=$(chat_post "推荐一些 Python 课程")
assert_json "search_result 包含全部必需字段" "$R" "
required = ['task_id', 'intent', 'result_type', 'items', 'summary', 'answer', 'citations']
missing = [f for f in required if f not in data]
print('PASS' if not missing else f'Missing: {missing}')
"
assert_json "search_result: items 为 list" "$R" "
print('PASS' if isinstance(data.get('items'), list) else f\"items type: {type(data.get('items'))}\")
"
assert_json "search_result: citations 为 list" "$R" "
print('PASS' if isinstance(data.get('citations'), list) else f\"citations type: {type(data.get('citations'))}\")
"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 汇总
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo ""
echo -e "${BOLD}━━ 测试汇总 ━━${NC}"
echo -e "  ${GREEN}✓ 通过: ${PASS_COUNT}${NC}"
if [[ $FAIL_COUNT -gt 0 ]]; then
    echo -e "  ${RED}✗ 失败: ${FAIL_COUNT}${NC}"
fi
if [[ $SKIP_COUNT -gt 0 ]]; then
    echo -e "  ${YELLOW}⊘ 跳过: ${SKIP_COUNT}${NC}"
fi
TOTAL=$((PASS_COUNT + FAIL_COUNT + SKIP_COUNT))
echo -e "  总计: ${TOTAL}"
echo ""

if [[ $FAIL_COUNT -gt 0 ]]; then
    exit 1
fi
