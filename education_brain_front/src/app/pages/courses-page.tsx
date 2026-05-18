import { useState, useEffect } from 'react'
import { getCourses, toCourseCardVM } from '../api/course'
import type { CourseCardVM, Pagination as PaginationState } from '../types'
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
import { Search, BookOpen, X, Users, Target } from 'lucide-react'

const PAGE_SIZE = 10

export function CoursesPage() {
  const [keyword, setKeyword] = useState('')
  const [courses, setCourses] = useState<CourseCardVM[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<CourseCardVM | null>(null)
  const [page, setPage] = useState(1)
  const [pagination, setPagination] = useState<PaginationState>({ page: 1, size: PAGE_SIZE, total: 0 })
  const pageMeta = buildPagination(pagination.total, pagination.size, page)

  const fetchCourses = async (nextPage = page) => {
    setLoading(true)
    setError(null)
    try {
      const res = await getCourses({ keyword, page: nextPage, page_size: PAGE_SIZE })
      setCourses(res.items.map(toCourseCardVM))
      setPagination(res.pagination)
    } catch (e: any) {
      setError(e.message || '查询失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void fetchCourses(page) }, [page])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSelected(null)
    if (page !== 1) {
      setPage(1)
      return
    }
    void fetchCourses(1)
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <form onSubmit={handleSearch} className="flex gap-2 max-w-xl">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              value={keyword}
              onChange={e => setKeyword(e.target.value)}
              placeholder="搜索课程系列..."
              className="w-full pl-9 pr-3 py-2 border border-border rounded-md bg-input-background text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <button type="submit" className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:opacity-90">
            查询
          </button>
        </form>
      </div>

      {/* Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* List */}
        <div className={`${selected ? 'w-1/2 lg:w-2/5' : 'w-full'} overflow-y-auto p-4 transition-all`}>
          {loading ? <StateView type="loading" /> :
           error ? <StateView type="error" message={error} onRetry={() => void fetchCourses(page)} /> :
           courses.length === 0 ? <StateView type="empty" message="没有找到匹配的课程" /> :
           <div className="space-y-3">
             {courses.map(c => (
              <div
                key={c.id}
                onClick={() => setSelected(c)}
                className={`p-4 border rounded-lg cursor-pointer transition-colors ${selected?.id === c.id ? 'border-primary bg-accent/50' : 'border-border hover:border-primary/30'}`}
              >
                <div className="flex items-start justify-between mb-2">
                  <h4 className="text-sm">{c.title}</h4>
                  <span className="text-xs text-muted-foreground shrink-0 ml-2">{c.moduleCount} 个模块</span>
                </div>
                <p className="text-xs text-muted-foreground mb-2 line-clamp-2">{c.description}</p>
                <div className="flex flex-wrap gap-1">
                  {c.tags.map(t => <Tag key={t}>{t}</Tag>)}
                  {c.categoryPath.map(p => <Tag key={p} variant="info">{p}</Tag>)}
                </div>
              </div>
            ))}

             <div className="flex flex-col gap-3 border-t border-border pt-4">
               <div className="text-sm text-muted-foreground">
                 {pageMeta.totalItems === 0
                   ? '暂无结果'
                   : `显示 ${pageMeta.startItem}-${pageMeta.endItem} 条，共 ${pageMeta.totalItems} 条`}
               </div>
               <Pagination className="justify-between">
                 <PaginationContent>
                   <PaginationItem>
                     <PaginationPrevious
                       href="#"
                       onClick={(e) => {
                         e.preventDefault()
                         if (!pageMeta.hasPrevious || loading) return
                         setSelected(null)
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
                         setSelected(null)
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

        {/* Detail Drawer */}
        {selected && (
          <div className="flex-1 border-l border-border overflow-y-auto p-5">
            <div className="flex items-center justify-between mb-4">
              <h2>{selected.title}</h2>
              <button onClick={() => setSelected(null)} className="p-1 hover:bg-muted rounded"><X className="w-4 h-4" /></button>
            </div>
            <p className="text-sm text-muted-foreground mb-4">{selected.description}</p>

            <div className="flex flex-wrap gap-4 mb-6 text-sm">
              <div className="flex items-center gap-1 text-muted-foreground"><Users className="w-4 h-4" /> {selected.audience.join('、')}</div>
              <div className="flex items-center gap-1 text-muted-foreground"><Target className="w-4 h-4" /> {selected.tags.join('、')}</div>
            </div>

            <h3 className="mb-3 flex items-center gap-1.5"><BookOpen className="w-4 h-4" /> 课程模块</h3>
            <div className="space-y-2 mb-6">
              {selected.modules.map(m => (
                <div key={m.module_code} className="p-3 bg-muted/50 rounded-md">
                  <div className="flex justify-between mb-1">
                    <span className="text-sm">{m.module_title}</span>
                    <span className="text-xs text-muted-foreground">{m.lesson_count} 课时 · {m.credit_hours} 学时</span>
                  </div>
                  <p className="text-xs text-muted-foreground">{m.description}</p>
                </div>
              ))}
            </div>

            {selected.relatedDocs.length > 0 && (
              <>
                <h3 className="mb-3">关联文档</h3>
                <div className="space-y-1.5">
                  {selected.relatedDocs.map(d => (
                    <div key={d.doc_id} className="text-sm text-muted-foreground">{d.doc_title}</div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
