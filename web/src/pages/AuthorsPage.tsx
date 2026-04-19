import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FormEvent, useMemo, useState } from 'react'

import type { AuthorRead, AuthorWritePayload } from '../shared/types/api'
import { deleteAuthor, getAuthorPoems, listAuthors, updateAuthor } from '../shared/api/authors'
import { ApiError } from '../shared/api/http'
import { EmptyState } from '../shared/ui/EmptyState'
import { CollapsiblePoemCard } from '../shared/ui/CollapsiblePoemCard'
import { PageSection } from '../shared/ui/PageSection'

const EMPTY_FORM: AuthorWritePayload = {
  name: '',
  bio: '',
}

export function AuthorsPage() {
  const queryClient = useQueryClient()
  const [keyword, setKeyword] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  const [selectedAuthorId, setSelectedAuthorId] = useState<number | null>(null)
  const [openMenuAuthorId, setOpenMenuAuthorId] = useState<number | null>(null)
  const [editingAuthor, setEditingAuthor] = useState<AuthorRead | null>(null)
  const [formData, setFormData] = useState<AuthorWritePayload>(EMPTY_FORM)
  const [formOpen, setFormOpen] = useState(false)
  const [message, setMessage] = useState('')

  const authorsQuery = useQuery({
    queryKey: ['authors', keyword],
    queryFn: () => listAuthors(keyword, 20, 0),
  })

  const selectedAuthor = authorsQuery.data?.items.find((item) => item.id === selectedAuthorId) ?? null
  const hasActiveSearch = Boolean(keyword)

  const poemsQuery = useQuery({
    queryKey: ['author-poems', selectedAuthorId],
    queryFn: () => getAuthorPoems(selectedAuthorId!, 20, 0),
    enabled: selectedAuthorId !== null,
  })

  const updateMutation = useMutation({
    mutationFn: ({ authorId, payload }: { authorId: number; payload: AuthorWritePayload }) =>
      updateAuthor(authorId, payload),
    onSuccess: (author) => {
      setMessage('作者已更新')
      setSelectedAuthorId(author.id)
      closeForm()
      queryClient.invalidateQueries({ queryKey: ['authors'] })
      queryClient.invalidateQueries({ queryKey: ['authors-options'] })
    },
    onError: () => {
      setMessage('更新作者失败，请稍后重试')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteAuthor,
    onSuccess: (_, authorId) => {
      setMessage('作者已删除')
      if (selectedAuthorId === authorId) setSelectedAuthorId(null)
      queryClient.invalidateQueries({ queryKey: ['authors'] })
      queryClient.invalidateQueries({ queryKey: ['authors-options'] })
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        setMessage('请先删除作者名下所有诗词')
        return
      }

      setMessage('删除作者失败，请稍后重试')
    },
  })

  const isSubmitting = updateMutation.isPending || deleteMutation.isPending
  const submitLabel = useMemo(() => '保存修改', [])

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

  function handleEditAuthor(author: AuthorRead) {
    setOpenMenuAuthorId(null)
    setEditingAuthor(author)
    setFormData({
      name: author.name,
      bio: author.bio ?? '',
    })
    setMessage('')
    setFormOpen(true)
  }

  function closeForm() {
    setFormOpen(false)
    setEditingAuthor(null)
    setFormData(EMPTY_FORM)
  }

  function handleToggleAuthorMenu(authorId: number) {
    setOpenMenuAuthorId((current) => (current === authorId ? null : authorId))
  }

  function handleDeleteAuthor(authorId: number) {
    setOpenMenuAuthorId(null)
    deleteMutation.mutate(authorId)
  }

  function handleFormSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editingAuthor) return

    setMessage('')
    updateMutation.mutate({
      authorId: editingAuthor.id,
      payload: {
        ...formData,
        bio: formData.bio?.trim() ? formData.bio.trim() : null,
      },
    })
  }

  return (
    <>
      <div className="page-grid page-grid-split">
        <PageSection
          title="作者"
          subtitle="选择作者后，在右侧查看详情与名下诗词。"
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
                    placeholder="按作者名搜索"
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
          {authorsQuery.isLoading ? <p className="hint">加载中...</p> : null}
          {authorsQuery.isError ? <p className="hint">加载失败，请检查后端服务。</p> : null}

          <div className="list-panel">
            {authorsQuery.data?.items.map((author) => (
              <div key={author.id} className={selectedAuthorId === author.id ? 'list-row list-row-active' : 'list-row'}>
                <button className="list-row-main" onClick={() => setSelectedAuthorId(author.id)} type="button">
                  <span>{author.name}</span>
                  <span className="muted">#{author.id}</span>
                </button>
                <div className="menu-wrap">
                  <button
                    className="icon-button"
                    type="button"
                    aria-label="更多操作"
                    aria-expanded={openMenuAuthorId === author.id}
                    onClick={() => handleToggleAuthorMenu(author.id)}
                  >
                    ⋯
                  </button>
                  {openMenuAuthorId === author.id ? (
                    <div className="popup-menu">
                      <button type="button" onClick={() => handleEditAuthor(author)}>
                        编辑
                      </button>
                      <button
                        className="danger-text"
                        type="button"
                        disabled={deleteMutation.isPending}
                        onClick={() => handleDeleteAuthor(author.id)}
                      >
                        删除
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
          </div>

          {authorsQuery.data && authorsQuery.data.items.length === 0 ? (
            <EmptyState title="暂无作者" description="先执行 make seed，或稍后接入新增作者表单。" />
          ) : null}
        </PageSection>

        <PageSection title="作者详情" subtitle="作者名下诗词默认折叠，展开后再看作者和内容。">
          {!selectedAuthor ? <EmptyState title="未选择作者" description="从左侧列表选择一个作者。" /> : null}

          {selectedAuthor ? (
            <div className="detail-panel">
              <div className="detail-card">
                <h3>{selectedAuthor.name}</h3>
                <p>{selectedAuthor.bio || '暂无简介'}</p>
              </div>

              <div className="detail-card">
                <h3>作者名下诗词</h3>
                {poemsQuery.isLoading ? <p className="hint">加载中...</p> : null}
                <div className="card-list">
                  {poemsQuery.data?.items.map((poem) => (
                    <CollapsiblePoemCard
                      key={poem.id}
                      id={poem.id}
                      title={poem.title}
                      author={poem.author}
                      content={poem.content}
                    />
                  ))}
                </div>
              </div>
            </div>
          ) : null}
        </PageSection>
      </div>

      {formOpen && editingAuthor ? (
        <div className="modal-backdrop" role="presentation" onClick={closeForm}>
          <div className="modal-card" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>编辑作者</h2>
                <p>填写作者姓名和简介。</p>
              </div>
              <button className="icon-button" type="button" aria-label="关闭" onClick={closeForm}>
                ×
              </button>
            </div>

            <form className="form-panel" onSubmit={handleFormSubmit}>
              <label className="field">
                <span>姓名</span>
                <input
                  className="input"
                  value={formData.name}
                  onChange={(event) => setFormData((prev) => ({ ...prev, name: event.target.value }))}
                  required
                />
              </label>

              <label className="field">
                <span>简介</span>
                <textarea
                  className="input textarea textarea-sm"
                  value={formData.bio ?? ''}
                  onChange={(event) => setFormData((prev) => ({ ...prev, bio: event.target.value }))}
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
            </form>
          </div>
        </div>
      ) : null}
    </>
  )
}
