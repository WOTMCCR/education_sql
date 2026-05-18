import { lazy, Suspense, useState, useRef, useEffect, useCallback } from 'react'
import { chatQuery, getChatHistory } from '../api/chat'
import type { ChatMessage, Citation } from '../types'
import { StateView } from '../components/empty-state'
import { MarkdownContent } from '../components/markdown-content'
import { Send, Bot, User, FileText, Plus, MessageSquare, Loader2, BarChart3 } from 'lucide-react'

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
      task_id: '', role: 'user', content: question, intent: 'data_qa',
      mode: 'data_qa',
      created_at: new Date().toISOString(), citations: [],
    }
    setMessages(prev => [...prev, userMsg])

    setSubmitting(true)
    try {
      const res = await chatQuery(activeSession, question)
      const assistantMsg: ChatMessage = {
        task_id: res.task_id,
        role: 'assistant',
        content: res.answer || res.summary || '',
        intent: 'data_qa',
        mode: 'data_qa',
        result_type: res.result_type || 'data_qa_result',
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
        content: '数据问数暂时不可用，请稍后重试。',
        intent: 'data_qa',
        mode: 'data_qa',
        result_type: 'data_qa_result',
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
                      <Loader2 className="w-3.5 h-3.5 animate-spin" /> 正在生成问数结果
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
                className="flex items-center gap-1.5 rounded bg-background px-2.5 py-1.5 text-xs text-foreground shadow-sm"
              >
                <BarChart3 className="h-3.5 w-3.5" />
                数据问数
              </button>
            </div>
            <div className="flex gap-2">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="例如：最近30天收入趋势如何？"
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
        ) : (
          <div className={`inline-block rounded-lg p-3 text-sm ${isUser ? 'bg-primary text-primary-foreground whitespace-pre-wrap' : 'bg-muted/50'}`}>
            {isUser ? message.content : <MarkdownContent content={message.content} />}
          </div>
        )}
        {message.citations.length > 0 && <CitationList citations={message.citations} />}
      </div>
    </div>
  )
}

function DataQaLoading() {
  return (
    <div className="rounded-lg border border-border bg-background px-3 py-3 text-xs text-muted-foreground">
      正在加载数据问数视图...
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
