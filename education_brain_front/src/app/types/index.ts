// ============ Common ============
export interface AppError {
  code: string
  message: string
  retryable?: boolean
}

export interface Pagination {
  page: number
  size: number
  total: number
}

// ============ Ingest ============
export type TaskStatus = 'pending' | 'running' | 'partial_success' | 'completed' | 'failed'
export type TaskType = 'catalog' | 'questions' | 'documents'
export type DocType = 'course_doc' | 'project_doc'

export interface IngestTaskResponse {
  task_id: string
  task_type: TaskType
  status: TaskStatus
  sub_task_count?: number
}

export interface SubTask {
  file: string
  status: TaskStatus
  chunks?: number
  warning_count?: number
  error?: string
}

export interface ProgressLog {
  time: string
  message: string
}

export interface TaskDetail {
  task_id: string
  task_type: TaskType
  status: TaskStatus
  created_at: string
  updated_at: string
  progress: {
    total: number
    completed: number
    failed: number
  }
  sub_tasks?: SubTask[]
  progress_logs: ProgressLog[]
}

// ============ Search ============
export interface CourseModule {
  module_code: string
  module_title: string
  lesson_count: number
  credit_hours: number
  description: string
}

export interface RelatedDocument {
  doc_id: string
  doc_title: string
}

export interface CourseSeriesItem {
  series_code: string
  series_title: string
  description: string
  category_path: string[]
  audience: string[]
  goal_tags: string[]
  grade_range: string[]
  modules: CourseModule[]
  related_documents: RelatedDocument[]
}

export interface SearchCoursesResponse {
  items: CourseSeriesItem[]
  pagination: Pagination
}

export interface QuestionOption {
  label: string
  content: string
}

export interface QuestionItem {
  question_code: string
  bank_code: string
  bank_name: string
  question_type: string
  stem: string
  options: QuestionOption[]
  answer_key: string[]
  reference_answer: string | null
  analysis: string
  quality_flags: string[]
}

export interface SearchQuestionsResponse {
  items: QuestionItem[]
  pagination: Pagination
}

export interface ImageRef {
  object_key: string
  url: string
}

export interface SourceMapping {
  series_code: string
  module_code: string
  project_name: string | null
}

export interface DocumentChunk {
  chunk_id: string
  doc_id: string
  doc_type: DocType
  doc_title: string
  source_file: string
  section_path: string[]
  chunk_kind: string
  chunk_text: string
  score: number
  source_mapping: SourceMapping
  image_refs: ImageRef[]
}

export interface SearchDocumentsResponse {
  total: number
  query: string
  doc_type: string
  items: DocumentChunk[]
}

// ============ Browse ============
export interface FileEntry {
  name: string
  path: string
  nav_path: string
  is_dir: boolean
  children_count: number
}

export interface BrowseResponse {
  current_path: string
  parent_path: string | null
  entries: FileEntry[]
}

// ============ Chat ============
export type IntentType = 'course_intro' | 'question_search' | 'knowledge' | 'doc_search' | 'knowledge_qa'

export interface ChatQueryResponse {
  task_id: string
  intent: IntentType
  status: string
}

export interface Citation {
  chunk_id: string
  doc_title: string
  section_path: string[]
}

export interface ChatMessage {
  task_id: string
  role: 'user' | 'assistant'
  content: string
  intent: IntentType
  created_at: string
  citations: Citation[]
}

export interface ChatHistoryResponse {
  session_id: string
  messages: ChatMessage[]
}

// ============ ViewModels ============
export interface CourseCardVM {
  id: string
  title: string
  description: string
  tags: string[]
  audience: string[]
  moduleCount: number
  modules: CourseModule[]
  relatedDocs: RelatedDocument[]
  categoryPath: string[]
}

export interface QuestionCardVM {
  id: string
  bankName: string
  type: string
  stem: string
  options: QuestionOption[]
  answerKey: string[]
  analysis: string
  qualityFlags: string[]
}
