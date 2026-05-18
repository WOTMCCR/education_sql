export type ProductChatMode = 'data_qa' | 'meta_qa'
export type DataQaMode = 'data_qa'

export type DataQaAnalysisType = 'single_metric' | 'trend' | 'ranking' | 'comparison' | 'detail'

export type DataQaFilterOperator =
  | 'eq'
  | 'ne'
  | 'in'
  | 'not_in'
  | 'gt'
  | 'gte'
  | 'lt'
  | 'lte'
  | 'between'
  | 'is_null'
  | 'is_not_null'
  | (string & {})

export type DataQaTimeGrain = 'day' | 'week' | 'month'

export type DataQaSortDirection = 'asc' | 'desc'

export interface DataQaFilter {
  field: string
  op: DataQaFilterOperator
  value: unknown
  label?: string
}

export interface DataQaTimeRange {
  start: string
  end: string
  grain?: DataQaTimeGrain
  label?: string
}

export interface DataQaSort {
  field: string
  direction: DataQaSortDirection
}

export interface DataQaIntent {
  analysisType: DataQaAnalysisType
  metrics: string[]
  dimensions: string[]
  filters: DataQaFilter[]
  timeRange?: DataQaTimeRange
  sort?: DataQaSort[]
  limit?: number
}

export type DataQaVisualType = 'stat' | 'line' | 'bar' | 'table'

export type DataQaColumnType = 'string' | 'number' | 'date' | 'percent' | 'currency'

export interface DataQaVisualColumn {
  key: string
  label: string
  type: DataQaColumnType
  unit?: string
  precision?: number
}

export type DataQaVisualRow = Record<string, unknown>

export interface DataQaVisual {
  type: DataQaVisualType
  title: string
  columns: DataQaVisualColumn[]
  rows: DataQaVisualRow[]
  x?: string
  y?: string[]
}

export interface DataQaExplainMetric {
  id: string
  name: string
  formula: string
  description: string
  unit?: string
}

export interface DataQaExplain {
  sql: string
  metrics: DataQaExplainMetric[]
  tables: string[]
  columns: string[]
  joins: string[]
  assumptions: string[]
}

export type DataQaTraceStageName =
  | 'extract_keywords'
  | 'recall_column'
  | 'recall_metric'
  | 'recall_value'
  | 'merge_retrieved_info'
  | 'filter_table'
  | 'filter_metric'
  | 'add_extra_context'
  | 'generate_sql'
  | 'validate_sql'
  | 'correct_sql'
  | 'execute_sql'
  | (string & {})

export type DataQaTraceStageStatus = 'ok' | 'error' | 'skipped'

export interface DataQaTraceStage {
  name: DataQaTraceStageName
  status: DataQaTraceStageStatus
  durationMs?: number
  message?: string
}

export interface DataQaTrace {
  stages: DataQaTraceStage[]
  rowCount: number
  durationMs: number
}

export type DataQaErrorCode =
  | 'RECALL_EMPTY'
  | 'JOIN_PATH_NOT_FOUND'
  | 'LLM_UNAVAILABLE'
  | 'SQL_UNSAFE'
  | 'SQL_VALIDATE_FAILED'
  | 'SQL_EXECUTE_FAILED'
  | 'EMPTY_RESULT'
  | (string & {})

export interface DataQaError {
  stage: string
  code: DataQaErrorCode
  message: string
}

export interface DataQaResult {
  queryId: string
  mode: DataQaMode
  question: string
  answer: string
  intent: DataQaIntent
  visual: DataQaVisual
  explain: DataQaExplain
  trace: DataQaTrace
  warnings: string[]
  error?: DataQaError
}

export type MetaCitationSource =
  | 'meta_metric_info'
  | 'meta_column_info'
  | 'meta_table_info'
  | 'meta_dimension_info'
  | 'meta_join_info'
  | (string & {})

export type MetaCitationKind =
  | 'metric'
  | 'column'
  | 'table'
  | 'dimension'
  | 'join'
  | 'value'
  | (string & {})

export interface MetaCitation {
  kind: MetaCitationKind
  id: string
  name: string
  source: MetaCitationSource
  description?: string
}

export type ChatBlock =
  | { type: 'markdown'; content: string }
  | { type: 'data_qa_result'; data: DataQaResult }
  | { type: 'meta_citations'; data: MetaCitation[] }

export interface DataQaChatResponse {
  task_id: string
  intent: string
  result_type: 'answer' | 'search_result' | 'data_qa_result' | (string & {})
  mode?: ProductChatMode
  items: unknown[]
  summary: string
  answer: string
  citations: unknown[]
  blocks?: ChatBlock[]
}
