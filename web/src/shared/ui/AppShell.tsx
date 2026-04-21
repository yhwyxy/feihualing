import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChangeEvent, FormEvent, useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'

import { createAuthor, listAuthors } from '../api/authors'
import { createCollection } from '../api/collections'
import { importBatch } from '../api/imports'
import { createPoem } from '../api/poems'
import type {
  AuthorWritePayload,
  BatchImportPayload,
  BatchImportResponse,
  CollectionWritePayload,
  ImportCollectionInput,
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

const SAMPLE_IMPORT_PAYLOAD: BatchImportPayload = {
  authors: [
    {
      name: '李白',
      bio: '唐代诗人，字太白，号青莲居士。',
    },
  ],
  poems: [
    {
      title: '静夜思',
      author: '李白',
      content: '床前明月光，\n疑是地上霜。\n举头望明月，\n低头思故乡。',
      collections: ['唐诗精选', '思乡诗'],
    },
  ],
  collections: [
    {
      name: '唐诗精选',
      description: '收录常见唐诗名篇。',
      poems: [
        {
          title: '静夜思',
          author: '李白',
        },
      ],
    },
  ],
}

const MAX_IMPORT_FILE_SIZE = 50 * 1024 * 1024

function parseCsv(text: string) {
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let inQuotes = false

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index]
    const nextChar = text[index + 1]

    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        cell += '"'
        index += 1
      } else {
        inQuotes = !inQuotes
      }
      continue
    }

    if (char === ',' && !inQuotes) {
      row.push(cell)
      cell = ''
      continue
    }

    if ((char === '\n' || char === '\r') && !inQuotes) {
      if (char === '\r' && nextChar === '\n') index += 1
      row.push(cell)
      if (row.some((value) => value.trim())) rows.push(row)
      row = []
      cell = ''
      continue
    }

    cell += char
  }

  row.push(cell)
  if (row.some((value) => value.trim())) rows.push(row)
  return rows
}

function parseCsvImport(text: string): BatchImportPayload {
  const rows = parseCsv(text)
  const [headers, ...dataRows] = rows
  if (!headers || dataRows.length === 0) {
    throw new Error('CSV 至少需要标题行和一行数据')
  }

  const columnIndexes = new Map(headers.map((header, index) => [header.trim(), index]))
  const getValue = (row: string[], key: string) => row[columnIndexes.get(key) ?? -1]?.trim() ?? ''
  const authorMap = new Map<string, { name: string; bio: string | null }>()
  const collectionMap = new Map<string, ImportCollectionInput>()
  const poems: NonNullable<BatchImportPayload['poems']> = []

  dataRows.forEach((row, index) => {
    const title = getValue(row, 'title')
    const author = getValue(row, 'author')
    const content = getValue(row, 'content').replace(/\\n/g, '\n')
    const authorBio = getValue(row, 'author_bio') || null
    const collectionDescription = getValue(row, 'collection_description') || null
    const collections = getValue(row, 'collections')
      .split(';')
      .map((item) => item.trim())
      .filter(Boolean)

    if (!title || !author || !content) {
      throw new Error(`CSV 第 ${index + 2} 行必须包含 title、author、content`)
    }

    if (!authorMap.has(author)) {
      authorMap.set(author, { name: author, bio: authorBio })
    }

    collections.forEach((name) => {
      if (!collectionMap.has(name)) {
        collectionMap.set(name, { name, description: collectionDescription, poems: [] })
      }
      collectionMap.get(name)?.poems?.push({ title, author })
    })

    poems.push({ title, author, content, collections })
  })

  return {
    authors: Array.from(authorMap.values()),
    poems,
    collections: Array.from(collectionMap.values()),
  }
}

function parseImportText(text: string): BatchImportPayload {
  const value = JSON.parse(text) as BatchImportPayload
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('JSON 顶层必须是对象')
  }
  return value
}

function formatSummary(result: BatchImportResponse) {
  const { summary } = result
  return `导入完成：新增 ${summary.poems.created} 首诗词、${summary.authors.created} 位作者、${summary.collections.created} 个合集、${summary.collection_poems.created} 条收录关系。`
}

export function AppShell() {
  const queryClient = useQueryClient()
  const [actionMenuOpen, setActionMenuOpen] = useState(false)
  const [poemFormOpen, setPoemFormOpen] = useState(false)
  const [authorFormOpen, setAuthorFormOpen] = useState(false)
  const [collectionFormOpen, setCollectionFormOpen] = useState(false)
  const [importFormOpen, setImportFormOpen] = useState(false)
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
  const [importText, setImportText] = useState('')
  const [importError, setImportError] = useState('')
  const [importResult, setImportResult] = useState<BatchImportResponse | null>(null)

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

  const importBatchMutation = useMutation({
    mutationFn: importBatch,
    onSuccess: (result) => {
      setImportResult(result)
      setImportError('')
      setMessage(formatSummary(result))
      queryClient.invalidateQueries({ queryKey: ['poems'] })
      queryClient.invalidateQueries({ queryKey: ['authors'] })
      queryClient.invalidateQueries({ queryKey: ['authors-options'] })
      queryClient.invalidateQueries({ queryKey: ['collections'] })
      queryClient.invalidateQueries({ queryKey: ['author-poems'] })
      queryClient.invalidateQueries({ queryKey: ['collection-poems'] })
    },
    onError: () => {
      setImportResult(null)
      setImportError('导入失败，请检查格式或后端服务。')
    },
  })

  const isSubmitting =
    createPoemMutation.isPending ||
    createAuthorMutation.isPending ||
    createCollectionMutation.isPending ||
    importBatchMutation.isPending

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

  function openImportForm() {
    setActionMenuOpen(false)
    setMessage('')
    setImportError('')
    setImportResult(null)
    setImportFormOpen(true)
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

  function closeImportForm() {
    setImportFormOpen(false)
    setImportText('')
    setImportError('')
    setImportResult(null)
  }

  function fillImportExample() {
    setImportText(JSON.stringify(SAMPLE_IMPORT_PAYLOAD, null, 2))
    setImportError('')
    setImportResult(null)
  }

  async function handleImportFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return

    if (file.size > MAX_IMPORT_FILE_SIZE) {
      setImportResult(null)
      setImportError('文件不能超过 50MB')
      event.target.value = ''
      return
    }

    try {
      const text = await file.text()
      const payload = file.name.toLowerCase().endsWith('.csv') ? parseCsvImport(text) : parseImportText(text)
      setImportText(JSON.stringify(payload, null, 2))
      setImportError('')
      setImportResult(null)
    } catch (error) {
      setImportResult(null)
      setImportError(error instanceof Error ? error.message : '文件解析失败')
    } finally {
      event.target.value = ''
    }
  }

  function handleImportSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    try {
      const payload = parseImportText(importText)
      setImportError('')
      setImportResult(null)
      importBatchMutation.mutate(payload)
    } catch (error) {
      setImportResult(null)
      setImportError(error instanceof Error ? error.message : 'JSON 格式错误')
    }
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
              <button type="button" onClick={openImportForm}>
                批量导入
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

      {importFormOpen ? (
        <div className="modal-backdrop" role="presentation" onClick={closeImportForm}>
          <div className="modal-card" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>批量导入</h2>
                <p>粘贴 JSON，或选择 .json / .csv 文件；文件会在浏览器中解析后提交。</p>
              </div>
              <button className="icon-button" type="button" aria-label="关闭" onClick={closeImportForm}>
                ×
              </button>
            </div>

            <form className="form-panel" onSubmit={handleImportSubmit}>
              <label className="field">
                <span>文件</span>
                <input className="input" type="file" accept=".json,.csv" onChange={handleImportFileChange} />
              </label>

              <label className="field">
                <span>导入 JSON</span>
                <textarea
                  className="input textarea import-textarea"
                  value={importText}
                  onChange={(event) => {
                    setImportText(event.target.value)
                    setImportError('')
                    setImportResult(null)
                  }}
                  placeholder="粘贴批量导入 JSON，或选择 .json / .csv 文件自动填充"
                  required
                />
              </label>

              <p className="hint">
                CSV 列名：title, author, content, collections, author_bio, collection_description；多个合集用英文分号分隔。
              </p>

              {importError ? <p className="hint danger-text">{importError}</p> : null}

              {importResult ? (
                <div className="import-result">
                  <h3>导入结果</h3>
                  <div className="import-summary-grid">
                    <span>作者：新增 {importResult.summary.authors.created}，匹配 {importResult.summary.authors.matched}，跳过 {importResult.summary.authors.skipped}</span>
                    <span>诗词：新增 {importResult.summary.poems.created}，匹配 {importResult.summary.poems.matched}，跳过 {importResult.summary.poems.skipped}</span>
                    <span>合集：新增 {importResult.summary.collections.created}，匹配 {importResult.summary.collections.matched}，跳过 {importResult.summary.collections.skipped}</span>
                    <span>收录：新增 {importResult.summary.collection_poems.created}，匹配 {importResult.summary.collection_poems.matched}，跳过 {importResult.summary.collection_poems.skipped}</span>
                  </div>
                  {importResult.warnings.length > 0 ? (
                    <div className="warning-list">
                      <p className="hint">提示</p>
                      {importResult.warnings.map((warning, index) => (
                        <p className="hint" key={`${warning.code}-${warning.path}-${index}`}>
                          {warning.message}
                        </p>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}

              <div className="modal-actions">
                <button className="button" type="button" onClick={fillImportExample}>
                  填入示例
                </button>
                <button className="button button-primary" type="submit" disabled={isSubmitting || !importText.trim()}>
                  开始导入
                </button>
                <button className="button" type="button" onClick={closeImportForm}>
                  关闭
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  )
}
