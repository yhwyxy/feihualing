import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChangeEvent, FormEvent, useState } from 'react'

import {
  deleteDocument,
  listDocuments,
} from '../shared/api/documents'
import { ApiError } from '../shared/api/http'
import { importUnified, importUnifiedFile } from '../shared/api/imports'
import { parseCsvImport, parseImportText } from '../shared/lib/importParsing'
import type { BatchImportResponse, UnifiedImportPayload, UnifiedImportResponse } from '../shared/types/api'

const MAX_FILE_SIZE = 50 * 1024 * 1024
const STRUCTURED_EXTENSIONS = new Set(['json', 'csv'])
const SERVER_FILE_EXTENSIONS = new Set(['pdf'])
const TEXT_EXTENSIONS = new Set(['txt', 'md', 'markdown'])

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}

function formatImportSummary(result: BatchImportResponse | null) {
  if (!result) return '无结构化诗词入库'
  const { summary } = result
  return `新增 ${summary.poems.created} 首 / 匹配 ${summary.poems.matched} 首；作者新增 ${summary.authors.created} 位；合集新增 ${summary.collections.created} 个；收录关系新增 ${summary.collection_poems.created} 条。`
}

function extractionSourceLabel(source: UnifiedImportResponse['extraction']['source']) {
  switch (source) {
    case 'batch_payload':
      return '结构化文件'
    case 'llm':
      return 'AI 自动识别'
    case 'skipped':
      return '已跳过识别'
    case 'unavailable':
      return 'LLM 未配置'
    case 'failed':
      return '识别失败'
    default:
      return source
  }
}

export function DocumentsPage() {
  const queryClient = useQueryClient()

  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [sourceFilename, setSourceFilename] = useState<string>('')
  const [batchPayload, setBatchPayload] = useState<UnifiedImportPayload['batch_payload']>(null)
  const [serverFile, setServerFile] = useState<File | null>(null)
  const [extractPoems, setExtractPoems] = useState(true)
  const [errorMessage, setErrorMessage] = useState('')
  const [successResult, setSuccessResult] = useState<UnifiedImportResponse | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['documents'],
    queryFn: () => listDocuments({ limit: 50 }),
    refetchInterval: 5000,
  })

  const resetForm = () => {
    setTitle('')
    setContent('')
    setSourceFilename('')
    setBatchPayload(null)
    setServerFile(null)
  }

  const onUnifiedSuccess = (result: UnifiedImportResponse) => {
    setSuccessResult(result)
    setErrorMessage('')
    resetForm()
    queryClient.invalidateQueries({ queryKey: ['documents'] })
    queryClient.invalidateQueries({ queryKey: ['poems'] })
    queryClient.invalidateQueries({ queryKey: ['authors'] })
    queryClient.invalidateQueries({ queryKey: ['authors-options'] })
    queryClient.invalidateQueries({ queryKey: ['collections'] })
    queryClient.invalidateQueries({ queryKey: ['author-poems'] })
    queryClient.invalidateQueries({ queryKey: ['collection-poems'] })
  }

  const unifiedMutation = useMutation({
    mutationFn: importUnified,
    onSuccess: onUnifiedSuccess,
    onError: (error) => {
      setSuccessResult(null)
      setErrorMessage(error instanceof ApiError ? error.message : '导入失败，请稍后重试。')
    },
  })

  const unifiedFileMutation = useMutation({
    mutationFn: importUnifiedFile,
    onSuccess: onUnifiedSuccess,
    onError: (error) => {
      setSuccessResult(null)
      setErrorMessage(error instanceof ApiError ? error.message : '文件导入失败，请稍后重试。')
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
    if (!TEXT_EXTENSIONS.has(ext) && !STRUCTURED_EXTENSIONS.has(ext) && !SERVER_FILE_EXTENSIONS.has(ext)) {
      setErrorMessage('仅支持 .txt / .md / .markdown / .json / .csv / .pdf 文件')
      return
    }

    setSuccessResult(null)
    setBatchPayload(null)
    setServerFile(null)
    setSourceFilename(file.name)
    if (!title.trim()) {
      setTitle(file.name.replace(/\.(txt|md|markdown|json|csv|pdf)$/i, ''))
    }

    if (SERVER_FILE_EXTENSIONS.has(ext)) {
      setContent('')
      setServerFile(file)
      setErrorMessage('')
      return
    }

    try {
      const text = await file.text()
      setContent(text)
      if (ext === 'json') {
        setBatchPayload(parseImportText(text))
      } else if (ext === 'csv') {
        setBatchPayload(parseCsvImport(text))
      }
      setErrorMessage('')
    } catch (error) {
      setBatchPayload(null)
      setErrorMessage(error instanceof Error ? error.message : '读取文件失败')
    }
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmedTitle = title.trim()
    if (!trimmedTitle) {
      setErrorMessage('请填写标题')
      return
    }

    if (serverFile) {
      const formData = new FormData()
      formData.append('file', serverFile)
      formData.append('title', trimmedTitle)
      formData.append('extract_poems', String(extractPoems))
      formData.append('max_extracted_poems', '80')
      unifiedFileMutation.mutate(formData)
      return
    }

    const trimmedContent = content.trim()
    if (!trimmedContent) {
      setErrorMessage('请粘贴或上传资料内容')
      return
    }

    const payload: UnifiedImportPayload = {
      title: trimmedTitle,
      content: trimmedContent,
      source_filename: sourceFilename || null,
      batch_payload: batchPayload,
      extract_poems: extractPoems,
      max_extracted_poems: 80,
    }
    unifiedMutation.mutate(payload)
  }

  const handleDelete = (id: number, title: string) => {
    if (!confirm(`确定删除《${title}》？对应的所有向量片段也会一起删除。`)) return
    deleteMutation.mutate(id)
  }

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

  const pending = unifiedMutation.isPending || unifiedFileMutation.isPending

  return (
    <div className="documents-page">
      <header className="documents-header">
        <h1>导入中心</h1>
        <p className="documents-subtitle">
          所有资料都会进入 RAG 文档库并向量化；系统会自动识别诗词，成功后同步写入诗词库。
        </p>
      </header>

      <section className="documents-upload">
        <h2>导入资料</h2>
        <form className="documents-upload-form" onSubmit={handleSubmit}>
          <label className="documents-field">
            <span>标题</span>
            <input
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="例如：唐诗三百首"
              maxLength={200}
            />
          </label>

          <label className="documents-field documents-switch-row">
            <span>
              自动识别诗词
              <span className="documents-hint"> （关闭后只进入 RAG，不写入诗词库）</span>
            </span>
            <input
              type="checkbox"
              checked={extractPoems}
              onChange={(event) => setExtractPoems(event.target.checked)}
            />
          </label>

          <label className="documents-field">
            <span>
              内容
              <span className="documents-hint"> （粘贴文本，或选择文件）</span>
            </span>
            <textarea
              className="documents-textarea"
              value={serverFile ? `已选择 PDF：${serverFile.name}（内容由后端解析）` : content}
              onChange={(event) => {
                setServerFile(null)
                setSourceFilename('')
                setBatchPayload(null)
                setContent(event.target.value)
              }}
              disabled={Boolean(serverFile)}
              placeholder="粘贴 txt / md 内容；JSON/CSV 文件会自动识别为结构化导入；PDF 将由后端提取文本。"
            />
          </label>

          <div className="documents-upload-actions">
            <label className="documents-file-pick">
              <input
                type="file"
                accept=".txt,.md,.markdown,.json,.csv,.pdf,text/plain,text/markdown,application/json,text/csv,application/pdf"
                onChange={handleFileChange}
                hidden
              />
              <span>选择资料文件</span>
            </label>
            {sourceFilename ? (
              <span className="documents-file-hint">
                已读取：{sourceFilename}{batchPayload ? ' · 结构化诗词导入' : serverFile ? ' · PDF 服务端解析' : ''}
              </span>
            ) : null}
            <div className="documents-upload-spacer" />
            <button
              type="submit"
              className="documents-upload-submit"
              disabled={pending}
            >
              {pending ? '导入中…' : '导入并处理'}
            </button>
          </div>

          {errorMessage ? <div className="documents-error">{errorMessage}</div> : null}
          {successResult ? (
            <div className="documents-success">
              <strong>《{successResult.document.title}》已导入</strong>
              <p>{successResult.document.chunk_count} 个 RAG 片段，后台向量化中。</p>
              <p>
                诗词识别：{extractionSourceLabel(successResult.extraction.source)}；识别 {successResult.extraction.extracted_poem_count} 首。
              </p>
              <p>{formatImportSummary(successResult.extraction.imported)}</p>
              {successResult.extraction.warnings.length ? (
                <ul className="documents-warning-list">
                  {successResult.extraction.warnings.map((warning, index) => (
                    <li key={`${warning.code}-${index}`}>{warning.message}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
        </form>
      </section>

      <section className="documents-list-section">
        <h2>
          RAG 文档库
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
          <div className="documents-empty">还没有导入过资料。</div>
        )}
      </section>
    </div>
  )
}
