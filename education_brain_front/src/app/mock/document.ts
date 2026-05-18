import type { SearchDocumentsResponse } from '../types'

export function mockSearchDocuments(_params: { query: string; doc_type?: string; top_k?: number }): SearchDocumentsResponse {
  return {
    items: [
      {
        chunk_id: 'chunk_001', doc_id: 'doc_python_mysql_001', doc_type: 'course_doc',
        doc_title: '尚硅谷大模型技术之Python连接MySQL', source_file: '尚硅谷大模型技术之Python连接MySQL.docx',
        section_path: ['第2章 数据库连接', '2.1 pymysql 基础使用'], chunk_kind: 'code',
        chunk_text: '使用 pymysql.connect(host, user, password, database) 建立连接。连接成功后，可以通过 cursor() 创建游标对象执行 SQL 语句。',
        score: 0.8912, source_mapping: { series_code: 'general_purpose_programming_foundation', module_code: 'gppf_m2', project_name: null },
        image_refs: [],
      },
      {
        chunk_id: 'chunk_002', doc_id: 'doc_python_mysql_001', doc_type: 'course_doc',
        doc_title: '尚硅谷大模型技术之Python连接MySQL', source_file: '尚硅谷大模型技术之Python连接MySQL.docx',
        section_path: ['第2章 数据库连接', '2.2 连接池配置'], chunk_kind: 'text',
        chunk_text: '在生产环境中，建议使用连接池管理数据库连接。DBUtils 提供了 PooledDB 类来实现连接池功能。',
        score: 0.7654, source_mapping: { series_code: 'general_purpose_programming_foundation', module_code: 'gppf_m2', project_name: null },
        image_refs: [],
      },
      {
        chunk_id: 'chunk_003', doc_id: 'doc_python_001', doc_type: 'course_doc',
        doc_title: '尚硅谷大模型技术之Python1.0', source_file: '尚硅谷大模型技术之Python1.0.docx',
        section_path: ['第5章 模块与包', '5.3 第三方库安装'], chunk_kind: 'text',
        chunk_text: '使用 pip install pymysql 安装 pymysql 库。安装完成后即可在代码中 import pymysql。',
        score: 0.7123, source_mapping: { series_code: 'general_purpose_programming_foundation', module_code: 'gppf_m1', project_name: null },
        image_refs: [],
      },
    ],
  }
}
