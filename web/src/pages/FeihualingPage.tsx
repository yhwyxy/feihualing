import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from 'react'

import { ApiError } from '../shared/api/http'
import {
  getFeihualingSession,
  listFeihualingSessions,
  streamPlayFeihualingTurn,
  streamStartFeihualing,
  surrenderFeihualing,
} from '../shared/api/feihualing'
import type {
  FeihualingDifficulty,
  FeihualingStreamEvent,
  SessionRead,
  SessionSummary,
  TurnRead,
} from '../shared/types/api'

const DIFFICULTY_OPTIONS: { value: FeihualingDifficulty; label: string; hint: string }[] = [
  { value: 'easy', label: '初级', hint: '仅顶流诗句（约 10% 库）' },
  { value: 'medium', label: '中级', hint: '常见及以上（约 30% 库）' },
  { value: 'hard', label: '高级', hint: '全库，偏门优先' },
  { value: 'expert', label: '炼狱', hint: '全库 + AI 可引用库外原句' },
]

const STATUS_LABEL: Record<SessionRead['status'], string> = {
  in_progress: '对局进行中',
  user_won: '你赢了',
  agent_won: 'AI 赢了',
  abandoned: '已中止',
}

function formatTime(iso: string | null) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}

function TurnBubble({ turn, animateIn }: { turn: TurnRead; animateIn?: boolean }) {
  const isUser = turn.speaker === 'user'
  const invalid = !turn.is_valid
  const hasLibSource = turn.title !== null
  const hasLlmSource = turn.llm_title !== null || turn.llm_author !== null
  return (
    <div className={`fh-row ${isUser ? 'fh-row-user' : 'fh-row-agent'} ${animateIn ? 'fh-row-enter' : ''}`}>
      <div className={`fh-bubble ${invalid ? 'fh-bubble-invalid' : isUser ? 'fh-bubble-user' : 'fh-bubble-agent'}`}>
        <div className="fh-line">{turn.line}</div>
        {hasLibSource ? (
          <div className="fh-source">
            《{turn.title}》{turn.author ? ` · ${turn.author}` : ''}
          </div>
        ) : hasLlmSource ? (
          <div className="fh-source fh-source-llm">
            《{turn.llm_title ?? '?'}》
            {turn.llm_author ? ` · ${turn.llm_author}` : ''}
            <span className="fh-source-tag">LLM 识别</span>
          </div>
        ) : turn.is_valid ? (
          <div className="fh-source">（LLM 判定为真，未知出处）</div>
        ) : null}
        {turn.reject_reason ? <div className="fh-reject">{turn.reject_reason}</div> : null}
        {turn.latency_ms ? (
          <div className="fh-latency">
            {turn.speaker === 'agent' ? 'Agent' : '校验'} {turn.latency_ms} ms
          </div>
        ) : null}
      </div>
    </div>
  )
}

function SessionStatusBanner({ session }: { session: SessionRead }) {
  if (session.status === 'in_progress') return null
  const isWin = session.status === 'user_won'
  return (
    <div className={`fh-banner ${isWin ? 'fh-banner-win' : 'fh-banner-lose'}`}>
      <div className="fh-banner-title">{STATUS_LABEL[session.status]}</div>
      {session.winner_reason ? <div className="fh-banner-reason">{session.winner_reason}</div> : null}
    </div>
  )
}

export function FeihualingPage() {
  const queryClient = useQueryClient()

  const [targetChar, setTargetChar] = useState('月')
  const [difficulty, setDifficulty] = useState<FeihualingDifficulty>('medium')
  const [session, setSession] = useState<SessionRead | null>(null)
  const [line, setLine] = useState('')
  const [error, setError] = useState('')
  const [thinking, setThinking] = useState(false)
  const [agentStep, setAgentStep] = useState('')
  const [lastTurnId, setLastTurnId] = useState<string>('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  const { data: sessionList } = useQuery({
    queryKey: ['feihualing-sessions'],
    queryFn: () => listFeihualingSessions({ limit: 10 }),
    refetchInterval: 10000,
  })

  const appendTurn = (turn: TurnRead) => {
    setSession((prev) => {
      if (!prev) return prev
      return { ...prev, turns: [...prev.turns, turn] }
    })
    setLastTurnId(`${turn.turn_index}-${turn.speaker}`)
  }

  const handleStreamEvent = (event: FeihualingStreamEvent) => {
    switch (event.type) {
      case 'session_created':
        setSession({
          session_id: event.session_id,
          target_char: event.target_char,
          difficulty: event.difficulty,
          status: 'in_progress',
          winner_reason: null,
          started_at: new Date().toISOString(),
          ended_at: null,
          turns: [],
        })
        setAgentStep('Agent 思考中…')
        break
      case 'user_validating':
        setAgentStep('正在校验你的诗句…')
        break
      case 'user_result':
        appendTurn(event.turn)
        if (event.turn.is_valid) {
          setAgentStep('Agent 思考中…')
        } else {
          setAgentStep('')
        }
        break
      case 'agent_thinking':
        setAgentStep('Agent 思考中…')
        break
      case 'agent_tool_call':
        setAgentStep(`Agent 调用工具 ${event.name}…`)
        break
      case 'agent_tool_result':
        if (event.count === 0) {
          setAgentStep('候选为空')
        } else {
          const preview = event.sample_lines.slice(0, 2).join(' / ')
          setAgentStep(`找到 ${event.count} 个候选：${preview}${event.count > 2 ? '…' : ''}`)
        }
        break
      case 'agent_result':
        appendTurn(event.turn)
        setAgentStep(event.source === 'fallback' ? '已使用兜底检索完成本轮' : '')
        break
      case 'agent_surrender':
        setAgentStep('')
        setSession((prev) =>
          prev ? { ...prev, status: 'user_won', winner_reason: event.reason } : prev,
        )
        break
      case 'agent_error':
        setAgentStep(`Agent 异常（${event.message}），切换兜底…`)
        break
      case 'agent_fallback_started':
        setAgentStep(`兜底检索中：${event.reason}`)
        break
      case 'error':
        setAgentStep('')
        setError(event.message)
        break
      case 'done':
        setAgentStep('')
        setSession((prev) =>
          prev
            ? {
                ...prev,
                status: event.status,
                winner_reason: event.winner_reason,
                ended_at:
                  event.status === 'in_progress' ? null : new Date().toISOString(),
              }
            : prev,
        )
        if (event.status !== 'in_progress') {
          queryClient.invalidateQueries({ queryKey: ['feihualing-sessions'] })
        }
        break
    }
  }

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [session?.turns?.length, thinking, lastTurnId])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const runStart = async () => {
    const char = targetChar.trim()
    if (char.length !== 1) {
      setError('请输入一个汉字作为目标字')
      return
    }
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setError('')
    setThinking(true)
    setLine('')
    try {
      await streamStartFeihualing({ target_char: char, difficulty }, handleStreamEvent, controller.signal)
    } catch (err) {
      if (controller.signal.aborted) return
      if (err instanceof ApiError) setError(err.message)
      else if (err instanceof Error) setError(err.message)
      else setError('开局失败，请稍后再试。')
    } finally {
      setThinking(false)
      setAgentStep('')
    }
  }

  const runTurn = async () => {
    if (!session) return
    const trimmed = line.trim()
    if (!trimmed) {
      setError('请输入一句诗')
      return
    }
    if (session.status !== 'in_progress') return

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setError('')
    setThinking(true)
    setLine('')
    try {
      await streamPlayFeihualingTurn(
        session.session_id,
        trimmed,
        handleStreamEvent,
        controller.signal,
      )
    } catch (err) {
      if (controller.signal.aborted) return
      if (err instanceof ApiError) setError(err.message)
      else if (err instanceof Error) setError(err.message)
      else setError('提交失败，请稍后再试。')
    } finally {
      setThinking(false)
      setAgentStep('')
    }
  }

  const surrenderMutation = useMutation({
    mutationFn: surrenderFeihualing,
    onSuccess: () => {
      setSession((prev) =>
        prev
          ? {
              ...prev,
              status: 'agent_won',
              winner_reason: '用户认输',
              ended_at: new Date().toISOString(),
            }
          : prev,
      )
      queryClient.invalidateQueries({ queryKey: ['feihualing-sessions'] })
    },
  })

  const handleStart = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    void runStart()
  }

  const handleSubmitLine = () => {
    void runTurn()
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSubmitLine()
    }
  }

  const handleSurrender = () => {
    if (!session) return
    if (!confirm('确定认输吗？')) return
    surrenderMutation.mutate(session.session_id)
  }

  const handleRestart = () => {
    abortRef.current?.abort()
    setSession(null)
    setLine('')
    setError('')
    setAgentStep('')
    setThinking(false)
  }

  const handleBackToMenu = async () => {
    if (!session) return
    if (session.status === 'in_progress') {
      if (!confirm('当前对局将算作认输，确认返回开局界面？')) return
      try {
        await surrenderFeihualing(session.session_id)
      } catch {
        // 即使认输失败也继续返回
      }
      queryClient.invalidateQueries({ queryKey: ['feihualing-sessions'] })
    }
    handleRestart()
  }

  const handleResumeFromList = async (sid: number) => {
    abortRef.current?.abort()
    try {
      setError('')
      setThinking(true)
      const data = await getFeihualingSession(sid)
      setSession(data)
      setLine('')
    } catch {
      setError('加载对局失败')
    } finally {
      setThinking(false)
    }
  }

  const inProgress = session?.status === 'in_progress'

  return (
    <div className="fh-page">
      <header className="fh-header">
        <h1>飞花令</h1>
        <p className="fh-subtitle">
          你和 AI 轮流说含指定字的古诗词原句。AI 走真实 Function Calling 工具调用 + 严格库/LLM 双验证，全链路 SSE 流式。
        </p>
      </header>

      {session === null ? (
        <section className="fh-start">
          <form className="fh-start-form" onSubmit={handleStart}>
            <label className="fh-field">
              <span>目标字</span>
              <input
                className="fh-char-input"
                value={targetChar}
                onChange={(event) => setTargetChar(event.target.value.slice(-1))}
                maxLength={1}
                placeholder="月"
              />
            </label>
            <div className="fh-field">
              <span>难度</span>
              <div className="fh-difficulty">
                {DIFFICULTY_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    className={
                      difficulty === opt.value
                        ? 'fh-diff-btn fh-diff-btn-active'
                        : 'fh-diff-btn'
                    }
                    onClick={() => setDifficulty(opt.value)}
                    title={opt.hint}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
            <button type="submit" className="fh-start-btn" disabled={thinking}>
              {thinking ? '开局中…' : '开始对局'}
            </button>
          </form>
          {error ? <div className="fh-error">{error}</div> : null}
        </section>
      ) : (
        <section className="fh-game">
          <div className="fh-meta">
            <div className="fh-target">
              <span className="fh-target-label">目标字</span>
              <span className="fh-target-char">{session.target_char}</span>
            </div>
            <div className="fh-meta-right">
              <span className="fh-diff-tag">{
                DIFFICULTY_OPTIONS.find((o) => o.value === session.difficulty)?.label ?? session.difficulty
              }</span>
              <span className="fh-turn-count">已用 {session.turns.filter((t) => t.is_valid).length} 句</span>
              {inProgress ? (
                <>
                  <button className="fh-surrender" type="button" onClick={handleSurrender}>
                    认输
                  </button>
                  <button className="fh-back" type="button" onClick={handleBackToMenu}>
                    返回
                  </button>
                </>
              ) : (
                <button className="fh-restart" type="button" onClick={handleRestart}>
                  开新局
                </button>
              )}
            </div>
          </div>

          <div className="fh-dialog" ref={scrollRef}>
            {session.turns.map((turn) => (
              <TurnBubble
                key={`${turn.turn_index}-${turn.speaker}`}
                turn={turn}
                animateIn={lastTurnId === `${turn.turn_index}-${turn.speaker}`}
              />
            ))}
            {thinking && inProgress ? (
              <div className="fh-row fh-row-agent">
                <div className="fh-bubble fh-bubble-agent fh-bubble-thinking">
                  {agentStep ? (
                    <span className="fh-step-text">{agentStep}</span>
                  ) : (
                    <>
                      <span className="fh-dot" />
                      <span className="fh-dot" />
                      <span className="fh-dot" />
                    </>
                  )}
                </div>
              </div>
            ) : null}
          </div>

          <SessionStatusBanner session={session} />

          {inProgress ? (
            <div className="fh-input-row">
              <input
                className="fh-line-input"
                value={line}
                onChange={(event) => setLine(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={`出一句含「${session.target_char}」字的诗`}
                disabled={thinking}
                autoFocus
              />
              <button
                type="button"
                className="fh-submit"
                onClick={handleSubmitLine}
                disabled={thinking || !line.trim()}
              >
                {thinking ? '…' : '出句'}
              </button>
            </div>
          ) : null}

          {error ? <div className="fh-error">{error}</div> : null}
        </section>
      )}

      {sessionList && sessionList.items.length > 0 ? (
        <section className="fh-history">
          <h2>最近对局</h2>
          <div className="fh-history-list">
            {sessionList.items.map((s: SessionSummary) => (
              <button
                key={s.session_id}
                type="button"
                className="fh-history-item"
                onClick={() => handleResumeFromList(s.session_id)}
                disabled={s.status === 'in_progress' && session?.session_id === s.session_id}
              >
                <span className="fh-history-char">{s.target_char}</span>
                <span className="fh-history-meta">
                  {DIFFICULTY_OPTIONS.find((o) => o.value === s.difficulty)?.label}
                  {' · '}
                  <span
                    className={
                      s.status === 'user_won'
                        ? 'fh-history-win'
                        : s.status === 'agent_won'
                          ? 'fh-history-lose'
                          : 'fh-history-muted'
                    }
                  >
                    {STATUS_LABEL[s.status]}
                  </span>
                </span>
                <span className="fh-history-turns">{s.turn_count} 回合</span>
                <span className="fh-history-time">{formatTime(s.started_at)}</span>
              </button>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  )
}
