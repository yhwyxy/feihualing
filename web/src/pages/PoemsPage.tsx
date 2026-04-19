import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { listAuthors } from '../shared/api/authors'
import { addPoemToCollection, createCollection, listCollections } from '../shared/api/collections'
import { ApiError } from '../shared/api/http'
import { createPoem, deletePoem, listPoems, updatePoem } from '../shared/api/poems'
import type { CollectionWritePayload, PoemRead, PoemWritePayload } from '../shared/types/api'
import { EmptyState } from '../shared/ui/EmptyState'
import { CollapsiblePoemCard } from '../shared/ui/CollapsiblePoemCard'
import { PageSection } from '../shared/ui/PageSection'

const EMPTY_FORM: PoemWritePayload = {
  title: '',
  content: '',
  author_id: 1,
}

const EMPTY_COLLECTION_FORM: CollectionWritePayload = {
  name: '',
  description: '',
}

type PoemSearchMode = 'title' | 'author'

type SearchParamKey = 'keyword' | 'author_name'

interface SearchModeConfig {
  value: PoemSearchMode
  label: string
  placeholder: string
  toParams: (input: string) => Partial<Record<SearchParamKey, string>>
}

const SEARCH_MODES: SearchModeConfig[] = [
  {
    value: 'title',
    label: '按标题',
    placeholder: '输入诗词标题',
    toParams: (input) => ({ keyword: input }),
  },
  {
    value: 'author',
    label: '按作者名',
    placeholder: '输入作者名',
    toParams: (input) => ({ author_name: input }),
  },
]

export function PoemsPage() {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const keyword = searchParams.get('keyword') ?? ''
  const authorName = searchParams.get('author_name') ?? ''
  const [searchOpen, setSearchOpen] = useState(Boolean(keyword || authorName))
  const [searchMode, setSearchMode] = useState<PoemSearchMode>(authorName ? 'author' : 'title')
  const [searchInput, setSearchInput] = useState(authorName || keyword)
  const [editingPoem, setEditingPoem] = useState<PoemRead | null>(null)
  const [targetPoem, setTargetPoem] = useState<PoemRead | null>(null)
  const [selectedCollectionIds, setSelectedCollectionIds] = useState<number[]>([])
  const [formData, setFormData] = useState<PoemWritePayload>(EMPTY_FORM)
  const [collectionFormData, setCollectionFormData] = useState<CollectionWritePayload>(EMPTY_COLLECTION_FORM)
  const [formOpen, setFormOpen] = useState(false)
  const [collectionFormOpen, setCollectionFormOpen] = useState(false)
  const [collectionPickerOpen, setCollectionPickerOpen] = useState(false)
  const [message, setMessage] = useState('')

  const poemsQuery = useQuery({
    queryKey: ['poems', keyword, authorName],
    queryFn: () => listPoems({ keyword, author_name: authorName, limit: 20, offset: 0 }),
  })

  const authorsQuery = useQuery({
    queryKey: ['authors-options'],
    queryFn: async () => {
      const response = await listAuthors('', 100, 0)
      return response.items
    },
  })

  const collectionsQuery = useQuery({
    queryKey: ['collections', 'poem-add-picker'],
    queryFn: () => listCollections('', 100, 0),
    enabled: collectionPickerOpen,
  })

  const createMutation = useMutation({
    mutationFn: createPoem,
    onSuccess: () => {
      setMessage('诗词已新增')
      closeForm()
      queryClient.invalidateQueries({ queryKey: ['poems'] })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ poemId, payload }: { poemId: number; payload: PoemWritePayload }) =>
      updatePoem(poemId, payload),
    onSuccess: () => {
      setMessage('诗词已更新')
      closeForm()
      queryClient.invalidateQueries({ queryKey: ['poems'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deletePoem,
    onSuccess: () => {
      setMessage('诗词已删除')
      queryClient.invalidateQueries({ queryKey: ['poems'] })
    },
  })

  const createCollectionMutation = useMutation({
    mutationFn: createCollection,
    onSuccess: () => {
      setMessage('合集已新增')
      closeCollectionForm()
      queryClient.invalidateQueries({ queryKey: ['collections'] })
    },
  })

  const addToCollectionsMutation = useMutation({
    mutationFn: async ({ poemId, collectionIds }: { poemId: number; collectionIds: number[] }) => {
      const results = await Promise.allSettled(
        collectionIds.map((collectionId) => addPoemToCollection(collectionId, poemId)),
      )
      const alreadyExists = results.filter(
        (result) => result.status === 'rejected' && result.reason instanceof ApiError && result.reason.status === 409,
      ).length
      const failed = results.filter(
        (result) => result.status === 'rejected' && !(result.reason instanceof ApiError && result.reason.status === 409),
      ).length
      const succeeded = results.filter((result) => result.status === 'fulfilled').length

      return { alreadyExists, failed, succeeded }
    },
    onSuccess: ({ alreadyExists, failed, succeeded }) => {
      if (failed > 0) {
        setMessage('部分合集加入失败，请稍后重试')
      } else if (succeeded > 0 && alreadyExists > 0) {
        setMessage('已加入部分合集，已存在的合集已跳过')
        closeCollectionPicker()
      } else if (succeeded > 0) {
        setMessage('已加入选中合集')
        closeCollectionPicker()
      } else if (alreadyExists > 0) {
        setMessage('这首诗已在所选合集内')
      }

      queryClient.invalidateQueries({ queryKey: ['collection-poems'] })
    },
  })

  const isSubmitting =
    createMutation.isPending ||
    updateMutation.isPending ||
    deleteMutation.isPending ||
    createCollectionMutation.isPending ||
    addToCollectionsMutation.isPending

  const submitLabel = useMemo(() => (editingPoem ? '保存修改' : '新增诗词'), [editingPoem])
  const activeSearchMode = useMemo(
    () => SEARCH_MODES.find((mode) => mode.value === searchMode) ?? SEARCH_MODES[0],
    [searchMode],
  )
  const hasActiveSearch = Boolean(keyword || authorName)

  useEffect(() => {
    setSearchMode(authorName ? 'author' : 'title')
    setSearchInput(authorName || keyword)
    setSearchOpen(Boolean(keyword || authorName))
  }, [authorName, keyword])

  function getDefaultAuthorId() {
    return authorsQuery.data?.[0]?.id ?? 1
  }

  function clearSearchParams() {
    const next = new URLSearchParams(searchParams)
    next.delete('keyword')
    next.delete('author_name')
    setSearchParams(next)
  }

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const next = new URLSearchParams(searchParams)
    const normalizedInput = searchInput.trim()

    next.delete('keyword')
    next.delete('author_name')

    if (normalizedInput) {
      const params = activeSearchMode.toParams(normalizedInput)
      Object.entries(params).forEach(([key, value]) => {
        if (value) next.set(key, value)
      })
    }

    setSearchParams(next)
  }

  function handleResetSearch() {
    setSearchMode('title')
    setSearchInput('')
    setSearchOpen(false)
    clearSearchParams()
  }

  function handleToggleSearch() {
    if (searchOpen) {
      handleResetSearch()
      return
    }

    setSearchOpen(true)
  }

  function handleAddPoem() {
    setEditingPoem(null)
    setFormData({ ...EMPTY_FORM, author_id: getDefaultAuthorId() })
    setMessage('')
    setFormOpen(true)
  }

  function handleAddCollection() {
    setCollectionFormData(EMPTY_COLLECTION_FORM)
    setMessage('')
    setCollectionFormOpen(true)
  }

  function handleEdit(poem: PoemRead) {
    setEditingPoem(poem)
    setFormData({
      title: poem.title,
      content: poem.content,
      author_id: poem.author_id,
    })
    setMessage('')
    setFormOpen(true)
  }

  function handleOpenCollectionPicker(poem: PoemRead) {
    setTargetPoem(poem)
    setSelectedCollectionIds([])
    setMessage('')
    setCollectionPickerOpen(true)
  }

  function closeForm() {
    setFormOpen(false)
    setEditingPoem(null)
    setFormData({ ...EMPTY_FORM, author_id: getDefaultAuthorId() })
  }

  function closeCollectionForm() {
    setCollectionFormOpen(false)
    setCollectionFormData(EMPTY_COLLECTION_FORM)
  }

  function closeCollectionPicker() {
    setCollectionPickerOpen(false)
    setTargetPoem(null)
    setSelectedCollectionIds([])
  }

  function toggleCollection(collectionId: number) {
    setSelectedCollectionIds((prev) =>
      prev.includes(collectionId) ? prev.filter((item) => item !== collectionId) : [...prev, collectionId],
    )
  }

  function handleFormSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setMessage('')

    if (editingPoem) {
      updateMutation.mutate({ poemId: editingPoem.id, payload: formData })
      return
    }

    createMutation.mutate(formData)
  }

  function handleCollectionFormSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setMessage('')

    createCollectionMutation.mutate({
      ...collectionFormData,
      description: collectionFormData.description?.trim() ? collectionFormData.description.trim() : null,
    })
  }

  function handleAddToCollectionsSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!targetPoem || selectedCollectionIds.length === 0) return

    setMessage('')
    addToCollectionsMutation.mutate({ poemId: targetPoem.id, collectionIds: selectedCollectionIds })
  }

  return (
    <>
      <div className="page-grid page-grid-single">
        <PageSection
          title="诗词"
          subtitle="默认折叠展示，展开后查看作者和完整诗句。"
          actions={
            <div className="poem-search-wrap">
              <button
                className={hasActiveSearch ? 'icon-button poem-search-trigger poem-search-trigger-active' : 'icon-button poem-search-trigger'}
                type="button"
                aria-label={searchOpen ? '关闭搜索' : '打开搜索'}
                onClick={handleToggleSearch}
              >
                ⌕
              </button>
              {searchOpen ? (
                <form className="poem-search-panel" onSubmit={handleSearchSubmit}>
                  <select
                    className="input poem-search-mode"
                    value={searchMode}
                    onChange={(event) => setSearchMode(event.target.value as PoemSearchMode)}
                  >
                    {SEARCH_MODES.map((mode) => (
                      <option key={mode.value} value={mode.value}>
                        {mode.label}
                      </option>
                    ))}
                  </select>
                  <input
                    className="input poem-search-input"
                    placeholder={activeSearchMode.placeholder}
                    value={searchInput}
                    onChange={(event) => setSearchInput(event.target.value)}
                  />
                  <div className="poem-search-actions">
                    <button className="button button-primary" type="submit">
                      搜索
                    </button>
                    <button className="button" type="button" onClick={handleResetSearch}>
                      清空
                    </button>
                  </div>
                </form>
              ) : null}
            </div>
          }
        >
          {message ? <p className="hint">{message}</p> : null}
          {poemsQuery.isLoading ? <p className="hint">加载中...</p> : null}
          {poemsQuery.isError ? <p className="hint">加载失败，请检查后端服务。</p> : null}
          {deleteMutation.isError ? <p className="hint">删除失败，请稍后重试。</p> : null}
          {addToCollectionsMutation.isError ? <p className="hint">加入合集失败，请稍后重试。</p> : null}

          {poemsQuery.data && poemsQuery.data.items.length > 0 ? (
            <div className="card-list">
              {poemsQuery.data.items.map((poem) => (
                <CollapsiblePoemCard
                  key={poem.id}
                  id={poem.id}
                  title={poem.title}
                  author={poem.author}
                  content={poem.content}
                  onAddToCollection={() => handleOpenCollectionPicker(poem)}
                  onEdit={() => handleEdit(poem)}
                  onDelete={() => deleteMutation.mutate(poem.id)}
                  disabled={isSubmitting}
                />
              ))}
            </div>
          ) : null}

          {poemsQuery.data && poemsQuery.data.items.length === 0 ? (
            <EmptyState title="暂无诗词" description="可以先执行 make seed，或点击右下角加号新增诗词。" />
          ) : null}
        </PageSection>
      </div>

      {formOpen ? (
        <div className="modal-backdrop" role="presentation" onClick={closeForm}>
          <div className="modal-card" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>{editingPoem ? '编辑诗词' : '新增诗词'}</h2>
                <p>填写标题、作者和完整诗句内容。</p>
              </div>
              <button className="icon-button" type="button" aria-label="关闭" onClick={closeForm}>
                ×
              </button>
            </div>

            <form className="form-panel" onSubmit={handleFormSubmit}>
              <label className="field">
                <span>标题</span>
                <input
                  className="input"
                  value={formData.title}
                  onChange={(event) => setFormData((prev) => ({ ...prev, title: event.target.value }))}
                  required
                />
              </label>

              <label className="field">
                <span>作者</span>
                <select
                  className="input"
                  value={formData.author_id}
                  onChange={(event) =>
                    setFormData((prev) => ({ ...prev, author_id: Number(event.target.value) }))
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
                  value={formData.content}
                  onChange={(event) => setFormData((prev) => ({ ...prev, content: event.target.value }))}
                  required
                />
              </label>

              <div className="modal-actions">
                <button className="button button-primary" type="submit" disabled={isSubmitting}>
                  {submitLabel}
                </button>
                <button className="button" type="button" onClick={closeForm}>
                  取消
                </button>
              </div>

              {createMutation.isError ? <p className="hint">新增失败，请检查输入。</p> : null}
              {updateMutation.isError ? <p className="hint">更新失败，请检查输入。</p> : null}
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

            <form className="form-panel" onSubmit={handleCollectionFormSubmit}>
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

      {collectionPickerOpen && targetPoem ? (
        <div className="modal-backdrop" role="presentation" onClick={closeCollectionPicker}>
          <div className="modal-card" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>加入合集</h2>
                <p>选择一个或多个合集，将《{targetPoem.title}》加入其中。</p>
              </div>
              <button className="icon-button" type="button" aria-label="关闭" onClick={closeCollectionPicker}>
                ×
              </button>
            </div>

            <form className="form-panel" onSubmit={handleAddToCollectionsSubmit}>
              {collectionsQuery.isLoading ? <p className="hint">加载中...</p> : null}
              {collectionsQuery.isError ? <p className="hint">加载合集失败，请稍后重试。</p> : null}

              <div className="list-panel">
                {collectionsQuery.data?.items.map((collection) => (
                  <label className="list-row selection-row" key={collection.id}>
                    <input
                      type="checkbox"
                      checked={selectedCollectionIds.includes(collection.id)}
                      onChange={() => toggleCollection(collection.id)}
                    />
                    <span className="selection-main">
                      <span>{collection.name}</span>
                      <span className="muted">{collection.description || '暂无描述'}</span>
                    </span>
                    <span className="badge">#{collection.id}</span>
                  </label>
                ))}
              </div>

              {collectionsQuery.data && collectionsQuery.data.items.length === 0 ? (
                <EmptyState title="暂无合集" description="可以先通过右下角新增合集。" />
              ) : null}

              <div className="modal-actions">
                <button
                  className="button button-primary"
                  type="submit"
                  disabled={isSubmitting || selectedCollectionIds.length === 0}
                >
                  加入选中合集
                </button>
                <button className="button" type="button" onClick={closeCollectionPicker}>
                  取消
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </>
  )
}
