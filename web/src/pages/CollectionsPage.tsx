import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FormEvent, useMemo, useState } from 'react'

import {
  createCollection,
  deleteCollection,
  getCollectionPoems,
  listCollections,
  removePoemFromCollection,
  replaceCollectionPoems,
  updateCollection,
} from '../shared/api/collections'
import { listPoems } from '../shared/api/poems'
import type { CollectionRead, CollectionWritePayload } from '../shared/types/api'
import { EmptyState } from '../shared/ui/EmptyState'
import { CollapsiblePoemCard } from '../shared/ui/CollapsiblePoemCard'
import { PageSection } from '../shared/ui/PageSection'

const EMPTY_FORM: CollectionWritePayload = {
  name: '',
  description: '',
}

export function CollectionsPage() {
  const queryClient = useQueryClient()
  const [keyword, setKeyword] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  const [selectedCollectionId, setSelectedCollectionId] = useState<number | null>(null)
  const [openMenuCollectionId, setOpenMenuCollectionId] = useState<number | null>(null)
  const [editingCollection, setEditingCollection] = useState<CollectionRead | null>(null)
  const [formData, setFormData] = useState<CollectionWritePayload>(EMPTY_FORM)
  const [formOpen, setFormOpen] = useState(false)
  const [replaceModalOpen, setReplaceModalOpen] = useState(false)
  const [replacePoemIds, setReplacePoemIds] = useState<number[]>([])
  const [message, setMessage] = useState('')

  const collectionsQuery = useQuery({
    queryKey: ['collections', keyword],
    queryFn: () => listCollections(keyword, 20, 0),
  })

  const selectedCollection =
    collectionsQuery.data?.items.find((item) => item.id === selectedCollectionId) ?? null
  const hasActiveSearch = Boolean(keyword)

  const poemsQuery = useQuery({
    queryKey: ['collection-poems', selectedCollectionId],
    queryFn: () => getCollectionPoems(selectedCollectionId!, 20, 0),
    enabled: selectedCollectionId !== null,
  })

  const poemCandidatesQuery = useQuery({
    queryKey: ['poems', 'collection-replace-picker'],
    queryFn: () => listPoems({ limit: 100, offset: 0 }),
    enabled: replaceModalOpen,
  })

  const createMutation = useMutation({
    mutationFn: createCollection,
    onSuccess: (collection) => {
      setMessage('合集已新增')
      setSelectedCollectionId(collection.id)
      closeForm()
      queryClient.invalidateQueries({ queryKey: ['collections'] })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ collectionId, payload }: { collectionId: number; payload: CollectionWritePayload }) =>
      updateCollection(collectionId, payload),
    onSuccess: (collection) => {
      setMessage('合集已更新')
      setSelectedCollectionId(collection.id)
      closeForm()
      queryClient.invalidateQueries({ queryKey: ['collections'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteCollection,
    onSuccess: (_, collectionId) => {
      setMessage('合集已删除')
      if (selectedCollectionId === collectionId) setSelectedCollectionId(null)
      queryClient.invalidateQueries({ queryKey: ['collections'] })
    },
  })

  const removePoemMutation = useMutation({
    mutationFn: ({ collectionId, poemId }: { collectionId: number; poemId: number }) =>
      removePoemFromCollection(collectionId, poemId),
    onSuccess: (_, { collectionId }) => {
      setMessage('已从合集中移除')
      queryClient.invalidateQueries({ queryKey: ['collection-poems', collectionId] })
    },
  })

  const replacePoemsMutation = useMutation({
    mutationFn: ({ collectionId, poemIds }: { collectionId: number; poemIds: number[] }) =>
      replaceCollectionPoems(collectionId, poemIds),
    onSuccess: (_, { collectionId }) => {
      setMessage('合集收录已更新')
      closeReplaceModal()
      queryClient.invalidateQueries({ queryKey: ['collection-poems', collectionId] })
    },
  })

  const isSubmitting =
    createMutation.isPending ||
    updateMutation.isPending ||
    deleteMutation.isPending ||
    removePoemMutation.isPending ||
    replacePoemsMutation.isPending
  const submitLabel = useMemo(() => (editingCollection ? '保存修改' : '新增合集'), [editingCollection])

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setKeyword(searchInput.trim())
  }

  function handleResetSearch() {
    setSearchInput('')
    setKeyword('')
    setSearchOpen(false)
  }

  function handleToggleSearch() {
    if (searchOpen) {
      handleResetSearch()
      return
    }

    setSearchOpen(true)
  }

  function handleAddCollection() {
    setEditingCollection(null)
    setFormData(EMPTY_FORM)
    setMessage('')
    setFormOpen(true)
  }

  function handleEditCollection(collection: CollectionRead) {
    setOpenMenuCollectionId(null)
    setEditingCollection(collection)
    setFormData({
      name: collection.name,
      description: collection.description ?? '',
    })
    setMessage('')
    setFormOpen(true)
  }

  function handleOpenReplaceModal() {
    if (!selectedCollection) return

    setReplacePoemIds(poemsQuery.data?.items.map((item: { poem: { id: number } }) => item.poem.id) ?? [])
    setMessage('')
    setReplaceModalOpen(true)
  }

  function closeForm() {
    setFormOpen(false)
    setEditingCollection(null)
    setFormData(EMPTY_FORM)
  }

  function closeReplaceModal() {
    setReplaceModalOpen(false)
    setReplacePoemIds([])
  }

  function handleToggleCollectionMenu(collectionId: number) {
    setOpenMenuCollectionId((current) => (current === collectionId ? null : collectionId))
  }

  function handleDeleteCollection(collectionId: number) {
    setOpenMenuCollectionId(null)
    deleteMutation.mutate(collectionId)
  }

  function toggleReplacePoem(poemId: number) {
    setReplacePoemIds((prev) =>
      prev.includes(poemId) ? prev.filter((item) => item !== poemId) : [...prev, poemId],
    )
  }

  function handleFormSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setMessage('')

    const payload = {
      ...formData,
      description: formData.description?.trim() ? formData.description.trim() : null,
    }

    if (editingCollection) {
      updateMutation.mutate({ collectionId: editingCollection.id, payload })
      return
    }

    createMutation.mutate(payload)
  }

  function handleReplaceFormSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedCollection) return

    setMessage('')
    replacePoemsMutation.mutate({ collectionId: selectedCollection.id, poemIds: replacePoemIds })
  }

  return (
    <>
      <div className="page-grid page-grid-split">
        <PageSection
          title="合集"
          subtitle="选择合集后，在右侧查看收录内容。"
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
                <form className="poem-search-panel poem-search-panel-single" onSubmit={handleSearchSubmit}>
                  <input
                    className="input poem-search-input"
                    placeholder="按合集名搜索"
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
          {collectionsQuery.isLoading ? <p className="hint">加载中...</p> : null}
          {collectionsQuery.isError ? <p className="hint">加载失败，请检查后端服务。</p> : null}
          {deleteMutation.isError ? <p className="hint">删除失败，请稍后重试。</p> : null}
          {removePoemMutation.isError ? <p className="hint">移出合集失败，请稍后重试。</p> : null}

          <div className="list-panel">
            {collectionsQuery.data?.items.map((collection) => (
              <div
                key={collection.id}
                className={selectedCollectionId === collection.id ? 'list-row list-row-active' : 'list-row'}
              >
                <button className="list-row-main" onClick={() => setSelectedCollectionId(collection.id)} type="button">
                  <span>{collection.name}</span>
                  <span className="muted">#{collection.id}</span>
                </button>
                <div className="menu-wrap">
                  <button
                    className="icon-button"
                    type="button"
                    aria-label="更多操作"
                    aria-expanded={openMenuCollectionId === collection.id}
                    onClick={() => handleToggleCollectionMenu(collection.id)}
                  >
                    ⋯
                  </button>
                  {openMenuCollectionId === collection.id ? (
                    <div className="popup-menu">
                      <button type="button" onClick={() => handleEditCollection(collection)}>
                        编辑
                      </button>
                      <button
                        className="danger-text"
                        type="button"
                        disabled={isSubmitting}
                        onClick={() => handleDeleteCollection(collection.id)}
                      >
                        删除
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
          </div>

          {collectionsQuery.data && collectionsQuery.data.items.length === 0 ? (
            <EmptyState title="暂无合集" description="点击新增合集，创建一个诗词合集。" />
          ) : null}
        </PageSection>

        <PageSection
          title="合集详情"
          subtitle="收录诗词默认折叠，展开后查看作者和具体内容。"
          actions={
            selectedCollection ? (
              <button className="button button-primary" type="button" onClick={handleOpenReplaceModal}>
                管理收录
              </button>
            ) : null
          }
        >
          {!selectedCollection ? <EmptyState title="未选择合集" description="从左侧列表选择一个合集。" /> : null}

          {selectedCollection ? (
            <div className="detail-panel">
              <div className="detail-card">
                <h3>{selectedCollection.name}</h3>
                <p>{selectedCollection.description || '暂无描述'}</p>
              </div>

              <div className="detail-card">
                <h3>收录诗词</h3>
                {poemsQuery.isLoading ? <p className="hint">加载中...</p> : null}
                {replacePoemsMutation.isError ? <p className="hint">更新收录失败，请稍后重试。</p> : null}
                <div className="card-list">
                  {poemsQuery.data?.items.map((item: { poem: { id: number; title: string; author: string; content: string } }) => (
                    <CollapsiblePoemCard
                      key={item.poem.id}
                      id={item.poem.id}
                      title={item.poem.title}
                      author={item.poem.author}
                      content={item.poem.content}
                      onDelete={() => removePoemMutation.mutate({ collectionId: selectedCollection.id, poemId: item.poem.id })}
                      deleteLabel="移出合集"
                      disabled={isSubmitting}
                    />
                  ))}
                </div>
                {poemsQuery.data && poemsQuery.data.items.length === 0 ? (
                  <EmptyState title="暂无诗词" description="点击管理收录，为这个合集添加诗词。" />
                ) : null}
              </div>
            </div>
          ) : null}
        </PageSection>
      </div>

      {formOpen ? (
        <div className="modal-backdrop" role="presentation" onClick={closeForm}>
          <div className="modal-card" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>{editingCollection ? '编辑合集' : '新增合集'}</h2>
                <p>填写合集名称和描述。</p>
              </div>
              <button className="icon-button" type="button" aria-label="关闭" onClick={closeForm}>
                ×
              </button>
            </div>

            <form className="form-panel" onSubmit={handleFormSubmit}>
              <label className="field">
                <span>名称</span>
                <input
                  className="input"
                  value={formData.name}
                  onChange={(event) => setFormData((prev) => ({ ...prev, name: event.target.value }))}
                  required
                />
              </label>

              <label className="field">
                <span>描述</span>
                <textarea
                  className="input textarea textarea-sm"
                  value={formData.description ?? ''}
                  onChange={(event) => setFormData((prev) => ({ ...prev, description: event.target.value }))}
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

      {replaceModalOpen && selectedCollection ? (
        <div className="modal-backdrop" role="presentation" onClick={closeReplaceModal}>
          <div className="modal-card" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>管理收录</h2>
                <p>勾选后保存，将用当前选择替换《{selectedCollection.name}》的全部收录内容。</p>
              </div>
              <button className="icon-button" type="button" aria-label="关闭" onClick={closeReplaceModal}>
                ×
              </button>
            </div>

            <form className="form-panel" onSubmit={handleReplaceFormSubmit}>
              {poemCandidatesQuery.isLoading ? <p className="hint">加载中...</p> : null}
              {poemCandidatesQuery.isError ? <p className="hint">加载诗词失败，请稍后重试。</p> : null}

              <div className="list-panel">
                {poemCandidatesQuery.data?.items.map((poem) => (
                  <label className="list-row selection-row" key={poem.id}>
                    <input
                      type="checkbox"
                      checked={replacePoemIds.includes(poem.id)}
                      onChange={() => toggleReplacePoem(poem.id)}
                    />
                    <span className="selection-main">
                      <span>{poem.title}</span>
                      <span className="muted">{poem.author}</span>
                    </span>
                    <span className="badge">#{poem.id}</span>
                  </label>
                ))}
              </div>

              {poemCandidatesQuery.data && poemCandidatesQuery.data.items.length === 0 ? (
                <EmptyState title="暂无诗词" description="请先在诗词页新增诗词。" />
              ) : null}

              <div className="modal-actions">
                <button className="button button-primary" type="submit" disabled={isSubmitting}>
                  保存收录
                </button>
                <button className="button" type="button" onClick={closeReplaceModal}>
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
