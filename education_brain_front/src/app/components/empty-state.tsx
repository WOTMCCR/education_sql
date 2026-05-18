import { Inbox, AlertTriangle, Loader2 } from 'lucide-react'

interface Props {
  type: 'empty' | 'error' | 'loading'
  message?: string
  onRetry?: () => void
}

export function StateView({ type, message, onRetry }: Props) {
  if (type === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
        <Loader2 className="w-8 h-8 animate-spin mb-3" />
        <p className="text-sm">{message || '加载中...'}</p>
      </div>
    )
  }
  if (type === 'error') {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
        <AlertTriangle className="w-8 h-8 mb-3 text-destructive" />
        <p className="text-sm mb-3">{message || '加载失败'}</p>
        {onRetry && (
          <button onClick={onRetry} className="px-4 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:opacity-90">
            重试
          </button>
        )}
      </div>
    )
  }
  return (
    <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
      <Inbox className="w-8 h-8 mb-3" />
      <p className="text-sm">{message || '暂无数据'}</p>
    </div>
  )
}
