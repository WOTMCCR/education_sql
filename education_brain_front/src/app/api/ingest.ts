import { useMock, http } from './http'
import { mockIngestCatalog, mockIngestQuestions, mockIngestDocuments, mockGetTaskStatus } from '../mock/ingest'
import type { IngestTaskResponse, TaskDetail } from '../types'

export async function ingestCatalog(filePath: string): Promise<IngestTaskResponse> {
  if (useMock) return mockIngestCatalog()
  const response = await http<{ task_id: string }>('POST', '/ingest/catalog', { body: { file_path: filePath } })
  return { task_id: response.task_id, task_type: 'catalog', status: 'pending' }
}

export async function ingestQuestions(filePath: string, enableQualityCheck = true): Promise<IngestTaskResponse> {
  if (useMock) return mockIngestQuestions()
  void enableQualityCheck
  const response = await http<{ task_id: string }>('POST', '/ingest/questions', { body: { file_path: filePath } })
  return { task_id: response.task_id, task_type: 'questions', status: 'pending' }
}

export async function ingestDocuments(filePaths: string[], docType: string, sourceMappings?: any[]): Promise<IngestTaskResponse> {
  if (useMock) return mockIngestDocuments(filePaths.length)
  void sourceMappings
  const response = await http<{ task_id: string }>('POST', '/ingest/documents', {
    body: { file_path: filePaths, doc_type: docType },
  })
  return {
    task_id: response.task_id,
    task_type: 'documents',
    status: 'pending',
    sub_task_count: filePaths.length || 1,
  }
}

export async function getTaskStatus(taskId: string): Promise<TaskDetail> {
  if (useMock) return mockGetTaskStatus(taskId)
  const response = await http<any>('GET', `/ingest/tasks/${taskId}`)
  const subTasks = Array.isArray(response.sub_tasks) ? response.sub_tasks : []
  const total = subTasks.length || 1
  const completed = subTasks.length
    ? subTasks.filter((task: any) => task.status === 'completed').length
    : response.status === 'completed'
      ? 1
      : 0
  const failed = subTasks.filter((task: any) => task.status === 'failed').length

  return {
    task_id: response.task_id,
    task_type: response.task_type,
    status: response.status,
    created_at: response.created_at,
    updated_at: response.updated_at,
    progress: {
      total,
      completed,
      failed,
    },
    sub_tasks: subTasks,
    progress_logs: (response.progress_logs || []).map((log: any) => ({
      time: log.time || log.timestamp,
      message: log.message || '',
    })),
  }
}
