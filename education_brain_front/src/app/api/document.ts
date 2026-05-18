import { useMock, http } from './http'
import { mockSearchDocuments } from '../mock/document'
import type { SearchDocumentsResponse } from '../types'

export interface SearchDocumentsParams {
  query: string
  doc_type?: string
  top_k?: number
}

export async function searchDocuments(params: SearchDocumentsParams): Promise<SearchDocumentsResponse> {
  if (useMock) return mockSearchDocuments(params)
  const response = await http<any>('GET', '/search/documents', {
    params: {
      query: params.query,
      doc_type: params.doc_type,
      limit: params.top_k,
    },
  })

  return {
    total: Number(response.total || 0),
    query: response.query || params.query,
    doc_type: response.doc_type || params.doc_type || 'all',
    items: (response.items || []).map((item: any) => ({
      chunk_id: item.chunk_id,
      doc_id: item.doc_id || '',
      doc_type: item.doc_type || 'course_doc',
      doc_title: item.doc_title || item.source_file || '',
      source_file: item.source_file || '',
      section_path: Array.isArray(item.section_path) ? item.section_path : [],
      chunk_kind: item.chunk_kind || 'text',
      chunk_text: item.chunk_text || '',
      score: Math.max(0, Math.min(1, 1 - Number(item.distance ?? 1))),
      source_mapping: {
        series_code: item.series_code || '',
        module_code: '',
        project_name: item.project_name || null,
      },
      image_refs: Array.isArray(item.image_refs) ? item.image_refs : [],
    })),
  }
}
