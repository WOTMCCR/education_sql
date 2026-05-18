import { lazy, Suspense, useState, useRef, useEffect, useCallback } from 'react'
import { chatQuery, getChatHistory } from '../api/chat'
import type { ChatMessage, ChatMode, Citation, MetaCitation } from '../types'
import { StateView } from '../components/empty-state'
import { MarkdownContent } from '../components/markdown-content'
import { Send, Bot, User, FileText, Plus, MessageSquare, Loader2, BarChart3, BookOpenText } from 'lucide-react'

const DataQaResultView = lazy(() =>
  import('../components/data-qa-result').then((module) => ({
    default: module.DataQaResultView,
  })),
)

export function ChatPage() {
  const [sessions, setSessions] = useState<string[]>(() => {
    const saved = localStorage.getItem('chat_sessions')
    return saved ? JSON.parse(saved) : ['session_web_001']
  })
  const [activeSession, setActiveSession] = useState(sessions[0])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [chatMode, setChatMode] = useState<ChatMode>('data_qa')
  const [submitting, setSubmitting] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })

  useEffect(() => { scrollToBottom() }, [messages, submitting])

  const loadHistory = useCallback(async (sid: string) => {
    setLoadingHistory(true)
    try {
      const res = await getChatHistory(sid)
      setMessages(res.messages)
    } catch { /* ignore */ }
    finally { setLoadingHistory(false) }
  }, [])

  useEffect(() => { loadHistory(activeSession) }, [activeSession, loadHistory])

  const handleSend = async () => {
    if (!input.trim() || submitting) return
    const question = input.trim()
    setInput('')

    const userMsg: ChatMessage = {
      task_id: '', role: 'user', content: question, intent: chatMode,
      mode: chatMode,
      created_at: new Date().toISOString(), citations: [],
    }
    setMessages(prev => [...prev, userMsg])

    setSubmitting(true)
    try {
      const res = await chatQuery(activeSession, question, chatMode)
      const assistantMsg: ChatMessage = {
        task_id: res.task_id,
        role: 'assistant',
        content: res.answer || res.summary || '',
        intent: res.intent || chatMode,
        mode: res.mode || chatMode,
        result_type: res.result_type || (chatMode === 'meta_qa' ? 'meta_answer' : 'data_qa_result'),
        items: res.items || [],
        summary: res.summary || '',
        answer: res.answer || '',
        blocks: res.blocks || [],
        created_at: new Date().toISOString(),
        citations: res.citations || [],
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch {
      const failedMsg: ChatMessage = {
        task_id: '',
        role: 'assistant',
        content: chatMode === 'meta_qa' ? '数据介绍暂时不可用，请稍后重试。' : '数据分析暂时不可用，请稍后重试。',
        intent: chatMode,
        mode: chatMode,
        result_type: chatMode === 'meta_qa' ? 'meta_answer' : 'data_qa_result',
        created_at: new Date().toISOString(),
        citations: [],
      }
      setMessages(prev => [...prev, failedMsg])
    } finally {
      setSubmitting(false)
    }
  }

  const handleNewSession = () => {
    const id = 'session_web_' + Date.now()
    const nextSessions = [id, ...sessions]
    setSessions(nextSessions)
    localStorage.setItem('chat_sessions', JSON.stringify(nextSessions))
    setActiveSession(id)
    setMessages([])
    setSubmitting(false)
  }

  return (
    <div className="flex h-full min-w-0">
      {/* Sidebar */}
      <div className="hidden w-52 border-r border-border bg-muted/30 flex-col shrink-0 lg:flex">
        <div className="p-3 border-b border-border">
          <button onClick={handleNewSession} className="w-full flex items-center justify-center gap-1.5 px-3 py-2 border border-border rounded-md text-sm hover:bg-muted transition-colors">
            <Plus className="w-4 h-4" /> 新对话
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {sessions.map(sid => (
            <button
              key={sid}
              onClick={() => setActiveSession(sid)}
              className={`w-full text-left px-3 py-2 rounded-md text-xs truncate transition-colors flex items-center gap-1.5 ${
                sid === activeSession ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-muted'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5 shrink-0" />
              {sid.slice(-8)}
            </button>
          ))}
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Messages */}
        <div className="flex-1 space-y-4 overflow-y-auto p-3 sm:p-4">
          {loadingHistory ? <StateView type="loading" /> :
           messages.length === 0 && !submitting ? (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
              <Bot className="w-12 h-12 mb-3 opacity-30" />
              <p className="text-sm">开始提问，探索经营数据</p>
            </div>
          ) : (
            <>
              {messages.map((msg, i) => (
                <MessageBubble key={i} message={msg} />
              ))}
              {submitting && (
                <div className="flex gap-3">
                  <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center shrink-0">
                    <Bot className="w-4 h-4 text-primary-foreground" />
                  </div>
                  <div className="flex-1 max-w-2xl">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" /> {chatMode === 'meta_qa' ? '正在生成数据介绍' : '正在生成数据分析'}
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-border">
          <form onSubmit={e => { e.preventDefault(); handleSend() }} className="max-w-3xl mx-auto space-y-2">
            <div className="inline-flex rounded-md border border-border bg-muted/30 p-1">
              <button
                type="button"
                onClick={() => setChatMode('data_qa')}
                className={`flex items-center gap-1.5 rounded px-2.5 py-1.5 text-xs transition-colors ${
                  chatMode === 'data_qa' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <BarChart3 className="h-3.5 w-3.5" />
                数据分析
              </button>
              <button
                type="button"
                onClick={() => setChatMode('meta_qa')}
                className={`flex items-center gap-1.5 rounded px-2.5 py-1.5 text-xs transition-colors ${
                  chatMode === 'meta_qa' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <BookOpenText className="h-3.5 w-3.5" />
                数据介绍
              </button>
            </div>
            <div className="flex gap-2">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder={chatMode === 'meta_qa' ? '例如：现在有哪些表？' : '例如：最近30天收入趋势如何？'}
              disabled={submitting}
              className="flex-1 px-4 py-2.5 border border-border rounded-lg bg-input-background text-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!input.trim() || submitting}
              className="px-4 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm hover:opacity-90 disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
            </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  const dataQaBlocks = message.blocks?.filter(block => block.type === 'data_qa_result') || []
  const markdownBlocks = message.blocks?.filter(block => block.type === 'markdown') || []
  const metaCitationBlocks = message.blocks?.filter(block => block.type === 'meta_citations') || []
  const knowledgeCitations = message.citations.filter(isKnowledgeCitation)
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${isUser ? 'bg-accent' : 'bg-primary'}`}>
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4 text-primary-foreground" />}
      </div>
      <div className={`min-w-0 max-w-2xl ${isUser ? 'text-right' : ''}`}>
        {dataQaBlocks.length > 0 && !isUser ? (
          <div className="space-y-2 text-left">
            <Suspense fallback={<DataQaLoading />}>
              {dataQaBlocks.map((block, index) => (
                <DataQaResultView key={index} result={block.data} />
              ))}
            </Suspense>
          </div>
        ) : (markdownBlocks.length > 0 || metaCitationBlocks.length > 0) && !isUser ? (
          <div className="space-y-2 text-left">
            {markdownBlocks.length > 0 ? (
              <div className="rounded-lg bg-muted/50 p-3 text-sm">
                {markdownBlocks.map((block, index) => (
                  <MarkdownContent key={index} content={block.content} />
                ))}
              </div>
            ) : null}
            {metaCitationBlocks.map((block, index) => (
              <MetaCitationList key={index} citations={block.data} />
            ))}
          </div>
        ) : (
          <div className={`inline-block rounded-lg p-3 text-sm ${isUser ? 'bg-primary text-primary-foreground whitespace-pre-wrap' : 'bg-muted/50'}`}>
            {isUser ? message.content : <MarkdownContent content={message.content} />}
          </div>
        )}
        {knowledgeCitations.length > 0 && <CitationList citations={knowledgeCitations} />}
      </div>
    </div>
  )
}

function DataQaLoading() {
  return (
    <div className="rounded-lg border border-border bg-background px-3 py-3 text-xs text-muted-foreground">
      正在加载数据分析视图...
    </div>
  )
}

function CitationList({ citations }: { citations: Citation[] }) {
  return (
    <div className="mt-2 space-y-1">
      {citations.map((c, i) => (
        <div key={i} className="flex items-center gap-1.5 text-xs text-muted-foreground bg-muted/30 px-2.5 py-1.5 rounded">
          <FileText className="w-3 h-3 shrink-0" />
          <span>{c.doc_title}</span>
          <span className="text-muted-foreground/60">· {c.section_path.join(' > ')}</span>
        </div>
      ))}
    </div>
  )
}

function isKnowledgeCitation(citation: Citation | MetaCitation): citation is Citation {
  return typeof (citation as Citation).doc_title === 'string' && Array.isArray((citation as Citation).section_path)
}

const metaCitationKindLabels: Record<string, string> = {
  metric: '指标',
  column: '字段',
  table: '表',
  dimension: '维度',
  join: '关联',
  value: '枚举值',
}

const metaCitationSourceLabels: Record<string, string> = {
  meta_metric_info: '指标口径',
  meta_column_info: '字段说明',
  meta_table_info: '表说明',
  meta_dimension_info: '维度说明',
  meta_join_info: '关联说明',
}

function MetaCitationList({ citations }: { citations: MetaCitation[] }) {
  if (citations.length === 0) return null

  return (
    <div className="space-y-1 rounded-lg border border-border bg-background p-2">
      {citations.map((citation, index) => (
        <div key={`${citation.source}-${citation.id}-${index}`} className="flex gap-2 rounded-md bg-muted/30 px-2.5 py-2 text-xs">
          <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="font-medium text-foreground">{citation.name}</span>
              <span className="rounded bg-background px-1.5 py-0.5 text-muted-foreground">
                {metaCitationKindLabels[citation.kind] || citation.kind}
              </span>
              <span className="text-muted-foreground">
                {metaCitationSourceLabels[citation.source] || citation.source}
              </span>
            </div>
            {citation.description && (
              <p className="mt-1 text-muted-foreground">{citation.description}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
