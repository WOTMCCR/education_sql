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

const mockAnswer = `Python 通常通过以下几种方式连接 MySQL：

1. **pymysql** - 纯 Python 实现的 MySQL 客户端库
   \`\`\`python
   import pymysql
   conn = pymysql.connect(host='localhost', user='root', password='123456', database='test')
   cursor = conn.cursor()
   cursor.execute('SELECT * FROM users')
   \`\`\`

2. **SQLAlchemy** - Python SQL 工具包和 ORM
   \`\`\`python
   from sqlalchemy import create_engine
   engine = create_engine('mysql+pymysql://root:123456@localhost/test')
   \`\`\`

3. **mysql-connector-python** - MySQL 官方驱动

建议在生产环境中使用连接池来管理数据库连接，避免频繁创建和销毁连接。`

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
          doc_title: '尚硅谷大模型技术之Python连接MySQL',
          section_path: ['第2章 数据库连接', '2.1 pymysql 基础使用'],
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
        task_id: 'chat_task_001', role: 'user', content: 'Python 怎么连接 MySQL？',
        intent: 'knowledge_qa', created_at: '2026-04-17T14:30:00+08:00', citations: [],
      },
      {
        task_id: 'chat_task_001', role: 'assistant',
        content: 'Python 通常通过 pymysql 或 SQLAlchemy 连接 MySQL。pymysql 是纯 Python 实现，使用 pymysql.connect() 建立连接。',
        intent: 'knowledge_qa', created_at: '2026-04-17T14:30:06+08:00',
        citations: [{ chunk_id: 'chunk_001', doc_title: '尚硅谷大模型技术之Python连接MySQL', section_path: ['第2章 数据库连接', '2.1 pymysql 基础使用'] }],
      },
      {
        task_id: 'chat_task_002', role: 'user', content: '如何使用连接池？',
        intent: 'knowledge_qa', created_at: '2026-04-17T14:31:00+08:00', citations: [],
      },
      {
        task_id: 'chat_task_002', role: 'assistant',
        content: '建议使用 DBUtils 的 PooledDB 类来实现连接池。它可以管理多个数据库连接，避免频繁创建和销毁连接带来的性能开销。',
        intent: 'knowledge_qa', created_at: '2026-04-17T14:31:08+08:00',
        citations: [{ chunk_id: 'chunk_002', doc_title: '尚硅谷大模型技术之Python连接MySQL', section_path: ['第2章 数据库连接', '2.2 连接池配置'] }],
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
