import { useMock, http } from './http'
import { mockGetCourses } from '../mock/course'
import type { SearchCoursesResponse, CourseCardVM } from '../types'

export interface SearchCoursesParams {
  keyword?: string
  audience?: string
  goal_tag?: string
  page?: number
  page_size?: number
}

export async function getCourses(params: SearchCoursesParams): Promise<SearchCoursesResponse> {
  if (useMock) return mockGetCourses(params)
  const response = await http<any>('GET', '/search/courses', {
    params: {
      keyword: params.keyword,
      audience: params.audience,
      goal: params.goal_tag,
      page: params.page,
      size: params.page_size,
    },
  })

  return {
    items: (response.items || []).map((item: any) => ({
      series_code: item.series_code,
      series_title: item.title || item.series_title || '',
      description: item.description || '',
      category_path: Array.isArray(item.category_path)
        ? item.category_path
        : String(item.category_path || '')
            .split('/')
            .map((part: string) => part.trim())
            .filter(Boolean),
      audience: Array.isArray(item.audience) ? item.audience : [],
      goal_tags: Array.isArray(item.goal_tags) ? item.goal_tags : [],
      grade_range: Array.isArray(item.grade_range)
        ? item.grade_range
        : Array.isArray(item.grade_tags)
          ? item.grade_tags
          : [],
      modules: (item.modules || []).map((module: any) => ({
        module_code: module.module_code,
        module_title: module.module_title || '',
        lesson_count: Number(module.lesson_count || 0),
        credit_hours: Number(module.credit_hours ?? module.study_hours ?? 0),
        description: module.description || module.module_desc || '',
      })),
      related_documents: (item.related_documents || []).map((doc: any) => ({
        doc_id: doc.doc_id || doc.source_file || '',
        doc_title: doc.doc_title || doc.source_file || '',
      })),
    })),
    pagination: {
      page: Number(response.page || params.page || 1),
      size: Number(response.size || params.page_size || 20),
      total: Number(response.total || 0),
    },
  }
}

export function toCourseCardVM(item: SearchCoursesResponse['items'][0]): CourseCardVM {
  return {
    id: item.series_code,
    title: item.series_title,
    description: item.description,
    tags: item.goal_tags,
    audience: item.audience,
    moduleCount: item.modules.length,
    modules: item.modules,
    relatedDocs: item.related_documents,
    categoryPath: item.category_path,
  }
}
