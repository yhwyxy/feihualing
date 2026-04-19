import { apiFetch } from './http'
import type { BatchImportPayload, BatchImportResponse } from '../types/api'

export function importBatch(payload: BatchImportPayload) {
  return apiFetch<BatchImportResponse>('/imports/batch', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
