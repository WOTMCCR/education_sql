import type { SearchDocumentsResponse } from '../types'

export function mockSearchDocuments(_params: { query: string; doc_type?: string; top_k?: number }): SearchDocumentsResponse {
  return {
    items: [
      {
        chunk_id: 'chunk_001', doc_id: 'doc_python_mysql_001', doc_type: 'course_doc',
        doc_title: '运营数据字典', source_file: '运营数据字典.docx',
        section_path: ['指标说明', '收入指标'], chunk_kind: 'text',
        chunk_text: '收入金额表示支付成功或已完成订单的实付金额汇总，可按日期、校区、课程系列和渠道等维度分析。',
        score: 0.8912, source_mapping: { series_code: 'general_purpose_programming_foundation', module_code: 'gppf_m2', project_name: null },
        image_refs: [],
      },
      {
        chunk_id: 'chunk_002', doc_id: 'doc_python_mysql_001', doc_type: 'course_doc',
        doc_title: '运营数据字典', source_file: '运营数据字典.docx',
        section_path: ['指标说明', '校区运营'], chunk_kind: 'text',
        chunk_text: '校区运营分析通常关注收入金额、支付订单数、报名学员数、出勤率和服务工单数。',
        score: 0.7654, source_mapping: { series_code: 'general_purpose_programming_foundation', module_code: 'gppf_m2', project_name: null },
        image_refs: [],
      },
      {
        chunk_id: 'chunk_003', doc_id: 'doc_python_001', doc_type: 'course_doc',
        doc_title: '数据分析操作指南', source_file: '数据分析操作指南.docx',
        section_path: ['常见问题', '可问范围'], chunk_kind: 'text',
        chunk_text: '用户可以询问收入趋势、校区排名、退款情况、咨询转化和学员履约等经营问题。',
        score: 0.7123, source_mapping: { series_code: 'general_purpose_programming_foundation', module_code: 'gppf_m1', project_name: null },
        image_refs: [],
      },
    ],
  }
}
