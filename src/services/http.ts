import { runtimeConfig } from '@/config/runtime'

export interface ApiErrorDetail {
  code?: string
  message?: string
  robot?: unknown
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string | null
  readonly detail: ApiErrorDetail | string | null

  constructor(status: number, detail: ApiErrorDetail | string | null, fallback: string) {
    const message = typeof detail === 'object' && detail?.message
      ? detail.message
      : typeof detail === 'string' && detail
        ? detail
        : fallback
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = typeof detail === 'object' && detail?.code ? detail.code : null
    this.detail = detail
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${runtimeConfig.apiBase}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {})
    }
  })

  if (!response.ok) {
    let payload: { detail?: ApiErrorDetail | string } | null = null
    try {
      payload = await response.json() as { detail?: ApiErrorDetail | string }
    } catch {
      // A non-JSON proxy error still gets a useful HTTP fallback below.
    }
    throw new ApiError(response.status, payload?.detail ?? null, `HTTP ${response.status}: ${response.statusText}`)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path)
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body)
  })
}

export function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'PUT',
    body: body === undefined ? undefined : JSON.stringify(body)
  })
}

export function apiDelete<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'DELETE' })
}
