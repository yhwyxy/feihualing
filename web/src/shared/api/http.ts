export const API_BASE_URL = 'http://127.0.0.1:8000'

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message)
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)

  if (init?.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  })

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`

    try {
      const data = (await response.json()) as { detail?: string }
      if (data.detail) {
        message = data.detail
      }
    } catch {
      // ignore json parse error
    }

    throw new ApiError(message, response.status)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}
