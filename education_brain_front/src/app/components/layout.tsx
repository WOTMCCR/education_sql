import { NavLink, Outlet } from 'react-router'
import { BookOpen, Upload, MessageSquare, Search, FileText, HelpCircle, Database, GraduationCap } from 'lucide-react'

const navItems = [
  { label: '智能问答', path: '/', icon: MessageSquare },
  { label: '课程检索', path: '/courses', icon: GraduationCap },
  { label: '题目检索', path: '/questions', icon: HelpCircle },
  { label: '文档搜索', path: '/documents', icon: Search },
  { label: '课程导入', path: '/ingest/catalog', icon: BookOpen },
  { label: '题库导入', path: '/ingest/questions', icon: FileText },
  { label: '文档导入', path: '/ingest/documents', icon: Database },
]

export function Layout() {
  return (
    <div className="flex h-screen bg-background">
      <aside className="w-56 border-r border-border bg-sidebar flex flex-col shrink-0">
        <div className="p-4 border-b border-border flex items-center gap-2">
          <Upload className="w-5 h-5 text-primary" />
          <span className="text-primary">教育知识库</span>
        </div>
        <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto">
          {navItems.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-md transition-colors text-sm ${
                  isActive ? 'bg-sidebar-accent text-sidebar-accent-foreground' : 'text-muted-foreground hover:bg-sidebar-accent/50'
                }`
              }
            >
              <item.icon className="w-4 h-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}
