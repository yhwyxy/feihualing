import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChangeEvent, FormEvent, useState } from 'react'

import {
  deleteDocument,
  listDocuments,
  uploadDocument,
} from '../shared/api/documents'
import { ApiError } from '../shared/api/http'
import type { DocumentUploadPayload } from '../shared/types/api'

const MAX_FILE_SIZE = 5 * 1024 * 1024

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}

export function DocumentsPage() {
  const queryClient = useQueryClient()

  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [sourceFilename, setSourceFilename] = useState<string>('')
  const [errorMessage, setErrorMessage] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  const { data, isLoading, isError } = useQuery({
    queryKey: ['documents'],
    queryFn: () => listDocuments({ limit: 50 }),
    refetchInterval: 5000,
  })

  const uploadMutation = useMutation({
    mutationFn: uploadDocument,
    onSuccess: (doc) => {
      setSuccessMessage(`《${doc.title}》已上传，共 ${doc.chunk_count} 个片段，正在后台向量化…`)
      setErrorMessage('')
      setTitle('')
      setContent('')
      setSourceFilename('')
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: (error) => {
      setSuccessMessage('')
      if (error instanceof ApiError) {
        setErrorMessage(error.message)
      } else {
        setErrorMessage('上传失败，请稍后重试。')
      }
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        setErrorMessage(error.message)
      } else {
        setErrorMessage('删除失败。')
      }
    },
  })

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (file.size > MAX_FILE_SIZE) {
      setErrorMessage(`文件过大（>${Math.round(MAX_FILE_SIZE / 1024 / 1024)} MB）`)
      return
    }
    const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
    if (ext !== 'txt' && ext !== 'md' && ext !== 'markdown') {
      setErrorMessage('仅支持 .txt / .md 文件')
      return
    }
    try {
      const text = await file.text()
      setContent(text)
      setSourceFilename(file.name)
      if (!title.trim()) {
        setTitle(file.name.replace(/\.(txt|md|markdown)$/i, ''))
      }
      setErrorMessage('')
    } catch {
      setErrorMessage('读取文件失败')
    }
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmedTitle = title.trim()
    const trimmedContent = content.trim()
    if (!trimmedTitle) {
      setErrorMessage('请填写文档标题')
      return
    }
    if (!trimmedContent) {
      setErrorMessage('请粘贴或上传文档内容')
      return
    }
    const payload: DocumentUploadPayload = {
      title: trimmedTitle,
      content: trimmedContent,
      source_filename: sourceFilename || null,
    }
    uploadMutation.mutate(payload)
  }

  const handleDelete = (id: number, title: string) => {
    if (!confirm(`确定删除《${title}》？对应的所有向量片段也会一起删除。`)) return
    deleteMutation.mutate(id)
  }

  return (
    <div className="documents-page">
      <header className="documents-header">
        <h1>文档库</h1>
        <p className="documents-subtitle">
          上传 txt / md 长文档，自动切分 + 向量化，供 RAG 搜索和问答引用。
        </p>
      </header>

      <section className="documents-upload">
        <h2>上传新文档</h2>
        <form className="documents-upload-form" onSubmit={handleSubmit}>
          <label className="documents-field">
            <span>标题</span>
            <input
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="例如：李白评传"
              maxLength={200}
            />
          </label>

          <label className="documents-field">
            <span>
              内容
              <span className="documents-hint">
                {' '}
                （粘贴文本，或从右侧选文件）
              </span>
            </span>
            <textarea
              className="documents-textarea"
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="粘贴长文内容，支持中文段落（按 \n\n 自动切分）"
            />
          </label>

          <div className="documents-upload-actions">
            <label className="documents-file-pick">
              <input
                type="file"
                accept=".txt,.md,.markdown,text/plain,text/markdown"
                onChange={handleFileChange}
                hidden
              />
              <span>选择 .txt / .md 文件</span>
            </label>
            {sourceFilename ? (
              <span className="documents-file-hint">已读取：{sourceFilename}</span>
            ) : null}
            <div className="documents-upload-spacer" />
            <button
              type="submit"
              className="documents-upload-submit"
              disabled={uploadMutation.isPending}
            >
              {uploadMutation.isPending ? '上传中…' : '上传并向量化'}
            </button>
          </div>

          {errorMessage ? <div className="documents-error">{errorMessage}</div> : null}
          {successMessage ? <div className="documents-success">{successMessage}</div> : null}
        </form>
      </section>

      <section className="documents-list-section">
        <h2>
          已上传文档
          {data ? <span className="documents-count">（{data.total}）</span> : null}
        </h2>
        {isLoading ? (
          <div className="documents-empty">加载中…</div>
        ) : isError ? (
          <div className="documents-error">加载文档列表失败</div>
        ) : data && data.items.length > 0 ? (
          <div className="documents-list">
            {data.items.map((doc) => {
              const embedding_progress =
                doc.chunk_count > 0
                  ? Math.round((doc.embedded_count / doc.chunk_count) * 100)
                  : 0
              const done = doc.chunk_count > 0 && doc.embedded_count === doc.chunk_count
              return (
                <article key={doc.id} className="documents-item">
                  <header className="documents-item-header">
                    <h3>{doc.title}</h3>
                    <div className="documents-item-actions">
                      <span
                        className={
                          done ? 'documents-badge documents-badge-done' : 'documents-badge'
                        }
                      >
                        {done
                          ? `${doc.chunk_count} 片段 · 已向量化`
                          : `${doc.embedded_count}/${doc.chunk_count} 片段 · ${embedding_progress}%`}
                      </span>
                      <button
                        type="button"
                        className="documents-delete"
                        onClick={() => handleDelete(doc.id, doc.title)}
                      >
                        删除
                      </button>
                    </div>
                  </header>
                  <div className="documents-item-meta">
                    {doc.source_filename ? <span>源文件：{doc.source_filename}</span> : null}
                    <span>上传于 {formatDate(doc.created_at)}</span>
                  </div>
                </article>
              )
            })}
          </div>
        ) : (
          <div className="documents-empty">还没有上传过文档。</div>
        )}
      </section>
    </div>
  )
}
