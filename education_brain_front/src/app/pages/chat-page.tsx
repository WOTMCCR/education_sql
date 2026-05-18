import { lazy, Suspense, useState, useRef, useEffect, useCallback } from 'react'
import { chatQuery, connectSSE, getChatHistory } from '../api/chat'
import type { ChatMessage, ChatMode, Citation } from '../types'
import { StateView } from '../components/empty-state'
import { MarkdownContent } from '../components/markdown-content'
import { Send, Bot, User, FileText, Plus, MessageSquare, Loader2, BookOpen, BarChart3 } from 'lucide-react'

const DataQaResultView = lazy(() =>
  import('../components/data-qa-result').then((module) => ({
    default: module.DataQaResultView,
  })),
)

interface StreamingState {
  content: string
  citations: Citation[]
  status: string
  done: boolean
  error: string | null
}

export function ChatPage() {
  const [sessions, setSessions] = useState<string[]>(() => {
    const saved = localStorage.getItem('chat_sessions')
    return saved ? JSON.parse(saved) : ['session_web_001']
  })
  const [activeSession, setActiveSession] = useState(sessions[0])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [mode, setMode] = useState<ChatMode>('knowledge')
  const [streaming, setStreaming] = useState<StreamingState | null>(null)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const sseRef = useRef<{ stop: () => void } | null>(null)

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })

  useEffect(() => { scrollToBottom() }, [messages, streaming?.content])

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
    if (!input.trim() || streaming) return
    const question = input.trim()
    setInput('')

    // Add user message
    const userMsg: ChatMessage = {
      task_id: '', role: 'user', content: question, intent: mode === 'data_qa' ? 'data_qa' : 'knowledge',
      mode,
      created_at: new Date().toISOString(), citations: [],
    }
    setMessages(prev => [...prev, userMsg])

    if (mode === 'data_qa') {
      try {
        const res = await chatQuery(activeSession, question, 'data_qa')
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
      }
      return
    }

    // Start streaming
    const streamState: StreamingState = { content: '', citations: [], status: '', done: false, error: null }
    setStreaming(streamState)

    try {
      const res = await chatQuery(activeSession, question, 'knowledge')
      sseRef.current = connectSSE(res.task_id, (type, data) => {
        setStreaming(prev => {
          if (!prev) return prev
          const next = { ...prev }
          switch (type) {
            case 'status': next.status = data.message; break
            case 'thinking': break
            case 'token': next.content += data.text ?? data.content ?? ''; break
            case 'citation':
              next.citations = Array.isArray(data.citations) ? data.citations : [...prev.citations, data]
              break
            case 'done': {
              next.done = true
              // Add assistant message
              const assistantMsg: ChatMessage = {
                task_id: data.task_id,
                role: 'assistant',
                content: data.answer || next.content,
                intent: data.intent || 'knowledge',
                mode: 'knowledge',
                created_at: new Date().toISOString(),
                citations: Array.isArray(data.citations) ? data.citations : next.citations,
              }
              setMessages(msgs => [...msgs, assistantMsg])
              setStreaming(null)
              sseRef.current?.stop()
              return null
            }
            case 'error': next.error = data.message; next.done = true; break
          }
          return next
        })
      })
    } catch {
      setStreaming(prev => prev ? { ...prev, error: '发送失败', done: true } : null)
    }
  }

  const handleNewSession = () => {
    const id = 'session_web_' + Date.now()
    const nextSessions = [id, ...sessions]
    setSessions(nextSessions)
    localStorage.setItem('chat_sessions', JSON.stringify(nextSessions))
    setActiveSession(id)
    setMessages([])
    setStreaming(null)
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
           messages.length === 0 && !streaming ? (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
              <Bot className="w-12 h-12 mb-3 opacity-30" />
              <p className="text-sm">开始提问，探索知识库或经营数据</p>
            </div>
          ) : (
            <>
              {messages.map((msg, i) => (
                <MessageBubble key={i} message={msg} />
              ))}
              {streaming && (
                <div className="flex gap-3">
                  <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center shrink-0">
                    <Bot className="w-4 h-4 text-primary-foreground" />
                  </div>
                  <div className="flex-1 max-w-2xl">
                    {streaming.status && !streaming.content && (
                      <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                        <Loader2 className="w-3.5 h-3.5 animate-spin" /> {streaming.status}
                      </div>
                    )}
                    {streaming.content && (
                      <div className="bg-muted/50 rounded-lg p-3 text-sm">
                        <MarkdownContent content={streaming.content} />
                        <span className="animate-pulse">▊</span>
                      </div>
                    )}
                    {streaming.error && (
                      <div className="text-sm text-destructive mt-2">{streaming.error}</div>
                    )}
                    {streaming.citations.length > 0 && <CitationList citations={streaming.citations} />}
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
                onClick={() => setMode('knowledge')}
                className={`flex items-center gap-1.5 rounded px-2.5 py-1.5 text-xs transition-colors ${
                  mode === 'knowledge' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <BookOpen className="h-3.5 w-3.5" />
                普通问答
              </button>
              <button
                type="button"
                onClick={() => setMode('data_qa')}
                className={`flex items-center gap-1.5 rounded px-2.5 py-1.5 text-xs transition-colors ${
                  mode === 'data_qa' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <BarChart3 className="h-3.5 w-3.5" />
                数据问数
              </button>
            </div>
            <div className="flex gap-2">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder={mode === 'data_qa' ? '例如：最近30天收入趋势如何？' : '输入你的问题...'}
              disabled={!!streaming}
              className="flex-1 px-4 py-2.5 border border-border rounded-lg bg-input-background text-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!input.trim() || !!streaming}
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
