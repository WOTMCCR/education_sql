import type { ChatBlock, DataQaChatResponse, DataQaResult } from '../types/data-qa'

const paidRevenueMetric = {
  id: 'paid_revenue',
  name: '收入金额',
  formula: 'SUM(order.paid_amount)',
  description: '已支付成功订单的实收金额总和',
  unit: 'yuan',
}

const successTraceStages = [
  { name: 'extract_keywords', status: 'ok', durationMs: 7 },
  { name: 'recall_metric', status: 'ok', durationMs: 39 },
  { name: 'recall_column', status: 'ok', durationMs: 36 },
  { name: 'merge_retrieved_info', status: 'ok', durationMs: 12 },
  { name: 'generate_sql', status: 'ok', durationMs: 860 },
  { name: 'validate_sql', status: 'ok', durationMs: 13 },
  { name: 'execute_sql', status: 'ok', durationMs: 22 },
] satisfies DataQaResult['trace']['stages']

export const mockMonthlyRevenueResult = {
  queryId: 'dq_mock_20260518_0001',
  mode: 'data_qa',
  question: '本月总收入是多少？',
  answer: '本月总收入为 128,560.00 元。',
  intent: {
    analysisType: 'single_metric',
    metrics: ['paid_revenue'],
    dimensions: [],
    filters: [],
    timeRange: {
      start: '2026-05-01',
      end: '2026-05-18',
      grain: 'day',
      label: '本月',
    },
  },
  visual: {
    type: 'stat',
    title: '本月总收入',
    columns: [
      { key: 'metric', label: '指标', type: 'string' },
      { key: 'value', label: '金额', type: 'currency', unit: 'yuan', precision: 2 },
    ],
    rows: [
      { metric: '收入金额', value: 128560.0 },
    ],
  },
  explain: {
    sql: "SELECT SUM(`order`.paid_amount) AS paid_revenue FROM `order` WHERE `order`.order_status IN ('paid','completed','partial_refunded','refunded') AND `order`.paid_at >= '2026-05-01' AND `order`.paid_at < '2026-05-19'",
    metrics: [paidRevenueMetric],
    tables: ['order'],
    columns: ['order.paid_amount', 'order.order_status', 'order.paid_at'],
    joins: [],
    assumptions: ['未指定校区或课程时统计全部订单。'],
  },
  trace: {
    stages: successTraceStages,
    rowCount: 1,
    durationMs: 989,
  },
  warnings: [],
} satisfies DataQaResult

export const mockRecentRevenueTrendResult = {
  queryId: 'dq_mock_20260518_0002',
  mode: 'data_qa',
  question: '最近30天收入趋势如何？',
  answer: '最近 30 天收入整体呈波动上升趋势，周末报名高峰较明显。',
  intent: {
    analysisType: 'trend',
    metrics: ['paid_revenue'],
    dimensions: ['paid_date'],
    filters: [],
    timeRange: {
      start: '2026-04-19',
      end: '2026-05-18',
      grain: 'day',
      label: '最近30天',
    },
    sort: [{ field: 'paid_date', direction: 'asc' }],
  },
  visual: {
    type: 'line',
    title: '最近30天收入趋势',
    columns: [
      { key: 'paid_date', label: '日期', type: 'date' },
      { key: 'paid_revenue', label: '收入金额', type: 'currency', unit: 'yuan', precision: 2 },
    ],
    rows: [
      { paid_date: '2026-04-19', paid_revenue: 3200.0 },
      { paid_date: '2026-04-22', paid_revenue: 5120.0 },
      { paid_date: '2026-04-25', paid_revenue: 4680.0 },
      { paid_date: '2026-04-28', paid_revenue: 6240.0 },
      { paid_date: '2026-05-01', paid_revenue: 5800.0 },
      { paid_date: '2026-05-04', paid_revenue: 7920.0 },
      { paid_date: '2026-05-07', paid_revenue: 7360.0 },
      { paid_date: '2026-05-10', paid_revenue: 9120.0 },
      { paid_date: '2026-05-13', paid_revenue: 8640.0 },
      { paid_date: '2026-05-16', paid_revenue: 10480.0 },
      { paid_date: '2026-05-18', paid_revenue: 9680.0 },
    ],
    x: 'paid_date',
    y: ['paid_revenue'],
  },
  explain: {
    sql: "SELECT DATE(`order`.paid_at) AS paid_date, SUM(`order`.paid_amount) AS paid_revenue FROM `order` WHERE `order`.order_status IN ('paid','completed','partial_refunded','refunded') AND `order`.paid_at >= '2026-04-19' AND `order`.paid_at < '2026-05-19' GROUP BY DATE(`order`.paid_at) ORDER BY paid_date ASC",
    metrics: [paidRevenueMetric],
    tables: ['order'],
    columns: ['order.paid_amount', 'order.order_status', 'order.paid_at'],
    joins: [],
    assumptions: ['图表 mock 按 2-3 天抽样展示，真实接口可返回完整日粒度。'],
  },
  trace: {
    stages: successTraceStages,
    rowCount: 30,
    durationMs: 1120,
  },
  warnings: [],
} satisfies DataQaResult

export const mockCampusRevenueRankingResult = {
  queryId: 'dq_mock_20260518_0003',
  mode: 'data_qa',
  question: '哪个校区收入最高？',
  answer: '收入最高的校区是朝阳校区，收入为 56,300.00 元。',
  intent: {
    analysisType: 'ranking',
    metrics: ['paid_revenue'],
    dimensions: ['campus'],
    filters: [],
    sort: [{ field: 'paid_revenue', direction: 'desc' }],
    limit: 10,
  },
  visual: {
    type: 'bar',
    title: '校区收入排名',
    columns: [
      { key: 'campus_name', label: '校区', type: 'string' },
      { key: 'paid_revenue', label: '收入金额', type: 'currency', unit: 'yuan', precision: 2 },
      { key: 'order_count', label: '订单数', type: 'number', precision: 0 },
    ],
    rows: [
      { campus_name: '朝阳校区', paid_revenue: 56300.0, order_count: 48 },
      { campus_name: '海淀校区', paid_revenue: 42180.0, order_count: 39 },
      { campus_name: '浦东校区', paid_revenue: 30120.0, order_count: 27 },
      { campus_name: '天河校区', paid_revenue: 24860.0, order_count: 22 },
    ],
    x: 'campus_name',
    y: ['paid_revenue'],
  },
  explain: {
    sql: "SELECT org_campus.campus_name, SUM(`order`.paid_amount) AS paid_revenue, COUNT(DISTINCT `order`.id) AS order_count FROM `order` JOIN order_item ON order_item.order_id = `order`.id JOIN series_cohort ON series_cohort.id = order_item.cohort_id JOIN org_campus ON org_campus.id = series_cohort.campus_id WHERE `order`.order_status IN ('paid','completed','partial_refunded','refunded') GROUP BY org_campus.campus_name ORDER BY paid_revenue DESC LIMIT 10",
    metrics: [
      paidRevenueMetric,
      {
        id: 'paid_order_count',
        name: '支付订单数',
        formula: 'COUNT(DISTINCT order.id)',
        description: '支付成功订单数量',
        unit: 'order',
      },
    ],
    tables: ['order', 'order_item', 'series_cohort', 'org_campus'],
    columns: ['order.id', 'order.paid_amount', 'order.order_status', 'order_item.cohort_id', 'series_cohort.campus_id', 'org_campus.campus_name'],
    joins: [
      'order.id = order_item.order_id',
      'order_item.cohort_id = series_cohort.id',
      'series_cohort.campus_id = org_campus.id',
    ],
    assumptions: ['未指定时间范围时统计全部可用订单数据。'],
  },
  trace: {
    stages: successTraceStages,
    rowCount: 4,
    durationMs: 1198,
  },
  warnings: [],
} satisfies DataQaResult

export const mockStudentEnrollmentDetailResult = {
  queryId: 'dq_mock_20260518_0004',
  mode: 'data_qa',
  question: '查看本月新报名学员明细',
  answer: '本月共有 5 条新报名学员明细，按支付时间倒序展示。',
  intent: {
    analysisType: 'detail',
    metrics: ['paid_revenue'],
    dimensions: ['student', 'course', 'campus', 'paid_at'],
    filters: [
      { field: 'order.order_status', op: 'in', value: ['paid', 'completed'], label: '已支付订单' },
    ],
    timeRange: {
      start: '2026-05-01',
      end: '2026-05-18',
      grain: 'day',
      label: '本月',
    },
    sort: [{ field: 'paid_at', direction: 'desc' }],
    limit: 20,
  },
  visual: {
    type: 'table',
    title: '本月新报名学员明细',
    columns: [
      { key: 'paid_at', label: '支付时间', type: 'date' },
      { key: 'student_name', label: '学员', type: 'string' },
      { key: 'course_name', label: '课程', type: 'string' },
      { key: 'campus_name', label: '校区', type: 'string' },
      { key: 'paid_amount', label: '实收金额', type: 'currency', unit: 'yuan', precision: 2 },
      { key: 'advisor_name', label: '顾问', type: 'string' },
    ],
    rows: [
      { paid_at: '2026-05-18', student_name: '李晨曦', course_name: 'Python 数据分析就业班', campus_name: '朝阳校区', paid_amount: 6980.0, advisor_name: '王老师' },
      { paid_at: '2026-05-17', student_name: '周雨桐', course_name: 'AIGC 项目实战营', campus_name: '海淀校区', paid_amount: 4280.0, advisor_name: '赵老师' },
      { paid_at: '2026-05-15', student_name: '陈子墨', course_name: 'Java 全栈进阶班', campus_name: '浦东校区', paid_amount: 7980.0, advisor_name: '刘老师' },
      { paid_at: '2026-05-12', student_name: '黄思源', course_name: 'MySQL 数据库专题课', campus_name: '天河校区', paid_amount: 1980.0, advisor_name: '孙老师' },
      { paid_at: '2026-05-09', student_name: '吴佳宁', course_name: 'Python 数据分析就业班', campus_name: '朝阳校区', paid_amount: 6980.0, advisor_name: '王老师' },
    ],
  },
  explain: {
    sql: "SELECT DATE(`order`.paid_at) AS paid_at, student.name AS student_name, course_series.series_title AS course_name, org_campus.campus_name, `order`.paid_amount, advisor.name AS advisor_name FROM `order` JOIN student ON student.id = `order`.student_id JOIN order_item ON order_item.order_id = `order`.id JOIN course_series ON course_series.id = order_item.series_id JOIN series_cohort ON series_cohort.id = order_item.cohort_id JOIN org_campus ON org_campus.id = series_cohort.campus_id LEFT JOIN advisor ON advisor.id = `order`.advisor_id WHERE `order`.order_status IN ('paid','completed') AND `order`.paid_at >= '2026-05-01' AND `order`.paid_at < '2026-05-19' ORDER BY `order`.paid_at DESC LIMIT 20",
    metrics: [paidRevenueMetric],
    tables: ['order', 'student', 'order_item', 'course_series', 'series_cohort', 'org_campus', 'advisor'],
    columns: ['order.paid_at', 'order.paid_amount', 'student.name', 'course_series.series_title', 'org_campus.campus_name', 'advisor.name'],
    joins: [
      'order.student_id = student.id',
      'order.id = order_item.order_id',
      'order_item.series_id = course_series.id',
      'order_item.cohort_id = series_cohort.id',
      'series_cohort.campus_id = org_campus.id',
      'order.advisor_id = advisor.id',
    ],
    assumptions: ['明细 mock 仅展示前 5 条，真实接口按 limit 返回。'],
  },
  trace: {
    stages: successTraceStages,
    rowCount: 5,
    durationMs: 1044,
  },
  warnings: ['当前为 mock 明细数据，字段用于前端表格和详情态调试。'],
} satisfies DataQaResult

export const mockUnsafeSqlResult = {
  queryId: 'dq_mock_20260518_0005',
  mode: 'data_qa',
  question: '本月总收入是多少？; DROP TABLE order;',
  answer: '这个问题包含不安全的 SQL 片段，系统已停止执行。',
  intent: {
    analysisType: 'single_metric',
    metrics: ['paid_revenue'],
    dimensions: [],
    filters: [],
  },
  visual: {
    type: 'table',
    title: '问数失败',
    columns: [
      { key: 'message', label: '说明', type: 'string' },
    ],
    rows: [
      { message: '请求包含不安全 SQL 片段，未执行查询。' },
    ],
  },
  explain: {
    sql: '',
    metrics: [],
    tables: [],
    columns: [],
    joins: [],
    assumptions: [],
  },
  trace: {
    stages: [
      { name: 'extract_keywords', status: 'ok', durationMs: 5 },
      { name: 'generate_sql', status: 'skipped', message: 'unsafe input' },
      { name: 'validate_sql', status: 'skipped' },
      { name: 'execute_sql', status: 'skipped' },
    ],
    rowCount: 0,
    durationMs: 6,
  },
  warnings: ['已拦截疑似 SQL 注入输入。'],
  error: {
    stage: 'input_guard',
    code: 'SQL_UNSAFE',
    message: '输入包含危险 SQL 片段。',
  },
} satisfies DataQaResult

export const mockDataQaResults = [
  mockMonthlyRevenueResult,
  mockRecentRevenueTrendResult,
  mockCampusRevenueRankingResult,
  mockStudentEnrollmentDetailResult,
  mockUnsafeSqlResult,
] satisfies DataQaResult[]

export function createDataQaResultBlock(result: DataQaResult): ChatBlock {
  return {
    type: 'data_qa_result',
    data: result,
  }
}

export function createDataQaChatBlocks(result: DataQaResult): ChatBlock[] {
  return [
    { type: 'markdown', content: result.answer },
    createDataQaResultBlock(result),
  ]
}

export function getMockDataQaResultBlock(question: string): ChatBlock {
  return createDataQaResultBlock(getMockDataQaResult(question))
}

export function getMockDataQaResult(question: string): DataQaResult {
  const trimmedQuestion = question.trim()
  const normalizedQuestion = trimmedQuestion.toLowerCase()
  const result = selectMockDataQaResult(normalizedQuestion)
  return {
    ...cloneDataQaResult(result),
    question: trimmedQuestion || result.question,
  }
}

export function mockDataQaChatResponse(question: string): DataQaChatResponse {
  const result = getMockDataQaResult(question)

  return {
    task_id: `chat_task_${result.queryId}`,
    intent: 'data_qa',
    result_type: 'data_qa_result',
    mode: 'data_qa',
    items: [],
    summary: result.answer,
    answer: result.answer,
    citations: [],
    blocks: createDataQaChatBlocks(result),
  }
}

function selectMockDataQaResult(normalizedQuestion: string): DataQaResult {
  if (/(drop|delete|truncate|update|insert|alter|;|--)/i.test(normalizedQuestion)) {
    return mockUnsafeSqlResult
  }
  if (normalizedQuestion.includes('趋势') || normalizedQuestion.includes('最近30天') || normalizedQuestion.includes('最近 30 天')) {
    return mockRecentRevenueTrendResult
  }
  if (normalizedQuestion.includes('校区') || normalizedQuestion.includes('排名') || normalizedQuestion.includes('最高')) {
    return mockCampusRevenueRankingResult
  }
  if (normalizedQuestion.includes('明细') || normalizedQuestion.includes('详情') || normalizedQuestion.includes('报名学员')) {
    return mockStudentEnrollmentDetailResult
  }
  return mockMonthlyRevenueResult
}

function cloneDataQaResult(result: DataQaResult): DataQaResult {
  return JSON.parse(JSON.stringify(result)) as DataQaResult
}
