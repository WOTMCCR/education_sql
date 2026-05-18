import { NavLink, Outlet } from 'react-router'
import { BarChart3, MessageSquare } from 'lucide-react'

const navItems = [
  { label: '数据分析', path: '/', icon: MessageSquare },
]

export function Layout() {
  return (
    <div className="flex h-screen bg-background">
      <aside className="hidden w-56 border-r border-border bg-sidebar flex-col shrink-0 md:flex">
        <div className="p-4 border-b border-border flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-primary" />
          <span className="text-primary">教育经营分析</span>
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
      <main className="min-w-0 flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}
