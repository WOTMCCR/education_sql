import type { SearchCoursesResponse } from '../types'

export function mockGetCourses(_params: { keyword?: string; page?: number; page_size?: number }): SearchCoursesResponse {
  return {
    items: [
      {
        series_code: 'general_purpose_programming_foundation',
        series_title: 'Python 编程基础',
        description: '面向数据团队的自动化分析基础模块，覆盖数据处理、脚本编排和报表自动化。',
        category_path: ['编程基础', 'Python'],
        audience: ['在校生', '求职者'],
        goal_tags: ['Python 基础', '编程能力'],
        grade_range: ['高年级', '大学'],
        modules: [
          { module_code: 'gppf_m1', module_title: 'Python 基础语法', lesson_count: 8, credit_hours: 16, description: '变量、流程控制、函数。' },
          { module_code: 'gppf_m2', module_title: 'Python 面向对象', lesson_count: 6, credit_hours: 12, description: '类与对象、继承、多态。' },
          { module_code: 'gppf_m3', module_title: 'Python 文件与异常', lesson_count: 4, credit_hours: 8, description: '文件读写、异常处理。' },
        ],
        related_documents: [
          { doc_id: 'doc_ops_001', doc_title: '运营数据处理手册' },
        ],
      },
      {
        series_code: 'database_foundation',
        series_title: 'MySQL 数据库基础',
        description: '面向运营分析的数据建模模块，覆盖指标表、维度表和查询性能基础。',
        category_path: ['数据库', 'MySQL'],
        audience: ['在校生', '开发者'],
        goal_tags: ['SQL 基础', '数据库设计'],
        grade_range: ['大学'],
        modules: [
          { module_code: 'dbf_m1', module_title: 'SQL 基础', lesson_count: 10, credit_hours: 20, description: 'SELECT、INSERT、UPDATE、DELETE。' },
          { module_code: 'dbf_m2', module_title: '表设计与索引', lesson_count: 6, credit_hours: 12, description: '范式、索引优化。' },
        ],
        related_documents: [
          { doc_id: 'doc_modeling_001', doc_title: '经营数据建模手册' },
        ],
      },
      {
        series_code: 'ai_foundation',
        series_title: '大模型技术入门',
        description: '从零开始学习大模型技术，包括 Transformer 架构、Prompt 工程、RAG 等核心概念。',
        category_path: ['人工智能', '大模型'],
        audience: ['开发者', '研究者'],
        goal_tags: ['大模型基础', 'Prompt 工程', 'RAG'],
        grade_range: ['大学', '研究生'],
        modules: [
          { module_code: 'aif_m1', module_title: 'Transformer 架构', lesson_count: 5, credit_hours: 10, description: '注意力机制、编码器解码器。' },
          { module_code: 'aif_m2', module_title: 'Prompt 工程', lesson_count: 4, credit_hours: 8, description: '提示词设计与优化。' },
        ],
        related_documents: [],
      },
    ],
    pagination: { page: 1, page_size: 10, total: 3 },
  }
}
