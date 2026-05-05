import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import {
  createManualLineConcept,
  deleteManualLineConcept,
  getConceptGraph,
  getPoemConcepts,
  listConcepts,
  reparsePoem,
} from '../shared/api/concepts'
import { getPoem } from '../shared/api/poems'
import { EmptyState } from '../shared/ui/EmptyState'
import { PageSection } from '../shared/ui/PageSection'

const LINE_SPLIT_RE = /[，。；！？、,.!?;\n\r]+/g

function splitPoemLines(content: string) {
  return content
    .split(LINE_SPLIT_RE)
    .map((line) => line.trim())
    .filter((line) => line.length >= 3 && line.length <= 40)
}

function groupLabel(type: string) {
  switch (type) {
    case 'line':
      return '诗句'
    case 'poem':
      return '诗词'
    case 'author':
      return '作者'
    case 'dynasty':
      return '朝代'
    default:
      return type
  }
}

export function ConceptGraphPage() {
  const queryClient = useQueryClient()
  const params = useParams()
  const conceptId = Number(params.conceptId)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [manualConceptId, setManualConceptId] = useState<number | null>(null)
  const [manualLineIndex, setManualLineIndex] = useState(0)
  const [manualMatchedText, setManualMatchedText] = useState('')
  const [sourceFilter, setSourceFilter] = useState<'parser' | 'manual' | 'import' | 'llm' | ''>('')
  const [minPopularity, setMinPopularity] = useState(1)
  const [minMatchedCount, setMinMatchedCount] = useState(1)
  const [nodeSearch, setNodeSearch] = useState('')
  const [collapsePoemLines, setCollapsePoemLines] = useState(true)

  const graphQuery = useQuery({
    queryKey: ['concept-graph', conceptId, sourceFilter, minPopularity, minMatchedCount],
    queryFn: () =>
      getConceptGraph(conceptId, {
        limit_poems: 30,
        limit_lines: 80,
        source: sourceFilter || undefined,
        min_popularity: minPopularity > 1 ? minPopularity : undefined,
        min_matched_count: minMatchedCount > 1 ? minMatchedCount : undefined,
      }),
    enabled: Number.isFinite(conceptId) && conceptId > 0,
  })

  const selectedNode =
    graphQuery.data?.nodes.find((node) => node.id === selectedNodeId) ??
    graphQuery.data?.center ??
    null

  const selectedPoemId =
    selectedNode?.type === 'poem' && typeof selectedNode.meta.poem_id === 'number'
      ? selectedNode.meta.poem_id
      : null

  const poemConceptsQuery = useQuery({
    queryKey: ['poem-concepts', selectedPoemId],
    queryFn: () => getPoemConcepts(selectedPoemId!),
    enabled: selectedPoemId !== null,
  })

  const poemDetailQuery = useQuery({
    queryKey: ['poem-detail', selectedPoemId],
    queryFn: () => getPoem(selectedPoemId!),
    enabled: selectedPoemId !== null,
  })

  const conceptOptionsQuery = useQuery({
    queryKey: ['concept-options-manual'],
    queryFn: () => listConcepts({ include_counts: false, limit: 100, offset: 0 }),
  })

  const reparseMutation = useMutation({
    mutationFn: reparsePoem,
    onSuccess: (result) => {
      setMessage(`已创建重解析任务 #${result.job_id}`)
      queryClient.invalidateQueries({ queryKey: ['poem-concepts', selectedPoemId] })
    },
    onError: () => {
      setMessage('重解析任务创建失败')
    },
  })

  const createManualMutation = useMutation({
    mutationFn: ({
      poemId,
      conceptId: nextConceptId,
      lineIndex,
      matchedText,
    }: {
      poemId: number
      conceptId: number
      lineIndex: number
      matchedText: string
    }) =>
      createManualLineConcept(poemId, {
        concept_id: nextConceptId,
        line_index: lineIndex,
        matched_text: matchedText || null,
        start_offset: 0,
      }),
    onSuccess: () => {
      setMessage('已新增手动概念关系')
      queryClient.invalidateQueries({ queryKey: ['poem-concepts', selectedPoemId] })
      queryClient.invalidateQueries({ queryKey: ['concept-graph', conceptId] })
      setManualMatchedText('')
    },
    onError: () => {
      setMessage('手动概念关系新增失败')
    },
  })

  const deleteManualMutation = useMutation({
    mutationFn: ({
      poemId,
      conceptId: nextConceptId,
      lineIndex,
      matchedText,
      startOffset,
    }: {
      poemId: number
      conceptId: number
      lineIndex: number
      matchedText: string
      startOffset: number
    }) =>
      deleteManualLineConcept(poemId, {
        concept_id: nextConceptId,
        line_index: lineIndex,
        matched_text: matchedText,
        start_offset: startOffset,
      }),
    onSuccess: () => {
      setMessage('已删除手动概念关系')
      queryClient.invalidateQueries({ queryKey: ['poem-concepts', selectedPoemId] })
      queryClient.invalidateQueries({ queryKey: ['concept-graph', conceptId] })
    },
    onError: () => {
      setMessage('手动概念关系删除失败')
    },
  })

  const groupedNodes = useMemo(() => {
    const nodes = graphQuery.data?.nodes ?? []
    const normalizedSearch = nodeSearch.trim()
    return ['line', 'poem', 'author', 'dynasty'].map((type) => ({
      type,
      label: groupLabel(type),
      items: nodes
        .filter((node) => node.type === type)
        .filter((node) => (normalizedSearch ? node.label.includes(normalizedSearch) : true))
        .filter((node, index, all) => {
          if (type !== 'line' || !collapsePoemLines) return true
          const poemId = node.meta.poem_id
          return all.findIndex((candidate) => candidate.meta.poem_id === poemId) === index
        }),
    }))
  }, [collapsePoemLines, graphQuery.data, nodeSearch])

  const selectedNodeEdges = useMemo(() => {
    if (!selectedNode || !graphQuery.data) return []
    return graphQuery.data.edges.filter(
      (edge) => edge.source === selectedNode.id || edge.target === selectedNode.id,
    )
  }, [graphQuery.data, selectedNode])

  const connectedNodeIds = useMemo(() => {
    if (!selectedNode) return new Set<string>()
    const ids = new Set<string>()
    for (const edge of selectedNodeEdges) {
      ids.add(edge.source)
      ids.add(edge.target)
    }
    return ids
  }, [selectedNode, selectedNodeEdges])

  const poemLines = useMemo(
    () => (poemDetailQuery.data ? splitPoemLines(poemDetailQuery.data.content) : []),
    [poemDetailQuery.data],
  )

  useEffect(() => {
    if (conceptOptionsQuery.data?.items.length && manualConceptId === null) {
      setManualConceptId(conceptOptionsQuery.data.items[0].id)
    }
  }, [conceptOptionsQuery.data, manualConceptId])

  useEffect(() => {
    if (graphQuery.data?.center) {
      setSelectedNodeId((current) => current ?? graphQuery.data!.center.id)
    }
  }, [graphQuery.data])

  if (!Number.isFinite(conceptId) || conceptId <= 0) {
    return <EmptyState title="参数无效" description="概念 ID 不合法。" />
  }

  function handleCreateManualConcept(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (selectedPoemId === null || manualConceptId === null) return
    createManualMutation.mutate({
      poemId: selectedPoemId,
      conceptId: manualConceptId,
      lineIndex: manualLineIndex,
      matchedText: manualMatchedText.trim(),
    })
  }

  return (
    <div className="page-grid page-grid-split-wide">
      <PageSection
        title={graphQuery.data?.center.label ?? '概念图谱'}
        subtitle="局部图谱默认深度为 1，聚焦概念与诗句、诗词、作者之间的关联。"
        actions={
          <Link className="button" to="/workspace/concepts">
            返回列表
          </Link>
        }
      >
        {message ? <p className="hint">{message}</p> : null}
        {graphQuery.isLoading ? <p className="hint">图谱加载中...</p> : null}
        {graphQuery.isError ? <p className="hint">图谱加载失败。</p> : null}

        {graphQuery.data ? (
          <div className="graph-layout">
            <form className="toolbar-form concept-manual-form">
              <div className="toolbar-row">
                <input
                  className="input"
                  placeholder="搜索节点"
                  value={nodeSearch}
                  onChange={(event) => setNodeSearch(event.target.value)}
                />
                <select
                  className="input"
                  value={sourceFilter}
                  onChange={(event) => setSourceFilter(event.target.value as typeof sourceFilter)}
                >
                  <option value="">全部来源</option>
                  <option value="parser">parser</option>
                  <option value="manual">manual</option>
                  <option value="import">import</option>
                  <option value="llm">llm</option>
                </select>
                <select
                  className="input"
                  value={minPopularity}
                  onChange={(event) => setMinPopularity(Number(event.target.value))}
                >
                  <option value={1}>热度全部</option>
                  <option value={2}>热度 2+</option>
                  <option value={3}>热度 3+</option>
                  <option value={4}>热度 4+</option>
                  <option value={5}>热度 5</option>
                </select>
              </div>
              <div className="toolbar-row">
                <select
                  className="input"
                  value={minMatchedCount}
                  onChange={(event) => setMinMatchedCount(Number(event.target.value))}
                >
                  <option value={1}>命中次数全部</option>
                  <option value={2}>命中 2+</option>
                  <option value={3}>命中 3+</option>
                  <option value={4}>命中 4+</option>
                </select>
                <label className="graph-toggle">
                  <input
                    type="checkbox"
                    checked={collapsePoemLines}
                    onChange={(event) => setCollapsePoemLines(event.target.checked)}
                  />
                  <span>折叠同诗多句</span>
                </label>
              </div>
            </form>
            <div className="graph-center-card">
              <span className="concept-stat-label">中心概念</span>
              <strong>{graphQuery.data.center.label}</strong>
              <span className="concept-type-badge">{String(graphQuery.data.center.meta.concept_type ?? 'concept')}</span>
            </div>

            <div className="graph-group-grid">
              {groupedNodes.map((group) => (
                <section key={group.type} className="graph-group-card">
                  <header className="graph-group-header">
                    <h3>{group.label}</h3>
                    <span className="muted">{group.items.length}</span>
                  </header>
                  <div className="graph-node-list">
                    {group.items.length === 0 ? <p className="hint">无关联节点</p> : null}
                    {group.items.map((node) => (
                      <button
                        key={node.id}
                        type="button"
                        className={
                          selectedNodeId === node.id
                            ? 'graph-node-button graph-node-button-active'
                            : connectedNodeIds.has(node.id)
                              ? 'graph-node-button graph-node-button-linked'
                              : 'graph-node-button'
                        }
                        onClick={() => setSelectedNodeId(node.id)}
                      >
                        <span>{node.label}</span>
                      </button>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </div>
        ) : null}
      </PageSection>

      <PageSection
        title={selectedNode ? selectedNode.label : '节点详情'}
        subtitle={selectedNode ? '点击左侧节点切换查看。' : '等待图谱加载。'}
      >
        {!selectedNode ? <EmptyState title="暂无节点" description="图谱加载后可查看节点详情。" /> : null}

        {selectedNode ? (
          <div className="concept-detail-stack">
            <div className="concept-stat-grid">
              <article className="concept-stat-card">
                <span className="concept-stat-label">节点类型</span>
                <strong>{selectedNode.type}</strong>
              </article>
              <article className="concept-stat-card">
                <span className="concept-stat-label">关系数量</span>
                <strong>{selectedNodeEdges.length}</strong>
              </article>
              {selectedPoemId ? (
                <article className="concept-stat-card">
                  <span className="concept-stat-label">诗词操作</span>
                  <button
                    className="button"
                    type="button"
                    disabled={reparseMutation.isPending}
                    onClick={() => reparseMutation.mutate(selectedPoemId)}
                  >
                    重新解析
                  </button>
                </article>
              ) : null}
            </div>

            <div className="detail-card">
              <h3>节点元数据</h3>
              <pre className="concept-json-block">
                {JSON.stringify(selectedNode.meta, null, 2)}
              </pre>
            </div>

            <div className="detail-card">
              <h3>关联边</h3>
              <div className="graph-edge-list">
                {selectedNodeEdges.length === 0 ? <p className="hint">没有可显示的关系。</p> : null}
                {selectedNodeEdges.map((edge) => (
                  <div key={edge.id} className="graph-edge-row">
                    <span>{edge.source}</span>
                    <span className="muted">{edge.type}</span>
                    <span>{edge.target}</span>
                  </div>
                ))}
              </div>
            </div>

            {selectedPoemId ? (
              <div className="detail-card">
                <h3>这首诗的概念命中</h3>
                {poemConceptsQuery.isLoading ? <p className="hint">读取中...</p> : null}
                {poemConceptsQuery.isError ? <p className="hint">诗词概念加载失败。</p> : null}
                <form className="toolbar-form concept-manual-form" onSubmit={handleCreateManualConcept}>
                  <div className="toolbar-row">
                    <select
                      className="input"
                      value={manualConceptId ?? ''}
                      onChange={(event) => setManualConceptId(Number(event.target.value))}
                    >
                      {conceptOptionsQuery.data?.items.map((concept) => (
                        <option key={concept.id} value={concept.id}>
                          {concept.name} · {concept.type}
                        </option>
                      ))}
                    </select>
                    <select
                      className="input"
                      value={manualLineIndex}
                      onChange={(event) => setManualLineIndex(Number(event.target.value))}
                    >
                      {poemLines.map((line, index) => (
                        <option key={`${index}-${line}`} value={index}>
                          第 {index + 1} 句 · {line}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="toolbar-row">
                    <input
                      className="input"
                      placeholder="命中文本，留空则使用概念名"
                      value={manualMatchedText}
                      onChange={(event) => setManualMatchedText(event.target.value)}
                    />
                    <button className="button button-primary" type="submit" disabled={createManualMutation.isPending}>
                      新增手动关系
                    </button>
                  </div>
                </form>
                <div className="concept-hit-list">
                  {poemConceptsQuery.data?.concepts.map((concept) => (
                    <article key={concept.id} className="concept-hit-card">
                      <div className="concept-hit-header">
                        <strong>{concept.name}</strong>
                        <span className="concept-type-badge">{concept.type}</span>
                      </div>
                      <p className="muted">
                        {concept.matched_count} 次命中 · {concept.source} · {concept.confidence}
                      </p>
                      <div className="concept-chip-wrap">
                        {concept.lines.map((line) => (
                          <span key={`${concept.id}-${line.line_index}-${line.start_offset}`} className="concept-manage-chip">
                            <span>{line.line_text}</span>
                            {line.source === 'manual' ? (
                              <button
                                type="button"
                                className="chip-remove-button"
                                disabled={deleteManualMutation.isPending}
                                onClick={() =>
                                  deleteManualMutation.mutate({
                                    poemId: selectedPoemId,
                                    conceptId: concept.id,
                                    lineIndex: line.line_index,
                                    matchedText: line.matched_text,
                                    startOffset: line.start_offset,
                                  })
                                }
                              >
                                ×
                              </button>
                            ) : null}
                          </span>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </PageSection>
    </div>
  )
}
