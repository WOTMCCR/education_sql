import { useMock, http } from './http'
import { mockGetQuestions } from '../mock/question'
import type { SearchQuestionsResponse, QuestionCardVM } from '../types'

export interface SearchQuestionsParams {
  keyword?: string
  bank_code?: string
  question_type?: string
  show_quality_flags?: boolean
  page?: number
  page_size?: number
}

export async function getQuestions(params: SearchQuestionsParams): Promise<SearchQuestionsResponse> {
  if (useMock) return mockGetQuestions(params)
  const response = await http<any>('GET', '/search/questions', {
    params: {
      keyword: params.keyword,
      bank_code: params.bank_code,
      question_type: params.question_type,
      page: params.page,
      size: params.page_size,
    },
  })

  return {
    items: (response.items || []).map((item: any) => ({
      question_code: item.question_code,
      bank_code: item.bank_code || '',
      bank_name: item.bank_name || item.bank_code || '',
      question_type: item.question_type || '',
      stem: item.stem || '',
      options: Array.isArray(item.options) ? item.options : [],
      answer_key: Array.isArray(item.answer_key)
        ? item.answer_key
        : String(item.answer_key || '')
            .split(/[,\s]+/)
            .map((part: string) => part.trim())
            .filter(Boolean),
      reference_answer: item.reference_answer || null,
      analysis: item.analysis || '',
      quality_flags: Array.isArray(item.quality_flags) ? item.quality_flags : [],
    })),
    pagination: {
      page: Number(response.page || params.page || 1),
      size: Number(response.size || params.page_size || 20),
      total: Number(response.total || 0),
    },
  }
}

export function toQuestionCardVM(item: SearchQuestionsResponse['items'][0]): QuestionCardVM {
  return {
    id: item.question_code,
    bankName: item.bank_name,
    type: item.question_type,
    stem: item.stem,
    options: item.options,
    answerKey: item.answer_key,
    analysis: item.analysis,
    qualityFlags: item.quality_flags,
  }
}
