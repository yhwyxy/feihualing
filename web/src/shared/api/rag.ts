import { API_BASE_URL, apiFetch } from './http'
import type {
  RagAskEvent,
  RagSearchRequest,
  RagSearchResponse,
} from '../types/api'

export function ragSearch(payload: RagSearchRequest) {
  return apiFetch<RagSearchResponse>('/rag/search', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function streamRagAsk(
  payload: { query: string; top_k?: number },
  onEvent: (event: RagAskEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/rag/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    let message = `Ask failed with status ${response.status}`
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
        const event = JSON.parse(jsonText) as RagAskEvent
        onEvent(event)
      } catch {
        // skip malformed chunk
      }
    }
  }
}
