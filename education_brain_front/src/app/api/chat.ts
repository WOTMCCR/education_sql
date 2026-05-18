import { useMock, http } from './http'
import { mockGetHistory } from '../mock/chat'
import { mockDataQaChatResponse } from '../mock/data-qa'
import type { ChatBlock, ChatHistoryResponse, ChatMessage, ChatMode, ChatQueryResponse, DataQaResult, MetaCitation } from '../types'

export async function chatQuery(sessionId: string, question: string, mode: ChatMode): Promise<ChatQueryResponse> {
  if (useMock) {
    if (mode === 'meta_qa') {
      return mockMetaQaChatResponse(question)
    }
    return mockDataQaChatResponse(question)
  }

  const response = await http<ChatQueryResponse>('POST', '/chat/query', {
    body: { session_id: sessionId, query: question, mode },
  })
  return normalizeChatResponse(response)
}

export async function getChatHistory(sessionId: string): Promise<ChatHistoryResponse> {
  if (useMock) return mockGetHistory(sessionId)
  const response = await http<any>('GET', '/chat/history', {
    params: { session_id: sessionId, limit: 20 },
  })

  return {
    session_id: response.session_id || sessionId,
    messages: (response.messages || []).map(normalizeHistoryMessage),
  }
}

function normalizeChatResponse(response: ChatQueryResponse): ChatQueryResponse {
  return {
    ...response,
    blocks: normalizeChatBlocks(response),
  }
}

function normalizeHistoryMessage(message: any): ChatMessage {
  const normalized: ChatMessage = {
    task_id: message.task_id || '',
    role: message.role,
    content: message.content || message.answer || '',
    intent: normalizeMode(message.intent),
    mode: normalizeMode(message.mode || message.intent),
    result_type: message.result_type,
    items: Array.isArray(message.items) ? message.items : [],
    summary: message.summary || '',
    answer: message.answer || '',
    blocks: normalizeChatBlocks(message),
    created_at: message.created_at,
    citations: Array.isArray(message.citations) ? message.citations : [],
  }

  return normalized
}

function normalizeChatBlocks(payload: any): ChatBlock[] {
  const blocks = Array.isArray(payload.blocks)
    ? payload.blocks.filter(isChatBlock)
    : []

  const mode = normalizeMode(payload?.mode || payload?.intent)
  const hasMarkdown = blocks.some(block => block.type === 'markdown')
  const markdownContent = payload?.answer || payload?.summary || payload?.content
  const normalizedBlocks = mode === 'meta_qa' && !hasMarkdown && typeof markdownContent === 'string' && markdownContent.trim()
    ? [{ type: 'markdown' as const, content: markdownContent }, ...blocks]
    : blocks

  if (blocks.some(block => block.type === 'data_qa_result')) {
    return normalizedBlocks
  }

  const dataQaResult = findDataQaResult(payload)
  if (!dataQaResult) {
    return normalizedBlocks
  }

  return [
    ...normalizedBlocks,
    { type: 'data_qa_result', data: dataQaResult },
  ]
}

function isChatBlock(block: any): block is ChatBlock {
  if (!block || typeof block !== 'object') return false
  if (block.type === 'markdown') return typeof block.content === 'string'
  if (block.type === 'data_qa_result') return isDataQaResult(block.data)
  if (block.type === 'meta_citations') return Array.isArray(block.data) && block.data.every(isMetaCitation)
  return false
}

function findDataQaResult(payload: any): DataQaResult | null {
  const candidates = [
    payload?.data_qa_result,
    payload?.dataQaResult,
    payload?.result,
    payload?.data,
    payload,
    ...(Array.isArray(payload?.items) ? payload.items : []),
  ]

  return candidates.find(isDataQaResult) || null
}

function isDataQaResult(value: any): value is DataQaResult {
  return Boolean(
    value &&
    typeof value === 'object' &&
    value.mode === 'data_qa' &&
    typeof value.answer === 'string' &&
    value.intent &&
    typeof value.intent === 'object' &&
    value.visual &&
    typeof value.visual === 'object' &&
    Array.isArray(value.visual.columns) &&
    Array.isArray(value.visual.rows) &&
    value.explain &&
    typeof value.explain === 'object' &&
    Array.isArray(value.explain.metrics) &&
    value.trace &&
    typeof value.trace === 'object' &&
    Array.isArray(value.trace.stages) &&
    Array.isArray(value.warnings),
  )
}

function isMetaCitation(value: any): value is MetaCitation {
  return Boolean(
    value &&
    typeof value === 'object' &&
    typeof value.kind === 'string' &&
    typeof value.id === 'string' &&
    typeof value.name === 'string' &&
    typeof value.source === 'string',
  )
}

function normalizeMode(value: any): ChatMode {
  return value === 'meta_qa' ? 'meta_qa' : 'data_qa'
}

function mockMetaQaChatResponse(question: string): ChatQueryResponse {
  const trimmedQuestion = question.trim()
  const answer = [
    `### ${trimmedQuestion || '数据介绍'}`,
    '',
    '实付收入指已支付成功订单的实收金额汇总，通常排除未支付、已取消或无效订单。',
    '',
    '- 可用于收入趋势、校区排名和课程收入分析。',
    '- 如果要查询具体金额或排名，请切换到数据分析模式。',
  ].join('\n')
  const citations: MetaCitation[] = [
    {
      kind: 'metric',
      id: 'paid_revenue',
      name: '实付收入',
      source: 'meta_metric_info',
      description: 'SUM(order.paid_amount)，仅统计支付成功相关状态。',
    },
    {
      kind: 'column',
      id: 'order.paid_amount',
      name: '订单实付金额',
      source: 'meta_column_info',
      description: '订单表中的实收金额字段。',
    },
  ]

  return {
    task_id: `chat_task_meta_${Date.now()}`,
    intent: 'meta_qa',
    result_type: 'meta_answer',
    mode: 'meta_qa',
    items: [],
    summary: answer,
    answer,
    citations: [],
    blocks: [
      { type: 'markdown', content: answer },
      { type: 'meta_citations', data: citations },
    ],
  }
}
