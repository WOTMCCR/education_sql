import { useMock, http } from './http'
import { mockGetHistory } from '../mock/chat'
import { mockDataQaChatResponse } from '../mock/data-qa'
import type { ChatBlock, ChatHistoryResponse, ChatMessage, ChatQueryResponse, DataQaResult } from '../types'

export async function chatQuery(sessionId: string, question: string): Promise<ChatQueryResponse> {
  if (useMock) {
    return mockDataQaChatResponse(question)
  }

  const response = await http<ChatQueryResponse>('POST', '/chat/query', {
    body: { session_id: sessionId, query: question, mode: 'data_qa' },
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
    intent: message.intent || 'data_qa',
    mode: message.mode,
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

  if (blocks.some(block => block.type === 'data_qa_result')) {
    return blocks
  }

  const dataQaResult = findDataQaResult(payload)
  if (!dataQaResult) {
    return blocks
  }

  return [
    ...blocks,
    { type: 'data_qa_result', data: dataQaResult },
  ]
}

function isChatBlock(block: any): block is ChatBlock {
  if (!block || typeof block !== 'object') return false
  if (block.type === 'markdown') return typeof block.content === 'string'
  if (block.type === 'data_qa_result') return isDataQaResult(block.data)
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
