import { useState, useEffect, useRef, useCallback } from 'react'
import { ingestCatalog, ingestQuestions, ingestDocuments, getTaskStatus } from '../api/ingest'
import type { TaskDetail, TaskStatus } from '../types'
import { StatusBadge } from '../components/status-badge'
import { StateView } from '../components/empty-state'
import { FileBrowserDialog } from '../components/file-browser-dialog'
import { Button } from '../components/ui/button'
import { Upload, Play, Clock, FolderOpen, X, FileText, Folder } from 'lucide-react'

const TERMINAL: TaskStatus[] = ['completed', 'partial_success', 'failed']

interface IngestPageProps {
  type: 'catalog' | 'questions' | 'documents'
}

const titles = { catalog: '课程目录导入', questions: '题库导入', documents: '文档导入' }
const descriptions = {
  catalog: '选择课程目录文件（.md）进行导入',
  questions: '选择题库文件（.md）进行导入',
  documents: '选择文档文件或文件夹进行批量导入',
}

export function IngestPage({ type }: IngestPageProps) {
  const [selectedPaths, setSelectedPaths] = useState<string[]>([])
  const [docType, setDocType] = useState('course_doc')
  const [taskDetail, setTaskDetail] = useState<TaskDetail | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [browserOpen, setBrowserOpen] = useState(false)
  const timerRef = useRef<ReturnType<typeof setInterval>>()

  const stopPolling = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = undefined }
  }, [])

  useEffect(() => () => stopPolling(), [stopPolling])

  useEffect(() => {
    setSelectedPaths([])
    setTaskDetail(null)
    setError(null)
  }, [type])

  const startPolling = useCallback((taskId: string) => {
    stopPolling()
    timerRef.current = setInterval(async () => {
      try {
        const detail = await getTaskStatus(taskId)
        setTaskDetail(detail)
        if (TERMINAL.includes(detail.status)) stopPolling()
      } catch {
        stopPolling()
        setError('轮询任务状态失败')
      }
    }, 1500)
  }, [stopPolling])

  const handleBrowseConfirm = (paths: string[]) => {
    if (type === 'documents') {
      setSelectedPaths(prev => {
        const existing = new Set(prev)
        const merged = [...prev]
        for (const p of paths) {
          if (!existing.has(p)) merged.push(p)
        }
        return merged
      })
    } else {
      setSelectedPaths(paths.slice(0, 1))
    }
  }

  const removePath = (path: string) => {
    setSelectedPaths(prev => prev.filter(p => p !== path))
  }

  const handleSubmit = async () => {
    if (selectedPaths.length === 0) return
    setSubmitting(true)
    setError(null)
    setTaskDetail(null)
    try {
      let res
      if (type === 'catalog') {
        res = await ingestCatalog(selectedPaths[0])
      } else if (type === 'questions') {
        res = await ingestQuestions(selectedPaths[0])
      } else {
        res = await ingestDocuments(selectedPaths, docType)
      }
      setTaskDetail({
        task_id: res.task_id,
        task_type: res.task_type,
        status: res.status,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        progress: { total: res.sub_task_count || 1, completed: 0, failed: 0 },
        progress_logs: [{ time: new Date().toISOString(), message: '任务已提交' }],
      })
      startPolling(res.task_id)
    } catch (e: any) {
      setError(e.message || '提交失败')
    } finally {
      setSubmitting(false)
    }
  }

  const isFolder = (path: string) => !path.includes('.')

  return (
    <div className="h-full overflow-y-auto p-6">
      <h1 className="mb-1 flex items-center gap-2"><Upload className="w-5 h-5" />{titles[type]}</h1>
      <p className="mb-6 text-sm text-muted-foreground">{descriptions[type]}</p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Input */}
        <div className="border border-border rounded-lg p-5 space-y-4">
          <h3>导入配置</h3>

          {/* File selector area */}
          <div>
            <label className="block text-sm mb-1.5 text-muted-foreground">
              {type === 'documents' ? '文件/文件夹（支持多选）' : '文件路径'}
            </label>

            {/* Selected files display */}
            {selectedPaths.length > 0 && (
              <div className="mb-2 border border-border rounded-md p-2 space-y-1.5 max-h-36 overflow-y-auto bg-muted/30">
                {selectedPaths.map(path => (
                  <div key={path} className="flex items-center gap-2 text-sm group">
                    {isFolder(path) ? (
                      <Folder className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                    ) : (
                      <FileText className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                    )}
                    <span className="flex-1 truncate">{path}</span>
                    <button
                      onClick={() => removePath(path)}
                      className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-muted"
                    >
                      <X className="w-3.5 h-3.5 text-muted-foreground" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Browse button */}
            <Button
              variant="outline"
              onClick={() => setBrowserOpen(true)}
              className="w-full gap-2 border-dashed"
            >
              <FolderOpen className="w-4 h-4" />
              {selectedPaths.length > 0
                ? (type === 'documents' ? '继续添加文件...' : '重新选择文件...')
                : '浏览并选择文件...'}
            </Button>
          </div>

          {type === 'documents' && (
            <div>
              <label className="block text-sm mb-1.5 text-muted-foreground">文档类型</label>
              <select
                value={docType}
                onChange={e => setDocType(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-md bg-input-background text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="course_doc">课程文档</option>
                <option value="project_doc">项目文档</option>
              </select>
            </div>
          )}

          <Button
            onClick={handleSubmit}
            disabled={submitting || selectedPaths.length === 0}
            className="gap-2"
          >
            <Play className="w-4 h-4" />
            {submitting ? '提交中...' : '开始导入'}
          </Button>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        {/* Right: Task Status */}
        <div className="border border-border rounded-lg p-5">
          <h3 className="mb-4">任务状态</h3>
          {!taskDetail ? (
            <StateView type="empty" message="提交导入任务后在此查看进度" />
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">任务 ID: {taskDetail.task_id.slice(-12)}</span>
                <StatusBadge status={taskDetail.status} />
              </div>

              {/* Progress bar */}
              <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    taskDetail.status === 'failed' ? 'bg-destructive' :
                    taskDetail.status === 'partial_success' ? 'bg-orange-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${taskDetail.progress.total ? ((taskDetail.progress.completed / taskDetail.progress.total) * 100) : 0}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                完成 {taskDetail.progress.completed} / {taskDetail.progress.total}
                {taskDetail.progress.failed > 0 && `，失败 ${taskDetail.progress.failed}`}
              </p>

              {/* Sub tasks */}
              {taskDetail.sub_tasks && taskDetail.sub_tasks.length > 0 && (
                <div>
                  <h4 className="text-sm mb-2">子任务</h4>
                  <div className="space-y-2">
                    {taskDetail.sub_tasks.map((st, i) => (
                      <div key={i} className="flex items-center justify-between p-2.5 bg-muted/50 rounded-md text-sm">
                        <span className="truncate flex-1 mr-2">{st.file}</span>
                        <div className="flex items-center gap-2 shrink-0">
                          {st.chunks && <span className="text-xs text-muted-foreground">{st.chunks} chunks</span>}
                          <StatusBadge status={st.status} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Progress logs */}
              <div>
                <h4 className="text-sm mb-2 flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> 进度日志</h4>
                <div className="space-y-1.5 max-h-48 overflow-y-auto">
                  {taskDetail.progress_logs.map((log, i) => (
                    <div key={i} className="flex gap-2 text-xs">
                      <span className="text-muted-foreground shrink-0">{new Date(log.time).toLocaleTimeString()}</span>
                      <span>{log.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* File Browser Dialog */}
      <FileBrowserDialog
        open={browserOpen}
        onOpenChange={setBrowserOpen}
        onConfirm={handleBrowseConfirm}
        multiple={type === 'documents'}
        title={titles[type] + ' - 选择文件'}
        acceptFolders={type === 'documents'}
      />
    </div>
  )
}
