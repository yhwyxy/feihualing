import { NavLink, Outlet } from 'react-router-dom'

const WORKSPACE_TABS = [
  { to: 'poems', label: '诗词' },
  { to: 'authors', label: '作者' },
  { to: 'collections', label: '合集' },
  { to: 'concepts', label: '主题图谱' },
  { to: 'documents', label: '导入' },
  { to: 'rag', label: '语义搜索' },
  { to: 'settings', label: '设置' },
]

export function WorkspacePage() {
  return (
    <div className="workspace-page">
      <nav className="workspace-tabs" aria-label="工作台子分类">
        {WORKSPACE_TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              isActive ? 'workspace-tab workspace-tab-active' : 'workspace-tab'
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <div className="workspace-content">
        <Outlet />
      </div>
    </div>
  )
}
