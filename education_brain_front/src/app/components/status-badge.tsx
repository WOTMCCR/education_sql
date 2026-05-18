import type { TaskStatus } from '../types'

const statusConfig: Record<TaskStatus, { label: string; className: string }> = {
  pending: { label: '等待中', className: 'bg-yellow-100 text-yellow-800' },
  running: { label: '运行中', className: 'bg-blue-100 text-blue-800' },
  completed: { label: '已完成', className: 'bg-green-100 text-green-800' },
  partial_success: { label: '部分成功', className: 'bg-orange-100 text-orange-800' },
  failed: { label: '失败', className: 'bg-red-100 text-red-800' },
}

export function StatusBadge({ status }: { status: TaskStatus }) {
  const config = statusConfig[status] || { label: status, className: 'bg-gray-100 text-gray-800' }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs ${config.className}`}>
      {config.label}
    </span>
  )
}

export function Tag({ children, variant = 'default' }: { children: React.ReactNode; variant?: 'default' | 'warning' | 'info' }) {
  const cls = variant === 'warning' ? 'bg-orange-100 text-orange-700' : variant === 'info' ? 'bg-blue-100 text-blue-700' : 'bg-muted text-muted-foreground'
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs ${cls}`}>{children}</span>
}
