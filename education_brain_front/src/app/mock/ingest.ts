import type { IngestTaskResponse, TaskDetail, TaskStatus } from '../types'

const taskStore: Record<string, { type: string; step: number; maxSteps: number }> = {}

export function mockIngestCatalog(): IngestTaskResponse {
  const id = 'ingest_catalog_' + Date.now()
  taskStore[id] = { type: 'catalog', step: 0, maxSteps: 4 }
  return { task_id: id, task_type: 'catalog', status: 'pending' }
}

export function mockIngestQuestions(): IngestTaskResponse {
  const id = 'ingest_questions_' + Date.now()
  taskStore[id] = { type: 'questions', step: 0, maxSteps: 5 }
  return { task_id: id, task_type: 'questions', status: 'pending' }
}

export function mockIngestDocuments(fileCount: number): IngestTaskResponse {
  const id = 'ingest_documents_' + Date.now()
  taskStore[id] = { type: 'documents', step: 0, maxSteps: 6 }
  return { task_id: id, task_type: 'documents', status: 'pending', sub_task_count: fileCount }
}

export function mockGetTaskStatus(taskId: string): TaskDetail {
  const task = taskStore[taskId]
  if (!task) {
    // Return a completed mock
    return createCompletedTask(taskId)
  }

  task.step++
  const progress = task.step / task.maxSteps
  let status: TaskStatus = 'running'
  if (progress >= 1) status = 'completed'
  else if (progress < 0.3) status = 'pending'

  const now = new Date().toISOString()
  const logs = [
    { time: now, message: '任务已创建' },
    ...(task.step >= 2 ? [{ time: now, message: '开始解析文件...' }] : []),
    ...(task.step >= 3 ? [{ time: now, message: '数据写入中...' }] : []),
    ...(status === 'completed' ? [{ time: now, message: '任务完成' }] : []),
  ]

  const subTasks = task.type === 'documents' ? [
    { file: '尚硅谷大模型技术之Python1.0.docx', status: (task.step >= 4 ? 'completed' : 'running') as TaskStatus, chunks: task.step >= 4 ? 85 : undefined },
    { file: '尚硅谷大模型技术之MySQL1.0.docx', status: (task.step >= 5 ? 'completed' : task.step >= 4 ? 'running' : 'pending') as TaskStatus },
  ] : undefined

  if (status === 'completed') delete taskStore[taskId]

  return {
    task_id: taskId,
    task_type: task.type as any,
    status,
    created_at: now,
    updated_at: now,
    progress: { total: task.type === 'documents' ? 2 : 1, completed: status === 'completed' ? (task.type === 'documents' ? 2 : 1) : 0, failed: 0 },
    sub_tasks: subTasks,
    progress_logs: logs,
  }
}

function createCompletedTask(taskId: string): TaskDetail {
  const now = new Date().toISOString()
  return {
    task_id: taskId, task_type: 'catalog', status: 'completed',
    created_at: now, updated_at: now,
    progress: { total: 1, completed: 1, failed: 0 },
    progress_logs: [{ time: now, message: '任务完成' }],
  }
}
