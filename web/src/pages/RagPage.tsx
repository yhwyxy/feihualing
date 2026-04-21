import { useMutation } from '@tanstack/react-query'
import { FormEvent, Fragment, useRef, useState } from 'react'

import { ApiError } from '../shared/api/http'
import { ragSearch, streamRagAsk } from '../shared/api/rag'
import { CollapsiblePoemCard } from '../shared/ui/CollapsiblePoemCard'
import type {
  RagAskDocChunkSource,
  RagAskPoemSource,
  RagAskSources,
  RagSearchResponse,
} from '../shared/types/api'

const TOP_K_OPTIONS = [3, 5, 10]

const EMPTY_SOURCES: RagAskSources = {
  poems: [],
  document_chunks: [],
}

function formatScore(score: number) {
  return Math.round(score * 1000)
}

function ScoreBadges({ score, sem, kw }: { score: number; sem: number; kw: number }) {
  const total = formatScore(score)
  const semVal = formatScore(sem)
  const kwVal = formatScore(kw)
  return (
    <span className="rag-score-group" title="RRF 融合分 = 1/(60+rank)。综合=语义+关键词。">
      <span className="rag-score-total">综合 {total}</span>
      <span className="rag-score-sub" title={`语义 RRF 分（×1000）`}>
        语义 {semVal}
      </span>
      <span
        className={kwVal > 0 ? 'rag-score-sub rag-score-sub-kw' : 'rag-score-sub rag-score-sub-empty'}
        title={`关键词 RRF 分（×1000）。0 表示关键词未命中。`}
      >
        关键词 {kwVal}
      </span>
    </span>
  )
}

function renderAnswer(text: string, sources: RagAskSources) {
  const parts = text.split(/(\[poem:\d+\]|\[doc:\d+#\d+\])/g)
  return parts.map((part, index) => {
    const poemMatch = part.match(/^\[poem:(\d+)\]$/)
    if (poemMatch) {
      const id = Number(poemMatch[1])
      const source = sources.poems.find((item) => item.id === id)
      const label = source ? `《${source.title}》` : `poem:${id}`
      return (
        <sup
          key={index}
          className="rag-citation"
          title={source ? `${source.title} · ${source.author ?? '佚名'}\n\n${source.content}` : `poem:${id}`}
        >
          {label}
        </sup>
      )
    }

    const docMatch = part.match(/^\[doc:(\d+)#(\d+)\]$/)
    if (docMatch) {
      const docId = Number(docMatch[1])
      const chunkIdx = Number(docMatch[2])
      const source = sources.document_chunks.find(
        (item) => item.document_id === docId && item.chunk_index === chunkIdx,
      )
      const label = source ? `《${source.document_title}》#${chunkIdx}` : `doc:${docId}#${chunkIdx}`
      return (
        <sup
          key={index}
          className="rag-citation rag-citation-doc"
          title={source ? `${source.document_title} · 片段 #${chunkIdx}\n\n${source.content}` : ''}
        >
          {label}
        </sup>
      )
    }

    return <Fragment key={index}>{part}</Fragment>
  })
}

export function RagPage() {
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(5)
  const [result, setResult] = useState<RagSearchResponse | null>(null)
  const [errorMessage, setErrorMessage] = useState('')

  const [answer, setAnswer] = useState('')
  const [answerSources, setAnswerSources] = useState<RagAskSources>(EMPTY_SOURCES)
  const [asking, setAsking] = useState(false)
  const [answerError, setAnswerError] = useState('')
  const askAbortRef = useRef<AbortController | null>(null)

  const searchMutation = useMutation({
    mutationFn: ragSearch,
    onSuccess: (data) => {
      setResult(data)
      setErrorMessage('')
    },
    onError: (error) => {
      setResult(null)
      if (error instanceof ApiError) {
        setErrorMessage(error.message)
      } else {
        setErrorMessage('检索失败，请稍后再试。')
      }
    },
  })

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmed = query.trim()
    if (!trimmed) {
      setErrorMessage('请输入查询内容。')
      return
    }
    setAnswer('')
    setAnswerSources(EMPTY_SOURCES)
    setAnswerError('')
    searchMutation.mutate({ query: trimmed, top_k: topK })
  }

  const handleAsk = async () => {
    const trimmed = query.trim()
    if (!trimmed) {
      setAnswerError('请先输入查询内容。')
      return
    }
    if (asking) return

    askAbortRef.current?.abort()
    const controller = new AbortController()
    askAbortRef.current = controller

    setAnswer('')
    setAnswerSources(EMPTY_SOURCES)
    setAnswerError('')
    setAsking(true)

    try {
      await streamRagAsk(
        { query: trimmed, top_k: topK },
        (event) => {
          if (event.type === 'sources') {
            setAnswerSources(event.sources)
          } else if (event.type === 'delta') {
            setAnswer((prev) => prev + event.text)
          } else if (event.type === 'error') {
            setAnswerError(event.message)
          }
        },
        controller.signal,
      )
    } catch (error) {
      if (controller.signal.aborted) {
        // 用户主动中断
      } else if (error instanceof Error) {
        setAnswerError(error.message)
      } else {
        setAnswerError('生成失败，请稍后再试。')
      }
    } finally {
      setAsking(false)
    }
  }

  const handleStopAsk = () => {
    askAbortRef.current?.abort()
    setAsking(false)
  }

  const loading = searchMutation.isPending
  const hasResult = !!result
  const noHits =
    hasResult &&
    result!.poems.length === 0 &&
    result!.authors.length === 0 &&
    result!.collections.length === 0 &&
    result!.document_chunks.length === 0
  const hasAnswer = answer.length > 0 || answerSources.poems.length > 0 || answerSources.document_chunks.length > 0 || asking || !!answerError

  return (
    <div className="rag-page">
      <header className="rag-header">
        <h1>语义搜索</h1>
        <p className="rag-subtitle">
          基于 bge-large-zh 本地向量检索，结合 qwen-plus 严格引用回答。
        </p>
      </header>

      <form className="rag-search-form" onSubmit={handleSubmit}>
        <input
          className="rag-search-input"
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="例如：思念家乡 / 李白的诗歌风格 / 登高远望"
          autoFocus
        />
        <label className="rag-topk-label">
          返回
          <select
            className="rag-topk-select"
            value={topK}
            onChange={(event) => setTopK(Number(event.target.value))}
          >
            {TOP_K_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          条
        </label>
        <button className="rag-search-submit" type="submit" disabled={loading}>
          {loading ? '检索中…' : '搜索'}
        </button>
        <button
          className="rag-ask-submit"
          type="button"
          onClick={asking ? handleStopAsk : handleAsk}
          disabled={!query.trim() && !asking}
        >
          {asking ? '停止生成' : '生成回答'}
        </button>
      </form>

      {errorMessage ? <div className="rag-error">{errorMessage}</div> : null}

      {hasAnswer ? (
        <section className="rag-answer">
          <header className="rag-answer-header">
            <h2>回答</h2>
            {asking ? <span className="rag-answer-status">生成中…</span> : null}
          </header>
          {answerError ? <div className="rag-error">{answerError}</div> : null}
          <div className="rag-answer-body">
            {answer ? renderAnswer(answer, answerSources) : <span className="rag-answer-placeholder">等待模型回复…</span>}
          </div>
          {answerSources.poems.length > 0 || answerSources.document_chunks.length > 0 ? (
            <footer className="rag-answer-sources">
              <span className="rag-answer-sources-label">参考来源</span>
              {answerSources.poems.map((source: RagAskPoemSource) => (
                <span key={`p-${source.id}`} className="rag-source-chip" title={source.content}>
                  《{source.title}》
                  {source.author ? ` · ${source.author}` : ''}
                </span>
              ))}
              {answerSources.document_chunks.map((source: RagAskDocChunkSource) => (
                <span
                  key={`d-${source.document_id}-${source.chunk_index}`}
                  className="rag-source-chip rag-source-chip-doc"
                  title={source.content}
                >
                  《{source.document_title}》#{source.chunk_index}
                </span>
              ))}
            </footer>
          ) : null}
        </section>
      ) : null}

      {hasResult && !noHits ? (
        <div className="rag-sections">
          {result!.poems.length > 0 ? (
            <section className="rag-section">
              <h2 className="rag-section-title">
                诗词 <span className="rag-section-count">{result!.poems.length}</span>
              </h2>
              <div className="rag-cards">
                {result!.poems.map((poem) => (
                  <div key={`poem-${poem.id}`} className="rag-card-wrap">
                    <ScoreBadges score={poem.score} sem={poem.sem_score} kw={poem.kw_score} />
                    <CollapsiblePoemCard
                      id={poem.id}
                      title={poem.title}
                      author={poem.author_name ?? '佚名'}
                      content={poem.content}
                    />
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {result!.document_chunks.length > 0 ? (
            <section className="rag-section">
              <h2 className="rag-section-title">
                文档片段 <span className="rag-section-count">{result!.document_chunks.length}</span>
              </h2>
              <div className="rag-doc-list">
                {result!.document_chunks.map((chunk) => (
                  <article key={`chunk-${chunk.chunk_id}`} className="rag-doc-card">
                    <header className="rag-doc-header">
                      <h3>
                        《{chunk.document_title}》
                        <span className="rag-doc-index">片段 #{chunk.chunk_index}</span>
                      </h3>
                      <ScoreBadges score={chunk.score} sem={chunk.sem_score} kw={chunk.kw_score} />
                    </header>
                    <p className="rag-doc-body">{chunk.content}</p>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {result!.authors.length > 0 ? (
            <section className="rag-section">
              <h2 className="rag-section-title">
                作者 <span className="rag-section-count">{result!.authors.length}</span>
              </h2>
              <div className="rag-meta-list">
                {result!.authors.map((author) => (
                  <article key={`author-${author.id}`} className="rag-meta-card">
                    <header className="rag-meta-header">
                      <h3>{author.name}</h3>
                      <ScoreBadges score={author.score} sem={author.sem_score} kw={author.kw_score} />
                    </header>
                    {author.bio ? <p className="rag-meta-body">{author.bio}</p> : null}
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {result!.collections.length > 0 ? (
            <section className="rag-section">
              <h2 className="rag-section-title">
                合集 <span className="rag-section-count">{result!.collections.length}</span>
              </h2>
              <div className="rag-meta-list">
                {result!.collections.map((collection) => (
                  <article key={`collection-${collection.id}`} className="rag-meta-card">
                    <header className="rag-meta-header">
                      <h3>{collection.name}</h3>
                      <ScoreBadges
                        score={collection.score}
                        sem={collection.sem_score}
                        kw={collection.kw_score}
                      />
                    </header>
                    {collection.description ? (
                      <p className="rag-meta-body">{collection.description}</p>
                    ) : null}
                  </article>
                ))}
              </div>
            </section>
          ) : null}
        </div>
      ) : null}

      {hasResult && noHits ? (
        <div className="rag-empty">没有相关结果，试试换个问法？</div>
      ) : null}
    </div>
  )
}
