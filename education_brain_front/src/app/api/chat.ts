import { useMock, http, resolveApiUrl } from './http'
import { mockChatQuery, createMockSSEStream, mockGetHistory } from '../mock/chat'
import { mockDataQaChatResponse } from '../mock/data-qa'
import type { ChatQueryResponse, ChatHistoryResponse } from '../types'

const enableSseDebug = import.meta.env.DEV || import.meta.env.VITE_DEBUG_HTTP === 'true'

export async function chatQuery(sessionId: string, question: string, mode: 'knowledge' | 'data_qa' = 'knowledge', docType?: string): Promise<ChatQueryResponse> {
  if (useMock) {
    return mode === 'data_qa'
      ? mockDataQaChatResponse(question)
      : mockChatQuery(sessionId)
  }
  void docType

  if (mode === 'data_qa') {
    return http<ChatQueryResponse>('POST', '/chat/query', { body: { session_id: sessionId, query: question, mode } })
  }

  return http<ChatQueryResponse>('POST', '/chat/query/stream', { body: { session_id: sessionId, query: question } })
}

export function connectSSE(taskId: string, onEvent: (type: string, data: any) => void): { stop: () => void } {
  if (useMock) return createMockSSEStream(onEvent)

  const url = resolveApiUrl(`/chat/stream/${taskId}`)
  if (enableSseDebug) {
    console.debug('[sse] → open', { taskId, url })
  }

  const es = new EventSource(url)
  const handler = (type: string) => (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data)
      if (enableSseDebug) {
        console.debug('[sse] ← event', { taskId, type, data })
      }
      onEvent(type, data)
    } catch {
      if (enableSseDebug) {
        console.debug('[sse] ← raw', { taskId, type, data: e.data })
      }
      onEvent(type, { content: e.data })
    }
  }
  ;['status', 'thinking', 'token', 'citation', 'done', 'error'].forEach(t => es.addEventListener(t, handler(t)))
  es.onerror = () => {
    if (enableSseDebug) {
      console.error('[sse] × error', { taskId, url })
    }
    onEvent('error', { message: '流连接已中断' })
    es.close()
  }
  return {
    stop: () => {
      if (enableSseDebug) {
        console.debug('[sse] ← close', { taskId, url })
      }
      es.close()
    },
  }
}

export async function getChatHistory(sessionId: string): Promise<ChatHistoryResponse> {
  if (useMock) return mockGetHistory(sessionId)
  const response = await http<any>('GET', '/chat/history', {
    params: { session_id: sessionId, limit: 20 },
  })

  return {
    session_id: response.session_id || sessionId,
    messages: (response.messages || []).map((message: any) => ({
      task_id: message.task_id || '',
      role: message.role,
      content: message.content || message.answer || '',
      intent: message.intent || 'knowledge',
      mode: message.mode,
      result_type: message.result_type,
      items: Array.isArray(message.items) ? message.items : [],
      summary: message.summary || '',
      answer: message.answer || '',
      blocks: Array.isArray(message.blocks) ? message.blocks : [],
      created_at: message.created_at,
      citations: Array.isArray(message.citations) ? message.citations : [],
    })),
  }
}
