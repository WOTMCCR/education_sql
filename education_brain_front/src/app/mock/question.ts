import type { SearchQuestionsResponse } from '../types'

export function mockGetQuestions(_params: { keyword?: string; bank_code?: string; question_type?: string; page?: number; page_size?: number }): SearchQuestionsResponse {
  return {
    items: [
      {
        question_code: 'python_bank_q001', bank_code: 'python_bank', bank_name: 'Python 题库',
        question_type: 'single_choice', stem: 'Python 中用于定义函数的关键字是什么？',
        options: [{ label: 'A', content: 'func' }, { label: 'B', content: 'def' }, { label: 'C', content: 'function' }, { label: 'D', content: 'lambda' }],
        answer_key: ['B'], reference_answer: null, analysis: 'Python 使用 def 定义函数。', quality_flags: [],
      },
      {
        question_code: 'python_bank_q002', bank_code: 'python_bank', bank_name: 'Python 题库',
        question_type: 'multiple_choice', stem: '以下哪些是 Python 内置数据类型？',
        options: [{ label: 'A', content: 'list' }, { label: 'B', content: 'dict' }, { label: 'C', content: 'array' }, { label: 'D', content: 'tuple' }],
        answer_key: ['A', 'B', 'D'], reference_answer: null, analysis: 'array 不是 Python 内置类型，需要 import array 模块。', quality_flags: [],
      },
      {
        question_code: 'mysql_bank_q001', bank_code: 'mysql_bank', bank_name: 'MySQL 题库',
        question_type: 'single_choice', stem: 'SQL 中用于查询数据的关键字是？',
        options: [{ label: 'A', content: 'GET' }, { label: 'B', content: 'FETCH' }, { label: 'C', content: 'SELECT' }, { label: 'D', content: 'FIND' }],
        answer_key: ['C'], reference_answer: null, analysis: 'SELECT 是 SQL 标准查询语句。', quality_flags: [],
      },
      {
        question_code: 'python_bank_q003', bank_code: 'python_bank', bank_name: 'Python 题库',
        question_type: 'fill_blank', stem: 'Python 中使用 ______ 关键字导入模块。',
        options: [], answer_key: ['import'], reference_answer: 'import', analysis: 'Python 使用 import 关键字导入模块。',
        quality_flags: ['stem_too_short'],
      },
      {
        question_code: 'mysql_bank_q002', bank_code: 'mysql_bank', bank_name: 'MySQL 题库',
        question_type: 'true_false', stem: 'MySQL 中 PRIMARY KEY 允许 NULL 值。',
        options: [{ label: 'A', content: '正确' }, { label: 'B', content: '错误' }],
        answer_key: ['B'], reference_answer: null, analysis: 'PRIMARY KEY 不允许 NULL 值。', quality_flags: [],
      },
    ],
    pagination: { page: 1, page_size: 20, total: 5 },
  }
}
