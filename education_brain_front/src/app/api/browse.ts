import { useMock, http } from './http'
import type { BrowseResponse } from '../types'

const mockEntries = {
  '': {
    current_path: '',
    parent_path: null,
    entries: [
      { name: '课程文档', path: 'data/数据/课程文档', nav_path: '课程文档', is_dir: true, children_count: 3 },
      { name: '项目文档', path: 'data/数据/项目文档', nav_path: '项目文档', is_dir: true, children_count: 2 },
      { name: '课程介绍.md', path: 'data/数据/课程介绍.md', nav_path: '课程介绍.md', is_dir: false, children_count: 0 },
      { name: '题目资料.md', path: 'data/数据/题目资料.md', nav_path: '题目资料.md', is_dir: false, children_count: 0 },
    ],
  },
  '课程文档': {
    current_path: '课程文档',
    parent_path: '',
    entries: [
      { name: '收入指标说明.docx', path: 'data/数据/课程文档/收入指标说明.docx', nav_path: '课程文档/收入指标说明.docx', is_dir: false, children_count: 0 },
      { name: '校区运营看板.docx', path: 'data/数据/课程文档/校区运营看板.docx', nav_path: '课程文档/校区运营看板.docx', is_dir: false, children_count: 0 },
      { name: '学员履约分析.docx', path: 'data/数据/课程文档/学员履约分析.docx', nav_path: '课程文档/学员履约分析.docx', is_dir: false, children_count: 0 },
    ],
  },
  '项目文档': {
    current_path: '项目文档',
    parent_path: '',
    entries: [
      { name: 'README.md', path: 'data/数据/项目文档/README.md', nav_path: '项目文档/README.md', is_dir: false, children_count: 0 },
      { name: '项目说明.docx', path: 'data/数据/项目文档/项目说明.docx', nav_path: '项目文档/项目说明.docx', is_dir: false, children_count: 0 },
    ],
  },
} as Record<string, BrowseResponse>

export async function browseFiles(path = ''): Promise<BrowseResponse> {
  if (useMock) {
    return mockEntries[path] || { current_path: path, parent_path: '', entries: [] }
  }
  return http<BrowseResponse>('GET', '/ingest/browse', { params: { path } })
}
