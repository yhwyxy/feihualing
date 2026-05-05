import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FormEvent, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import {
  createConceptAlias,
  deleteConceptAlias,
  getParseJob,
  getConceptGraph,
  listConceptAliases,
  listConcepts,
  listParseJobs,
} from '../shared/api/concepts'
import type { ConceptType } from '../shared/types/api'
import { EmptyState } from '../shared/ui/EmptyState'
import { PageSection } from '../shared/ui/PageSection'

const CONCEPT_TYPES: Array<{ value: '' | ConceptType; label: string }> = [
  { value: '', label: '全部' },
  { value: 'char', label: '字' },
  { value: 'phrase', label: '词' },
  { value: 'place', label: '地名' },
  { value: 'image', label: '意象' },
  { value: 'theme', label: '主题' },
  { value: 'dynasty', label: '朝代' },
]

export function ConceptsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const keyword = searchParams.get('keyword') ?? ''
  const type = (searchParams.get('type') ?? '') as '' | ConceptType
  const [searchInput, setSearchInput] = useState(keyword)
  const [typeInput, setTypeInput] = useState<'' | ConceptType>(type)
  const [selectedConceptId, setSelectedConceptId] = useState<number | null>(null)
  const [aliasInput, setAliasInput] = useState('')
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null)

  const conceptsQuery = useQuery({
    queryKey: ['concepts', keyword, type],
    queryFn: () =>
      listConcepts({
        keyword: keyword || undefined,
        type: type || undefined,
        include_counts: true,
        limit: 40,
        offset: 0,
      }),
  })

  const selectedConcept =
    conceptsQuery.data?.items.find((item) => item.id === selectedConceptId) ??
    conceptsQuery.data?.items[0] ??
    null

  const graphPreviewQuery = useQuery({
    queryKey: ['concept-graph-preview', selectedConcept?.id],
    queryFn: () =>
      getConceptGraph(selectedConcept!.id, {
        limit_poems: 8,
        limit_lines: 12,
      }),
    enabled: selectedConcept !== null,
  })

  const aliasesQuery = useQuery({
    queryKey: ['concept-aliases', selectedConcept?.id],
    queryFn: () => listConceptAliases(selectedConcept!.id),
    enabled: selectedConcept !== null,
  })

  const createAliasMutation = useMutation({
    mutationFn: (alias: string) => createConceptAlias(selectedConcept!.id, alias),
    onSuccess: () => {
      setAliasInput('')
      queryClient.invalidateQueries({ queryKey: ['concept-aliases', selectedConcept?.id] })
    },
  })

  const deleteAliasMutation = useMutation({
    mutationFn: (aliasId: number) => deleteConceptAlias(selectedConcept!.id, aliasId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['concept-aliases', selectedConcept?.id] })
    },
  })

  const parseJobsQuery = useQuery({
    queryKey: ['parse-jobs', 'recent-failed'],
    queryFn: () => listParseJobs({ limit: 10, offset: 0 }),
  })

  const selectedJob = parseJobsQuery.data?.items.find((item) => item.id === selectedJobId) ?? parseJobsQuery.data?.items[0] ?? null

  const parseJobDetailQuery = useQuery({
    queryKey: ['parse-job-detail', selectedJob?.id],
    queryFn: () => getParseJob(selectedJob!.id),
    enabled: selectedJob !== null,
  })

  useEffect(() => {
    if (!conceptsQuery.data?.items.length) {
      setSelectedConceptId(null)
      return
    }

    if (
      selectedConceptId === null ||
      !conceptsQuery.data.items.some((item) => item.id === selectedConceptId)
    ) {
      setSelectedConceptId(conceptsQuery.data.items[0].id)
    }
  }, [conceptsQuery.data, selectedConceptId])

  useEffect(() => {
    if (!parseJobsQuery.data?.items.length) {
      setSelectedJobId(null)
      return
    }

    if (
      selectedJobId === null ||
      !parseJobsQuery.data.items.some((item) => item.id === selectedJobId)
    ) {
      setSelectedJobId(parseJobsQuery.data.items[0].id)
    }
  }, [parseJobsQuery.data, selectedJobId])

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const next = new URLSearchParams(searchParams)
    const normalizedKeyword = searchInput.trim()

    if (normalizedKeyword) next.set('keyword', normalizedKeyword)
    else next.delete('keyword')

    if (typeInput) next.set('type', typeInput)
    else next.delete('type')

    setSearchParams(next)
  }

  function handleReset() {
    setSearchInput('')
    setTypeInput('')
    setSearchParams(new URLSearchParams())
  }

  function handleAliasSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const alias = aliasInput.trim()
    if (!alias || !selectedConcept) return
    createAliasMutation.mutate(alias)
  }

  return (
    <div className="page-grid page-grid-split-wide">
      <PageSection
        title="主题图谱"
        subtitle="按字、词、地名、意象和主题搜索概念。"
      >
        <form className="toolbar-form" onSubmit={handleSearchSubmit}>
          <div className="toolbar-row">
            <input
              className="input"
              placeholder="输入概念关键词"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
            <select
              className="input"
              value={typeInput}
              onChange={(event) => setTypeInput(event.target.value as '' | ConceptType)}
            >
              {CONCEPT_TYPES.map((option) => (
                <option key={option.value || 'all'} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="toolbar-actions">
            <button className="button button-primary" type="submit">
              搜索
            </button>
            <button className="button" type="button" onClick={handleReset}>
              清空
            </button>
          </div>
        </form>

        {conceptsQuery.isLoading ? <p className="hint">加载中...</p> : null}
        {conceptsQuery.isError ? <p className="hint">概念列表加载失败，请检查后端服务。</p> : null}

        <div className="concept-list">
          {conceptsQuery.data?.items.map((concept) => (
            <button
              key={concept.id}
              type="button"
              className={selectedConceptId === concept.id ? 'concept-row concept-row-active' : 'concept-row'}
              onClick={() => setSelectedConceptId(concept.id)}
            >
              <span className="concept-row-main">
                <span className="concept-row-title">{concept.name}</span>
                <span className="concept-type-badge">{concept.type}</span>
              </span>
              <span className="concept-row-meta">
                <span>{concept.poem_count ?? 0} 首诗</span>
                <span>{concept.line_count ?? 0} 句</span>
              </span>
            </button>
          ))}
        </div>

        {conceptsQuery.data && conceptsQuery.data.items.length === 0 ? (
          <EmptyState title="暂无概念" description="先执行解析，或在数据库中补充 concepts 词典。" />
        ) : null}
      </PageSection>

      <PageSection
        title={selectedConcept ? selectedConcept.name : '概念详情'}
        subtitle={selectedConcept ? '查看局部图谱预览并进入图谱页。' : '从左侧选择一个概念。'}
        actions={
          selectedConcept ? (
            <button
              className="button button-primary"
              type="button"
              onClick={() => navigate(`/workspace/concepts/${selectedConcept.id}`)}
            >
              打开图谱
            </button>
          ) : null
        }
      >
        {!selectedConcept ? <EmptyState title="未选择概念" description="左侧选择后会在这里显示预览。" /> : null}

        {selectedConcept ? (
          <div className="concept-detail-stack">
            <div className="concept-stat-grid">
              <article className="concept-stat-card">
                <span className="concept-stat-label">类型</span>
                <strong>{selectedConcept.type}</strong>
              </article>
              <article className="concept-stat-card">
                <span className="concept-stat-label">关联诗词</span>
                <strong>{selectedConcept.poem_count ?? 0}</strong>
              </article>
              <article className="concept-stat-card">
                <span className="concept-stat-label">关联诗句</span>
                <strong>{selectedConcept.line_count ?? 0}</strong>
              </article>
            </div>

            <div className="concept-preview-panel">
              <div className="concept-preview-header">
                <h3>局部图谱预览</h3>
                {graphPreviewQuery.data?.truncated ? <span className="muted">已截断</span> : null}
              </div>
              {graphPreviewQuery.isLoading ? <p className="hint">正在读取局部图谱...</p> : null}
              {graphPreviewQuery.isError ? <p className="hint">图谱预览加载失败。</p> : null}
              {graphPreviewQuery.data ? (
                <div className="concept-preview-groups">
                  {['line', 'poem', 'author', 'dynasty'].map((group) => {
                    const nodes = graphPreviewQuery.data!.nodes.filter((node) => node.type === group)
                    if (!nodes.length) return null
                    return (
                      <section key={group} className="concept-preview-group">
                        <h4>{group}</h4>
                        <div className="concept-chip-wrap">
                          {nodes.map((node) => (
                            <span key={node.id} className={`concept-chip concept-chip-${group}`}>
                              {node.label}
                            </span>
                          ))}
                        </div>
                      </section>
                    )
                  })}
                </div>
              ) : null}
            </div>

            <div className="concept-preview-panel">
              <div className="concept-preview-header">
                <h3>别名管理</h3>
              </div>
              <form className="toolbar-form" onSubmit={handleAliasSubmit}>
                <div className="toolbar-row">
                  <input
                    className="input"
                    placeholder="新增别名"
                    value={aliasInput}
                    onChange={(event) => setAliasInput(event.target.value)}
                  />
                  <button className="button button-primary" type="submit" disabled={createAliasMutation.isPending}>
                    添加别名
                  </button>
                </div>
              </form>
              {aliasesQuery.isLoading ? <p className="hint">别名读取中...</p> : null}
              {aliasesQuery.isError ? <p className="hint">别名读取失败。</p> : null}
              <div className="concept-chip-wrap">
                {aliasesQuery.data?.aliases.map((alias) => (
                  <span key={alias.id} className="concept-manage-chip">
                    <span>{alias.alias}</span>
                    <button
                      type="button"
                      className="chip-remove-button"
                      disabled={deleteAliasMutation.isPending}
                      onClick={() => deleteAliasMutation.mutate(alias.id)}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              {aliasesQuery.data && aliasesQuery.data.aliases.length === 0 ? (
                <p className="hint">当前还没有别名。</p>
              ) : null}
            </div>

            <div className="concept-preview-panel">
              <div className="concept-preview-header">
                <h3>解析任务</h3>
              </div>
              {parseJobsQuery.isLoading ? <p className="hint">任务读取中...</p> : null}
              {parseJobsQuery.isError ? <p className="hint">任务读取失败。</p> : null}
              <div className="concept-job-grid">
                <div className="graph-node-list">
                  {parseJobsQuery.data?.items.map((job) => (
                    <button
                      key={job.id}
                      type="button"
                      className={selectedJobId === job.id ? 'graph-node-button graph-node-button-active' : 'graph-node-button'}
                      onClick={() => setSelectedJobId(job.id)}
                    >
                      <span>#{job.id} · {job.status}</span>
                    </button>
                  ))}
                </div>
                <div className="detail-card">
                  {selectedJob ? (
                    <>
                      <h3>任务详情</h3>
                      {parseJobDetailQuery.isLoading ? <p className="hint">日志读取中...</p> : null}
                      {parseJobDetailQuery.isError ? <p className="hint">日志读取失败。</p> : null}
                      <p className="muted">
                        poem_id={selectedJob.poem_id ?? 'null'} · {selectedJob.job_type} · {selectedJob.trigger_source}
                      </p>
                      <div className="graph-edge-list">
                        {parseJobDetailQuery.data?.logs.map((log) => (
                          <div key={log.id} className="graph-edge-row">
                            <span>{log.level}</span>
                            <span>{log.message}</span>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <p className="hint">暂无任务记录。</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </PageSection>
    </div>
  )
}
