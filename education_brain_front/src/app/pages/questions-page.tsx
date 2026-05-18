import { useState, useEffect } from 'react'
import { getQuestions, toQuestionCardVM } from '../api/question'
import type { QuestionCardVM, Pagination as PaginationState } from '../types'
import { Tag } from '../components/status-badge'
import { StateView } from '../components/empty-state'
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '../components/ui/pagination'
import { buildPagination } from '../lib/pagination.js'
import { Search, ChevronDown, ChevronUp, CheckCircle2 } from 'lucide-react'

const typeLabels: Record<string, string> = {
  单选题: '单选题', 多选题: '多选题', 填空题: '填空题', 判断题: '判断题', 简答题: '简答题',
}
const PAGE_SIZE = 20

export function QuestionsPage() {
  const [keyword, setKeyword] = useState('')
  const [questionType, setQuestionType] = useState('')
  const [questions, setQuestions] = useState<QuestionCardVM[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [pagination, setPagination] = useState<PaginationState>({ page: 1, size: PAGE_SIZE, total: 0 })
  const pageMeta = buildPagination(pagination.total, pagination.size, page)

  const fetch = async (nextPage = page) => {
    setLoading(true); setError(null)
    try {
      const res = await getQuestions({
        keyword,
        question_type: questionType || undefined,
        page: nextPage,
        page_size: PAGE_SIZE,
        show_quality_flags: true,
      })
      setQuestions(res.items.map(toQuestionCardVM))
      setPagination(res.pagination)
    } catch (e: any) { setError(e.message || '查询失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { void fetch(page) }, [page])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setExpanded(null)
    if (page !== 1) {
      setPage(1)
      return
    }
    void fetch(1)
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-border">
        <form onSubmit={handleSearch} className="flex gap-2 flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="搜索题目..."
              className="w-full pl-9 pr-3 py-2 border border-border rounded-md bg-input-background text-sm focus:outline-none focus:ring-1 focus:ring-ring" />
          </div>
          <select value={questionType} onChange={e => setQuestionType(e.target.value)}
            className="px-3 py-2 border border-border rounded-md bg-input-background text-sm focus:outline-none focus:ring-1 focus:ring-ring">
            <option value="">全部题型</option>
            <option value="单选题">单选题</option>
            <option value="多选题">多选题</option>
            <option value="填空题">填空题</option>
            <option value="判断题">判断题</option>
          </select>
          <button type="submit" className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:opacity-90">查询</button>
        </form>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {loading ? <StateView type="loading" /> :
         error ? <StateView type="error" message={error} onRetry={() => void fetch(page)} /> :
         questions.length === 0 ? <StateView type="empty" message="没有找到匹配的题目" /> :
         <div className="space-y-3">
           {questions.map((q, i) => (
            <div key={q.id} className="border border-border rounded-lg p-4">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm text-muted-foreground">{(pageMeta.page - 1) * pageMeta.pageSize + i + 1}.</span>
                  <Tag variant="info">{typeLabels[q.type] || q.type}</Tag>
                  <Tag>{q.bankName}</Tag>
                  {q.qualityFlags.map(f => <Tag key={f} variant="warning">{f}</Tag>)}
                </div>
                <button onClick={() => setExpanded(expanded === q.id ? null : q.id)} className="p-1 hover:bg-muted rounded shrink-0">
                  {expanded === q.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
              </div>
              <p className="text-sm mb-3">{q.stem}</p>

              {q.options.length > 0 && (
                <div className="space-y-1.5 mb-3">
                  {q.options.map(o => (
                    <div key={o.label} className={`flex items-center gap-2 text-sm px-3 py-1.5 rounded ${q.answerKey.includes(o.label) ? 'bg-green-50 text-green-800' : 'text-muted-foreground'}`}>
                      {q.answerKey.includes(o.label) && <CheckCircle2 className="w-3.5 h-3.5" />}
                      <span>{o.label}. {o.content}</span>
                    </div>
                  ))}
                </div>
              )}

              {expanded === q.id && (
                <div className="mt-3 pt-3 border-t border-border space-y-2">
                  <div className="text-sm"><span className="text-muted-foreground">答案：</span>{q.answerKey.join('、')}</div>
                  {q.analysis && <div className="text-sm"><span className="text-muted-foreground">解析：</span>{q.analysis}</div>}
                </div>
              )}
            </div>
          ))}

           <div className="flex flex-col gap-3 border-t border-border pt-4">
             <div className="text-sm text-muted-foreground">
               {pageMeta.totalItems === 0
                 ? '暂无结果'
                 : `显示 ${pageMeta.startItem}-${pageMeta.endItem} 题，共 ${pageMeta.totalItems} 题`}
             </div>
             <Pagination className="justify-between">
               <PaginationContent>
                 <PaginationItem>
                   <PaginationPrevious
                     href="#"
                     onClick={(e) => {
                       e.preventDefault()
                       if (!pageMeta.hasPrevious || loading) return
                       setExpanded(null)
                       setPage(pageMeta.page - 1)
                     }}
                     className={!pageMeta.hasPrevious || loading ? 'pointer-events-none opacity-50' : ''}
                   />
                 </PaginationItem>
               </PaginationContent>
               <PaginationContent>
                 <PaginationItem>
                   <PaginationLink href="#" isActive onClick={(e) => e.preventDefault()}>
                     {pageMeta.page} / {pageMeta.totalPages}
                   </PaginationLink>
                 </PaginationItem>
               </PaginationContent>
               <PaginationContent>
                 <PaginationItem>
                   <PaginationNext
                     href="#"
                     onClick={(e) => {
                       e.preventDefault()
                       if (!pageMeta.hasNext || loading) return
                       setExpanded(null)
                       setPage(pageMeta.page + 1)
                     }}
                     className={!pageMeta.hasNext || loading ? 'pointer-events-none opacity-50' : ''}
                   />
                 </PaginationItem>
               </PaginationContent>
             </Pagination>
           </div>
         </div>
        }
      </div>
    </div>
  )
}
