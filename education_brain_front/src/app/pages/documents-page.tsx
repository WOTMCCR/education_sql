import { useState } from 'react'
import { searchDocuments } from '../api/document'
import type { DocumentChunk } from '../types'
import { Tag } from '../components/status-badge'
import { StateView } from '../components/empty-state'
import { Search, FileText, ChevronRight } from 'lucide-react'

export function DocumentsPage() {
  const [query, setQuery] = useState('')
  const [docType, setDocType] = useState('')
  const [results, setResults] = useState<DocumentChunk[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searched, setSearched] = useState(false)

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true); setError(null); setSearched(true)
    try {
      const res = await searchDocuments({ query, doc_type: docType || undefined, top_k: 5 })
      setResults(res.items)
    } catch (e: any) { setError(e.message || '检索失败') }
    finally { setLoading(false) }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-border">
        <form onSubmit={handleSearch} className="flex gap-2 flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input value={query} onChange={e => setQuery(e.target.value)} placeholder="输入检索文本..."
              className="w-full pl-9 pr-3 py-2 border border-border rounded-md bg-input-background text-sm focus:outline-none focus:ring-1 focus:ring-ring" />
          </div>
          <select value={docType} onChange={e => setDocType(e.target.value)}
            className="px-3 py-2 border border-border rounded-md bg-input-background text-sm focus:outline-none focus:ring-1 focus:ring-ring">
            <option value="">全部类型</option>
            <option value="course_doc">课程文档</option>
            <option value="project_doc">项目文档</option>
          </select>
          <button type="submit" className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:opacity-90">检索</button>
        </form>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {loading ? <StateView type="loading" /> :
         error ? <StateView type="error" message={error} /> :
         !searched ? <StateView type="empty" message="输入检索文本开始搜索" /> :
         results.length === 0 ? <StateView type="empty" message="未找到相关文档片段" /> :
         results.map(chunk => (
          <div key={chunk.chunk_id} className="border border-border rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm">{chunk.doc_title}</span>
              </div>
              <div className="flex items-center gap-2">
                <Tag variant="info">{chunk.doc_type === 'course_doc' ? '课程' : '项目'}</Tag>
                <Tag>{chunk.chunk_kind}</Tag>
                <span className="text-xs text-muted-foreground">相关度 {(chunk.score * 100).toFixed(0)}%</span>
              </div>
            </div>
            <div className="flex items-center gap-1 text-xs text-muted-foreground mb-3">
              {chunk.section_path.map((s, i) => (
                <span key={i} className="flex items-center gap-1">
                  {i > 0 && <ChevronRight className="w-3 h-3" />}
                  {s}
                </span>
              ))}
            </div>
            <p className="text-sm bg-muted/50 p-3 rounded-md">{chunk.chunk_text}</p>
            {chunk.image_refs.length > 0 && (
              <div className="mt-2 text-xs text-muted-foreground">📎 包含 {chunk.image_refs.length} 张图片</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
