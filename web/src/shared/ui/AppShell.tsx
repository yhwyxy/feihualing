import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChangeEvent, FormEvent, useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { createAuthor, listAuthors } from '../api/authors'
import { createCollection } from '../api/collections'
import { createPoem } from '../api/poems'
import type {
  AuthorWritePayload,
  CollectionWritePayload,
  PoemWritePayload,
} from '../types/api'

const navItems = [
  { to: '/feihualing', label: '飞花令' },
  { to: '/workspace', label: '工作台' },
]

const SIDEBAR_COLLAPSED_KEY = 'feihualing:sidebar:collapsed'

function SidebarToggleIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="3" y="4" width="18" height="16" rx="2.5" />
      <line x1="9.5" y1="4" x2="9.5" y2="20" />
    </svg>
  )
}

const EMPTY_POEM_FORM: PoemWritePayload = {
  title: '',
  content: '',
  author_id: 1,
}

const EMPTY_AUTHOR_FORM: AuthorWritePayload = {
  name: '',
  bio: '',
}

const EMPTY_COLLECTION_FORM: CollectionWritePayload = {
  name: '',
  description: '',
}

export function AppShell() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [actionMenuOpen, setActionMenuOpen] = useState(false)
  const [poemFormOpen, setPoemFormOpen] = useState(false)
  const [authorFormOpen, setAuthorFormOpen] = useState(false)
  const [collectionFormOpen, setCollectionFormOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1'
  })

  useEffect(() => {
    try {
      window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, sidebarCollapsed ? '1' : '0')
    } catch {
      // ignore
    }
  }, [sidebarCollapsed])
  const [poemFormData, setPoemFormData] = useState<PoemWritePayload>(EMPTY_POEM_FORM)
  const [authorFormData, setAuthorFormData] = useState<AuthorWritePayload>(EMPTY_AUTHOR_FORM)
  const [collectionFormData, setCollectionFormData] = useState<CollectionWritePayload>(EMPTY_COLLECTION_FORM)

  const authorsQuery = useQuery({
    queryKey: ['authors-options'],
    queryFn: async () => {
      const response = await listAuthors('', 100, 0)
      return response.items
    },
  })

  const createPoemMutation = useMutation({
    mutationFn: createPoem,
    onSuccess: () => {
      setMessage('诗词已新增')
      setPoemFormOpen(false)
      setPoemFormData(EMPTY_POEM_FORM)
      queryClient.invalidateQueries({ queryKey: ['poems'] })
    },
  })

  const createAuthorMutation = useMutation({
    mutationFn: createAuthor,
    onSuccess: () => {
      setMessage('作者已新增')
      setAuthorFormOpen(false)
      setAuthorFormData(EMPTY_AUTHOR_FORM)
      queryClient.invalidateQueries({ queryKey: ['authors'] })
      queryClient.invalidateQueries({ queryKey: ['authors-options'] })
    },
  })

  const createCollectionMutation = useMutation({
    mutationFn: createCollection,
    onSuccess: () => {
      setMessage('合集已新增')
      setCollectionFormOpen(false)
      setCollectionFormData(EMPTY_COLLECTION_FORM)
      queryClient.invalidateQueries({ queryKey: ['collections'] })
    },
  })

  const isSubmitting =
    createPoemMutation.isPending ||
    createAuthorMutation.isPending ||
    createCollectionMutation.isPending

  function openPoemForm() {
    setActionMenuOpen(false)
    setMessage('')
    setPoemFormData({ ...EMPTY_POEM_FORM, author_id: authorsQuery.data?.[0]?.id ?? 1 })
    setPoemFormOpen(true)
  }

  function openAuthorForm() {
    setActionMenuOpen(false)
    setMessage('')
    setAuthorFormOpen(true)
  }

  function openCollectionForm() {
    setActionMenuOpen(false)
    setMessage('')
    setCollectionFormOpen(true)
  }

  function openImportCenter() {
    setActionMenuOpen(false)
    setMessage('')
    navigate('/workspace/documents')
  }

  function closePoemForm() {
    setPoemFormOpen(false)
    setPoemFormData(EMPTY_POEM_FORM)
  }

  function closeAuthorForm() {
    setAuthorFormOpen(false)
    setAuthorFormData(EMPTY_AUTHOR_FORM)
  }

  function closeCollectionForm() {
    setCollectionFormOpen(false)
    setCollectionFormData(EMPTY_COLLECTION_FORM)
  }

  return (
    <div className={`app-shell ${sidebarCollapsed ? 'app-shell-collapsed' : ''}`}>
      <aside className="sidebar" aria-hidden={sidebarCollapsed}>
        <div>
          <p className="sidebar-eyebrow">feihualing</p>
          <h1 className="sidebar-title">飞花令</h1>
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                isActive ? 'nav-link nav-link-active' : 'nav-link'
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="content-shell">
        <header className="topbar">
          <button
            type="button"
            className="sidebar-toggle"
            onClick={() => setSidebarCollapsed((v) => !v)}
            aria-label={sidebarCollapsed ? '展开侧栏' : '收起侧栏'}
            title={sidebarCollapsed ? '展开侧栏' : '收起侧栏'}
          >
            <SidebarToggleIcon />
          </button>
        </header>
        <main className="page-container">
          {message ? <p className="hint">{message}</p> : null}
          <Outlet />
        </main>

        <div className="floating-action-wrap">
          {actionMenuOpen ? (
            <div className="floating-action-menu">
              <button type="button" onClick={openPoemForm}>
                添加诗词
              </button>
              <button type="button" onClick={openAuthorForm}>
                添加作者
              </button>
              <button type="button" onClick={openCollectionForm}>
                添加合集
              </button>
              <button type="button" onClick={openImportCenter}>
                导入资料
              </button>
            </div>
          ) : null}
          <button
            className="floating-action-button"
            type="button"
            aria-label="添加"
            onClick={() => setActionMenuOpen((value) => !value)}
          >
            +
          </button>
        </div>
      </div>

      {poemFormOpen ? (
        <div className="modal-backdrop" role="presentation" onClick={closePoemForm}>
          <div className="modal-card" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>新增诗词</h2>
                <p>填写标题、作者和完整诗句内容。</p>
              </div>
              <button className="icon-button" type="button" aria-label="关闭" onClick={closePoemForm}>
                ×
              </button>
            </div>

            <form
              className="form-panel"
              onSubmit={(event) => {
                event.preventDefault()
                setMessage('')
                createPoemMutation.mutate(poemFormData)
              }}
            >
              <label className="field">
                <span>标题</span>
                <input
                  className="input"
                  value={poemFormData.title}
                  onChange={(event) => setPoemFormData((prev) => ({ ...prev, title: event.target.value }))}
                  required
                />
              </label>

              <label className="field">
                <span>作者</span>
                <select
                  className="input"
                  value={poemFormData.author_id}
                  onChange={(event) =>
                    setPoemFormData((prev) => ({ ...prev, author_id: Number(event.target.value) }))
                  }
                >
                  {authorsQuery.data?.map((author) => (
                    <option key={author.id} value={author.id}>
                      {author.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>内容</span>
                <textarea
                  className="input textarea"
                  value={poemFormData.content}
                  onChange={(event) => setPoemFormData((prev) => ({ ...prev, content: event.target.value }))}
                  required
                />
              </label>

              <div className="modal-actions">
                <button className="button button-primary" type="submit" disabled={isSubmitting}>
                  新增诗词
                </button>
                <button className="button" type="button" onClick={closePoemForm}>
                  取消
                </button>
              </div>

              {createPoemMutation.isError ? <p className="hint">新增诗词失败，请检查输入。</p> : null}
            </form>
          </div>
        </div>
      ) : null}

      {authorFormOpen ? (
        <div className="modal-backdrop" role="presentation" onClick={closeAuthorForm}>
          <div className="modal-card" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>新增作者</h2>
                <p>填写作者姓名和简介。</p>
              </div>
              <button className="icon-button" type="button" aria-label="关闭" onClick={closeAuthorForm}>
                ×
              </button>
            </div>

            <form
              className="form-panel"
              onSubmit={(event) => {
                event.preventDefault()
                setMessage('')
                createAuthorMutation.mutate({
                  ...authorFormData,
                  bio: authorFormData.bio?.trim() ? authorFormData.bio.trim() : null,
                })
              }}
            >
              <label className="field">
                <span>姓名</span>
                <input
                  className="input"
                  value={authorFormData.name}
                  onChange={(event) => setAuthorFormData((prev) => ({ ...prev, name: event.target.value }))}
                  required
                />
              </label>

              <label className="field">
                <span>简介</span>
                <textarea
                  className="input textarea textarea-sm"
                  value={authorFormData.bio ?? ''}
                  onChange={(event) => setAuthorFormData((prev) => ({ ...prev, bio: event.target.value }))}
                />
              </label>

              <div className="modal-actions">
                <button className="button button-primary" type="submit" disabled={isSubmitting}>
                  新增作者
                </button>
                <button className="button" type="button" onClick={closeAuthorForm}>
                  取消
                </button>
              </div>

              {createAuthorMutation.isError ? <p className="hint">新增作者失败，请检查输入。</p> : null}
            </form>
          </div>
        </div>
      ) : null}

      {collectionFormOpen ? (
        <div className="modal-backdrop" role="presentation" onClick={closeCollectionForm}>
          <div className="modal-card" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>新增合集</h2>
                <p>填写合集名称和描述。</p>
              </div>
              <button className="icon-button" type="button" aria-label="关闭" onClick={closeCollectionForm}>
                ×
              </button>
            </div>

            <form
              className="form-panel"
              onSubmit={(event) => {
                event.preventDefault()
                setMessage('')
                createCollectionMutation.mutate({
                  ...collectionFormData,
                  description: collectionFormData.description?.trim() ? collectionFormData.description.trim() : null,
                })
              }}
            >
              <label className="field">
                <span>名称</span>
                <input
                  className="input"
                  value={collectionFormData.name}
                  onChange={(event) => setCollectionFormData((prev) => ({ ...prev, name: event.target.value }))}
                  required
                />
              </label>

              <label className="field">
                <span>描述</span>
                <textarea
                  className="input textarea textarea-sm"
                  value={collectionFormData.description ?? ''}
                  onChange={(event) =>
                    setCollectionFormData((prev) => ({ ...prev, description: event.target.value }))
                  }
                />
              </label>

              <div className="modal-actions">
                <button className="button button-primary" type="submit" disabled={isSubmitting}>
                  新增合集
                </button>
                <button className="button" type="button" onClick={closeCollectionForm}>
                  取消
                </button>
              </div>

              {createCollectionMutation.isError ? <p className="hint">新增合集失败，请检查输入。</p> : null}
            </form>
          </div>
        </div>
      ) : null}

    </div>
  )
}
