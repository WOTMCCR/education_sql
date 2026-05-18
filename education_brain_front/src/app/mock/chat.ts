import type { ChatQueryResponse, ChatHistoryResponse } from '../types'
import { createDataQaChatBlocks, mockCampusRevenueRankingResult } from './data-qa'

export function mockChatQuery(sessionId: string): ChatQueryResponse {
  void sessionId
  return {
    task_id: 'chat_task_' + Date.now(),
    intent: 'knowledge_qa',
    status: 'processing',
  }
}

const mockAnswer = `当前数据目录包含订单、校区、课程、咨询、出勤、退款和服务工单等经营数据。

你可以先关注：

1. **收入金额** - 衡量支付成功订单的收入规模。
2. **支付订单数** - 判断成交活跃度。
3. **咨询报名转化率** - 观察获客到报名的转化效率。
4. **出勤率** - 观察课程交付和学员参与情况。
5. **工单数** - 识别服务压力和履约问题。

如果要查询具体金额、趋势或排名，请切换到数据分析模式。`

export function createMockSSEStream(onEvent: (type: string, data: any) => void): { stop: () => void } {
  let stopped = false
  const tokens = mockAnswer.split('')
  let idx = 0

  // Status event
  setTimeout(() => {
    if (stopped) return
    onEvent('status', { stage: 'retrieving', message: '正在检索相关文档' })
  }, 200)

  setTimeout(() => {
    if (stopped) return
    onEvent('status', { stage: 'generating', message: '正在生成回答' })
  }, 800)

  // Token events
  const interval = setInterval(() => {
    if (stopped || idx >= tokens.length) {
      clearInterval(interval)
      if (!stopped) {
        // Citation
        onEvent('citation', {
          chunk_id: 'chunk_001',
          doc_title: '运营数据字典',
          section_path: ['指标说明', '收入指标'],
        })
        // Done
        setTimeout(() => {
          if (!stopped) onEvent('done', { task_id: 'chat_task_001' })
        }, 100)
      }
      return
    }
    // Send 2-3 chars at a time
    const chunk = tokens.slice(idx, idx + 3).join('')
    idx += 3
    onEvent('token', { text: chunk })
  }, 30)

  return {
    stop: () => {
      stopped = true
      clearInterval(interval)
    },
  }
}

export function mockGetHistory(sessionId: string): ChatHistoryResponse {
  return {
    session_id: sessionId,
    messages: [
      {
        task_id: 'chat_task_001', role: 'user', content: '我能问哪些收入相关问题？',
        intent: 'knowledge_qa', created_at: '2026-04-17T14:30:00+08:00', citations: [],
      },
      {
        task_id: 'chat_task_001', role: 'assistant',
        content: '你可以询问收入金额、收入趋势、校区收入排名、退款金额、退款率和客单价等问题。',
        intent: 'knowledge_qa', created_at: '2026-04-17T14:30:06+08:00',
        citations: [{ chunk_id: 'chunk_001', doc_title: '运营数据字典', section_path: ['指标说明', '收入指标'] }],
      },
      {
        task_id: 'chat_task_002', role: 'user', content: '作为校区负责人每天该看哪些指标？',
        intent: 'knowledge_qa', created_at: '2026-04-17T14:31:00+08:00', citations: [],
      },
      {
        task_id: 'chat_task_002', role: 'assistant',
        content: '建议每天关注收入金额、支付订单数、咨询报名转化率、出勤率和服务工单数，并结合校区维度查看异常波动。',
        intent: 'knowledge_qa', created_at: '2026-04-17T14:31:08+08:00',
        citations: [{ chunk_id: 'chunk_002', doc_title: '运营数据字典', section_path: ['指标说明', '运营看板'] }],
      },
      {
        task_id: 'chat_task_003', role: 'user', content: '哪个校区收入最高？',
        intent: 'data_qa', mode: 'data_qa', created_at: '2026-05-18T10:00:00+08:00', citations: [],
      },
      {
        task_id: 'chat_task_003', role: 'assistant',
        content: mockCampusRevenueRankingResult.answer,
        intent: 'data_qa',
        mode: 'data_qa',
        result_type: 'data_qa_result',
        summary: mockCampusRevenueRankingResult.answer,
        answer: mockCampusRevenueRankingResult.answer,
        blocks: createDataQaChatBlocks(mockCampusRevenueRankingResult),
        created_at: '2026-05-18T10:00:04+08:00',
        citations: [],
      },
    ],
  }
}
