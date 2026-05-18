#!/usr/bin/env bash
# 教育问数 API — 真实请求级冒烟测试
#
# 用法:
#   ./knowledge/tests/smoke_test_data_qa.sh
#   BASE=http://localhost:8000 SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh
#
# 阶段:
#   SMOKE_STAGE=meta      元数据健康与召回
#   SMOKE_STAGE=pipeline  NL2SQL pipeline
#   SMOKE_STAGE=chat      聊天接入与历史
#   SMOKE_STAGE=visual    图表协议
#   SMOKE_STAGE=all       全部阶段

set -uo pipefail

BASE="${BASE:-http://localhost:8000}"
SMOKE_STAGE="${SMOKE_STAGE:-all}"
QA_TIMEOUT="${QA_TIMEOUT:-180}"
SMOKE_VALUE_QUERY="${SMOKE_VALUE_QUERY:-北京校区}"
RUN_ID="data-qa-smoke-$(date +%s)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

section() {
    echo ""
    echo -e "${BOLD}${CYAN}━━ $1 ━━${NC}"
}

pass() {
    echo -e "  ${GREEN}✓${NC} $1"
    PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
    echo -e "  ${RED}✗${NC} $1"
    echo -e "    ${RED}→ $2${NC}"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

skip() {
    echo -e "  ${YELLOW}⊘${NC} $1 — $2"
    SKIP_COUNT=$((SKIP_COUNT + 1))
}

assert_json() {
    local description="$1"
    local response="$2"
    local check_expr="$3"

    if [[ -z "$response" ]]; then
        fail "$description" "响应为空"
        return
    fi

    local result
    result=$(echo "$response" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
except Exception as e:
    print(f'JSON_ERROR: {e}')
    sys.exit(0)
$check_expr
" 2>&1) || true

    if [[ "$result" == "PASS" ]]; then
        pass "$description"
    elif [[ "$result" == SKIP* ]]; then
        skip "$description" "${result#SKIP: }"
    else
        fail "$description" "$result"
    fi
}

get_json() {
    curl -sf --max-time "$QA_TIMEOUT" "$@" 2>/dev/null || true
}

post_json() {
    local path="$1"
    local body="$2"
    curl -sf --max-time "$QA_TIMEOUT" -X POST "${BASE}${path}" \
        -H "Content-Type: application/json" \
        -d "$body" 2>/dev/null || true
}

check_health() {
    section "0. 基础健康检查"

    local response
    response=$(get_json "${BASE}/health")
    if [[ -z "$response" ]]; then
        echo -e "${RED}服务未启动或不可达: ${BASE}/health${NC}"
        echo "请先启动: cd education_brain && uv run uvicorn knowledge.api.app:app --host 0.0.0.0 --port 8000"
        exit 1
    fi

    assert_json "服务健康接口可访问" "$response" "
status = data.get('status')
print('PASS' if status in ('healthy', 'degraded') else f'Unexpected status: {status}')
"
}

run_meta() {
    section "1. 元数据系统"

    local health metrics columns values
    health=$(get_json "${BASE}/analytics/health")
    assert_json "analytics health 包含依赖与计数" "$health" "
status = data.get('status')
if status not in ('healthy', 'degraded'):
    print(f'Unexpected status: {status}')
    sys.exit(0)
required = ['mysql_meta', 'qdrant', 'elasticsearch', 'embedding', 'counts']
missing = [k for k in required if k not in data]
if missing:
    print(f'Missing keys: {missing}')
else:
    counts = data.get('counts') or {}
    ok = counts.get('tables', 0) > 0 and counts.get('columns', 0) > 0 and counts.get('metrics', 0) >= 10 and counts.get('joins', 0) > 0 and counts.get('dimensions', 0) > 0
    print('PASS' if ok else f'Unexpected counts: {counts}')
"

    metrics=$(get_json -G "${BASE}/analytics/meta/metrics" --data-urlencode "q=收入" --data-urlencode "limit=5")
    assert_json "收入召回 paid_revenue 指标" "$metrics" "
items = data.get('items', data if isinstance(data, list) else [])
ids = [i.get('id') or i.get('metric_id') for i in items]
print('PASS' if 'paid_revenue' in ids else f'Expected paid_revenue, got {ids}')
"

    columns=$(get_json -G "${BASE}/analytics/meta/columns" --data-urlencode "q=实付金额" --data-urlencode "limit=5")
    assert_json "实付金额召回 order.paid_amount 字段" "$columns" "
items = data.get('items', data if isinstance(data, list) else [])
names = [i.get('id') or i.get('full_name') or '.'.join([str(i.get('table_name', '')), str(i.get('column_name', ''))]).strip('.') for i in items]
print('PASS' if 'order.paid_amount' in names else f'Expected order.paid_amount, got {names}')
"

    values=$(get_json -G "${BASE}/analytics/meta/values" --data-urlencode "q=${SMOKE_VALUE_QUERY}" --data-urlencode "limit=5")
    assert_json "真实维度取值可从 ES 召回" "$values" "
items = data.get('items', data if isinstance(data, list) else [])
if not items:
    print('Expected at least one value hit')
else:
    item = items[0]
    required = ['field', 'value', 'score']
    missing = [k for k in required if k not in item]
    print('PASS' if not missing else f'Missing {missing} in {item}')
"
}

assert_data_qa_result() {
    local description="$1"
    local response="$2"
    local expected_analysis="$3"
    local expected_visual="$4"

    assert_json "$description" "$response" "
if data.get('mode') != 'data_qa':
    print(f\"mode should be data_qa, got {data.get('mode')}\")
elif data.get('intent', {}).get('analysisType') != '$expected_analysis':
    print(f\"analysisType should be $expected_analysis, got {data.get('intent', {}).get('analysisType')}\")
elif data.get('visual', {}).get('type') != '$expected_visual':
    print(f\"visual.type should be $expected_visual, got {data.get('visual', {}).get('type')}\")
elif not data.get('explain', {}).get('sql'):
    print('Missing explain.sql')
elif not data.get('trace', {}).get('stages'):
    print('Missing trace.stages')
elif data.get('trace', {}).get('rowCount') is None:
    print('Missing trace.rowCount')
else:
    print('PASS')
"
}

run_pipeline() {
    section "2. NL2SQL Pipeline"

    local response
    response=$(post_json "/analytics/query" "{\"question\":\"本月总收入是多少？\",\"session_id\":\"${RUN_ID}-pipeline\"}")
    assert_data_qa_result "本月总收入 -> stat" "$response" "single_metric" "stat"
    assert_json "本月总收入包含 paid_revenue 口径" "$response" "
metrics = data.get('intent', {}).get('metrics', [])
explained = [m.get('id') for m in data.get('explain', {}).get('metrics', [])]
print('PASS' if 'paid_revenue' in metrics or 'paid_revenue' in explained else f'paid_revenue missing: metrics={metrics}, explained={explained}')
"
    assert_json "本月总收入返回表、join 和行数 trace" "$response" "
explain = data.get('explain', {})
trace = data.get('trace', {})
ok = explain.get('tables') and explain.get('joins') and trace.get('rowCount', -1) >= 1
print('PASS' if ok else f'tables={explain.get(\"tables\")}, joins={explain.get(\"joins\")}, rowCount={trace.get(\"rowCount\")}')
"

    response=$(post_json "/analytics/query" "{\"question\":\"最近30天收入趋势如何？\",\"session_id\":\"${RUN_ID}-pipeline\"}")
    assert_data_qa_result "最近30天收入趋势 -> line" "$response" "trend" "line"
    assert_json "趋势结果有多行和 x/y 字段" "$response" "
visual = data.get('visual', {})
rows = visual.get('rows', [])
print('PASS' if len(rows) > 1 and visual.get('x') and visual.get('y') else f'Unexpected visual: rows={len(rows)}, x={visual.get(\"x\")}, y={visual.get(\"y\")}')
"

    response=$(post_json "/analytics/query" "{\"question\":\"哪个校区收入最高？\",\"session_id\":\"${RUN_ID}-pipeline\"}")
    assert_data_qa_result "校区收入排名 -> bar" "$response" "ranking" "bar"
    assert_json "排名结果包含维度和值" "$response" "
visual = data.get('visual', {})
rows = visual.get('rows', [])
cols = [c.get('key') for c in visual.get('columns', [])]
print('PASS' if rows and len(cols) >= 2 else f'Unexpected ranking visual: rows={len(rows)}, cols={cols}')
"
    assert_json "排名意图包含 sort 或 limit" "$response" "
intent = data.get('intent', {})
print('PASS' if intent.get('sort') or intent.get('limit') else f'Missing sort/limit in intent: {intent}')
"

    response=$(post_json "/analytics/query" "{\"question\":\"本月总收入是多少？; DROP TABLE order;\",\"session_id\":\"${RUN_ID}-pipeline\"}")
    assert_json "危险 SQL 请求不会被执行" "$response" "
sql = data.get('explain', {}).get('sql', '')
err = data.get('error')
safe = ';' not in sql and 'DROP' not in sql.upper()
stages = data.get('trace', {}).get('stages', [])
execute_stage = next((s for s in stages if s.get('name') == 'execute_sql'), {})
skipped = execute_stage.get('status') == 'skipped'
structured_error = isinstance(err, dict) and err.get('stage') and err.get('code') and err.get('message')
print('PASS' if structured_error or (safe and skipped) else f'Expected structured error or skipped execute_sql, sql={sql}, error={err}, execute={execute_stage}')
"
}

run_chat() {
    section "3. 聊天接入"

    local session response history
    session="${RUN_ID}-chat"

    response=$(post_json "/chat/query" "{\"query\":\"本月总收入是多少？\",\"mode\":\"data_qa\",\"session_id\":\"${session}\"}")
    assert_json "chat data_qa 返回 data_qa_result" "$response" "
print('PASS' if data.get('result_type') == 'data_qa_result' else f\"result_type={data.get('result_type')}\")
"
    assert_json "chat data_qa 包含 data_qa_result block" "$response" "
blocks = data.get('blocks', [])
has_block = any(b.get('type') == 'data_qa_result' for b in blocks if isinstance(b, dict))
print('PASS' if has_block else f'Expected data_qa_result block, got {blocks}')
"

    history=$(get_json "${BASE}/chat/history?session_id=${session}&limit=10")
    assert_json "问数结果进入同一聊天历史" "$history" "
msgs = data.get('messages', [])
assistant = [m for m in msgs if m.get('role') == 'assistant']
if len(msgs) < 2 or not assistant:
    print(f'Unexpected messages: {msgs}')
else:
    last = assistant[-1]
    blocks = last.get('blocks', [])
    has_block = any(b.get('type') == 'data_qa_result' for b in blocks if isinstance(b, dict))
    print('PASS' if last.get('mode') == 'data_qa' and has_block else f'Unexpected assistant history item: {last}')
"
}

run_visual() {
    section "4. 图表协议"

    local response
    response=$(post_json "/analytics/query" "{\"question\":\"最近30天收入趋势如何？\",\"session_id\":\"${RUN_ID}-visual\"}")
    assert_json "visual columns 与 rows key 对齐" "$response" "
visual = data.get('visual', {})
cols = [c.get('key') for c in visual.get('columns', [])]
rows = visual.get('rows', [])
if not cols or not rows:
    print(f'Missing cols or rows: cols={cols}, rows={len(rows)}')
else:
    missing = [c for c in cols if c not in rows[0]]
    print('PASS' if not missing else f'Missing columns in row: {missing}')
"
    assert_json "SQL、指标口径、trace 可供折叠展示" "$response" "
explain = data.get('explain', {})
trace = data.get('trace', {})
ok = bool(explain.get('sql')) and isinstance(explain.get('metrics'), list) and isinstance(trace.get('stages'), list)
print('PASS' if ok else f'explain={explain}, trace={trace}')
"
}

should_run() {
    local stage="$1"
    [[ "$SMOKE_STAGE" == "all" || "$SMOKE_STAGE" == "$stage" ]]
}

check_health
should_run "meta" && run_meta
should_run "pipeline" && run_pipeline
should_run "chat" && run_chat
should_run "visual" && run_visual

echo ""
echo -e "${BOLD}━━ 测试汇总 ━━${NC}"
echo -e "  ${GREEN}✓ 通过: ${PASS_COUNT}${NC}"
if [[ $FAIL_COUNT -gt 0 ]]; then
    echo -e "  ${RED}✗ 失败: ${FAIL_COUNT}${NC}"
fi
if [[ $SKIP_COUNT -gt 0 ]]; then
    echo -e "  ${YELLOW}⊘ 跳过: ${SKIP_COUNT}${NC}"
fi
echo -e "  总计: $((PASS_COUNT + FAIL_COUNT + SKIP_COUNT))"
echo ""

if [[ $FAIL_COUNT -gt 0 ]]; then
    exit 1
fi
