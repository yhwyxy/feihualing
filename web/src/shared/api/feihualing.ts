import { API_BASE_URL, apiFetch } from './http'
import type {
  FeihualingDifficulty,
  FeihualingStreamEvent,
  MessageResponse,
  SessionListResponse,
  SessionRead,
} from '../types/api'


async function consumeSSE(
  response: Response,
  onEvent: (event: FeihualingStreamEvent) => void,
): Promise<void> {
  if (!response.ok) {
    let message = `Request failed with status ${response.status}`
    try {
      const data = (await response.json()) as { detail?: string }
      if (data.detail) message = data.detail
    } catch {
      // ignore
    }
    throw new Error(message)
  }
  if (!response.body) {
    throw new Error('Response body missing')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''

    for (const chunk of chunks) {
      const trimmed = chunk.trim()
      if (!trimmed.startsWith('data:')) continue
      const jsonText = trimmed.slice(5).trim()
      if (!jsonText) continue
      try {
        const event = JSON.parse(jsonText) as FeihualingStreamEvent
        onEvent(event)
      } catch {
        // skip malformed chunk
      }
    }
  }
}


export async function streamStartFeihualing(
  payload: { target_char: string; difficulty: FeihualingDifficulty },
  onEvent: (event: FeihualingStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/agent/feihualing/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
  await consumeSSE(response, onEvent)
}


export async function streamPlayFeihualingTurn(
  sessionId: number,
  line: string,
  onEvent: (event: FeihualingStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/agent/feihualing/${sessionId}/turn`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ line }),
    signal,
  })
  await consumeSSE(response, onEvent)
}


export function surrenderFeihualing(sessionId: number) {
  return apiFetch<MessageResponse>(`/agent/feihualing/${sessionId}/surrender`, {
    method: 'POST',
  })
}

export function getFeihualingSession(sessionId: number) {
  return apiFetch<SessionRead>(`/agent/feihualing/${sessionId}`)
}

export function listFeihualingSessions(params: { limit?: number; offset?: number } = {}) {
  const search = new URLSearchParams()
  if (params.limit !== undefined) search.set('limit', String(params.limit))
  if (params.offset !== undefined) search.set('offset', String(params.offset))
  const suffix = search.toString() ? `?${search.toString()}` : ''
  return apiFetch<SessionListResponse>(`/agent/feihualing${suffix}`)
}
