import { apiFetch } from './http'
import type {
  BatchImportPayload,
  BatchImportResponse,
  UnifiedImportPayload,
  UnifiedImportResponse,
} from '../types/api'

export function importBatch(payload: BatchImportPayload) {
  return apiFetch<BatchImportResponse>('/imports/batch', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function importUnified(payload: UnifiedImportPayload) {
  return apiFetch<UnifiedImportResponse>('/imports/unified', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function importUnifiedFile(formData: FormData) {
  return apiFetch<UnifiedImportResponse>('/imports/unified/file', {
    method: 'POST',
    body: formData,
  })
}
