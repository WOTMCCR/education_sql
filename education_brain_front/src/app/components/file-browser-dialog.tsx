import { useState, useEffect, useCallback } from 'react'
import { browseFiles } from '../api/browse'
import type { FileEntry } from '../types'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from './ui/dialog'
import { Button } from './ui/button'
import { ScrollArea } from './ui/scroll-area'
import { Checkbox } from './ui/checkbox'
import {
  Folder,
  FolderOpen,
  FileText,
  ChevronRight,
  ArrowLeft,
  Home,
  Loader2,
  FolderInput,
  CheckSquare,
} from 'lucide-react'

interface FileBrowserDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: (paths: string[]) => void
  multiple?: boolean
  title?: string
  acceptFolders?: boolean
}

export function FileBrowserDialog({
  open,
  onOpenChange,
  onConfirm,
  multiple = false,
  title = '选择文件',
  acceptFolders = true,
}: FileBrowserDialogProps) {
  const [currentPath, setCurrentPath] = useState('')
  const [parentPath, setParentPath] = useState<string | null>(null)
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [selected, setSelected] = useState<Map<string, FileEntry>>(new Map())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadDirectory = useCallback(async (navPath: string) => {
    setLoading(true)
    setError(null)
    try {
      const res = await browseFiles(navPath)
      setCurrentPath(res.current_path)
      setParentPath(res.parent_path)
      setEntries(res.entries)
    } catch (e: any) {
      setError(e.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (open) {
      setSelected(new Map())
      loadDirectory('')
    }
  }, [open, loadDirectory])

  const navigateTo = (navPath: string) => {
    setSelected(new Map())
    loadDirectory(navPath)
  }

  const toggleSelect = (entry: FileEntry) => {
    if (entry.is_dir && !acceptFolders) return

    setSelected(prev => {
      const next = new Map(prev)
      if (next.has(entry.path)) {
        next.delete(entry.path)
      } else {
        if (!multiple) next.clear()
        next.set(entry.path, entry)
      }
      return next
    })
  }

  const selectAll = () => {
    const selectable = entries.filter(e => !e.is_dir || acceptFolders)
    if (selectable.every(e => selected.has(e.path))) {
      setSelected(new Map())
    } else {
      setSelected(new Map(selectable.map(e => [e.path, e])))
    }
  }

  const handleConfirm = () => {
    if (selected.size > 0) {
      onConfirm(Array.from(selected.keys()))
      onOpenChange(false)
    }
  }

  const handleDoubleClick = (entry: FileEntry) => {
    if (entry.is_dir) {
      navigateTo(entry.nav_path)
    } else {
      onConfirm([entry.path])
      onOpenChange(false)
    }
  }

  const breadcrumbs = currentPath ? currentPath.split('/') : []

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FolderInput className="w-5 h-5" />
            {title}
          </DialogTitle>
          <DialogDescription>
            {multiple ? '可多选文件或文件夹，双击文件夹进入' : '选择文件或文件夹，双击文件夹进入'}
          </DialogDescription>
        </DialogHeader>

        {/* Breadcrumb navigation */}
        <div className="flex items-center gap-1 text-sm text-muted-foreground border-b border-border pb-2 min-h-[32px] flex-wrap">
          <button
            onClick={() => navigateTo('')}
            className="flex items-center gap-1 hover:text-foreground transition-colors px-1.5 py-0.5 rounded hover:bg-muted"
          >
            <Home className="w-3.5 h-3.5" />
            <span>数据目录</span>
          </button>
          {breadcrumbs.map((segment, i) => {
            const segPath = breadcrumbs.slice(0, i + 1).join('/')
            const isLast = i === breadcrumbs.length - 1
            return (
              <span key={segPath} className="flex items-center gap-1">
                <ChevronRight className="w-3 h-3" />
                {isLast ? (
                  <span className="text-foreground font-medium px-1.5 py-0.5">{segment}</span>
                ) : (
                  <button
                    onClick={() => navigateTo(segPath)}
                    className="hover:text-foreground transition-colors px-1.5 py-0.5 rounded hover:bg-muted"
                  >
                    {segment}
                  </button>
                )}
              </span>
            )
          })}
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-2">
          {parentPath !== null && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigateTo(parentPath)}
              className="gap-1"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              返回上级
            </Button>
          )}
          {multiple && entries.length > 0 && (
            <Button variant="ghost" size="sm" onClick={selectAll} className="gap-1">
              <CheckSquare className="w-3.5 h-3.5" />
              {entries.filter(e => !e.is_dir || acceptFolders).every(e => selected.has(e.path)) ? '取消全选' : '全选'}
            </Button>
          )}
          {selected.size > 0 && (
            <span className="text-xs text-muted-foreground ml-auto">
              已选 {selected.size} 项
            </span>
          )}
        </div>

        {/* File list */}
        <ScrollArea className="flex-1 min-h-0 h-[350px] border border-border rounded-md">
          {loading ? (
            <div className="flex items-center justify-center h-full py-12">
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
              <span className="ml-2 text-sm text-muted-foreground">加载中...</span>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-full py-12">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          ) : entries.length === 0 ? (
            <div className="flex items-center justify-center h-full py-12">
              <p className="text-sm text-muted-foreground">此文件夹为空</p>
            </div>
          ) : (
            <div className="p-1">
              {entries.map(entry => {
                const isSelected = selected.has(entry.path)
                const isSelectable = !entry.is_dir || acceptFolders
                return (
                  <div
                    key={entry.path}
                    className={`flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer transition-colors text-sm ${
                      isSelected
                        ? 'bg-primary/10 text-foreground'
                        : 'hover:bg-muted/70'
                    }`}
                    onClick={() => isSelectable && toggleSelect(entry)}
                    onDoubleClick={() => handleDoubleClick(entry)}
                  >
                    {multiple && isSelectable && (
                      <Checkbox
                        checked={isSelected}
                        onCheckedChange={() => toggleSelect(entry)}
                        onClick={e => e.stopPropagation()}
                      />
                    )}
                    {entry.is_dir ? (
                      isSelected ? (
                        <FolderOpen className="w-4 h-4 text-amber-500 shrink-0" />
                      ) : (
                        <Folder className="w-4 h-4 text-amber-500 shrink-0" />
                      )
                    ) : (
                      <FileText className="w-4 h-4 text-blue-500 shrink-0" />
                    )}
                    <span className="flex-1 truncate">{entry.name}</span>
                    {entry.is_dir && (
                      <span className="flex items-center gap-1 text-xs text-muted-foreground shrink-0">
                        {entry.children_count} 项
                        <ChevronRight className="w-3.5 h-3.5" />
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </ScrollArea>

        {/* Selected summary */}
        {selected.size > 0 && (
          <div className="text-xs text-muted-foreground border border-border rounded-md p-2 max-h-20 overflow-y-auto space-y-0.5">
            {Array.from(selected.values()).map(entry => (
              <div key={entry.path} className="flex items-center gap-1.5">
                {entry.is_dir ? (
                  <Folder className="w-3 h-3 text-amber-500 shrink-0" />
                ) : (
                  <FileText className="w-3 h-3 text-blue-500 shrink-0" />
                )}
                <span className="truncate">{entry.name}</span>
              </div>
            ))}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={handleConfirm} disabled={selected.size === 0}>
            确认选择 {selected.size > 0 && `(${selected.size})`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
