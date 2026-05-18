import type { AppError } from '../types'

const rawBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').trim()
const BASE_URL = rawBaseUrl.replace(/\/+$/, '')
const useMock = import.meta.env.VITE_USE_MOCK === 'true'
const enableHttpDebug = import.meta.env.DEV || import.meta.env.VITE_DEBUG_HTTP === 'true'

export { useMock }
export function resolveApiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${BASE_URL}${normalizedPath}`
}

function createRequestId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

function debugHttp(direction: 'request' | 'response' | 'error', payload: Record<string, unknown>) {
  if (!enableHttpDebug) return

  const prefix = direction === 'request' ? '→' : direction === 'response' ? '←' : '×'
  console.debug(`[http] ${prefix}`, payload)
}

export async function http<T>(method: string, path: string, options?: { params?: Record<string, any>; body?: any }): Promise<T> {
  const requestId = createRequestId()
  const url = new URL(resolveApiUrl(path))
  if (options?.params) {
    Object.entries(options.params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v))
    })
  }

  const headers: Record<string, string> = {}
  if (options?.body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  const body = options?.body ? JSON.stringify(options.body) : undefined
  const startedAt = performance.now()

  debugHttp('request', {
    requestId,
    method,
    url: url.toString(),
    params: options?.params || null,
    body: options?.body ?? null,
    mock: useMock,
  })

  let res: Response
  try {
    res = await fetch(url.toString(), {
      method,
      headers,
      body,
    })
  } catch (error) {
    const durationMs = Math.round(performance.now() - startedAt)
    const nativeMessage = error instanceof Error ? error.message : String(error)
    const isLikelyCors = nativeMessage === 'Failed to fetch'
    const appError: AppError = {
      code: 'NETWORK_ERROR',
      message: isLikelyCors
        ? `请求失败：浏览器未拿到响应，可能是 CORS 或网络错误。${method} ${url.toString()}`
        : `请求失败：${nativeMessage}`,
      retryable: true,
    }

    debugHttp('error', {
      requestId,
      method,
      url: url.toString(),
      durationMs,
      error: nativeMessage,
      hint: isLikelyCors ? 'Check backend CORS_ALLOW_ORIGINS / browser network panel' : null,
    })
    throw appError
  }

  const durationMs = Math.round(performance.now() - startedAt)
  debugHttp('response', {
    requestId,
    method,
    url: url.toString(),
    status: res.status,
    ok: res.ok,
    durationMs,
  })

  if (!res.ok) {
    const errorText = await res.text().catch(() => '')
    let errorData: any = {}
    if (errorText) {
      try {
        errorData = JSON.parse(errorText)
      } catch {
        errorData = { raw: errorText }
      }
    }
    const appError: AppError = {
      code: errorData?.error?.code || `HTTP_${res.status}`,
      message: errorData?.error?.message || errorData?.detail || errorData?.raw || `请求失败 (${res.status})`,
      retryable: res.status >= 500,
    }
    debugHttp('error', {
      requestId,
      method,
      url: url.toString(),
      status: res.status,
      error: appError,
      response: errorData,
    })
    throw appError
  }

  const responseText = await res.text()
  let data: T
  try {
    data = responseText ? JSON.parse(responseText) as T : (null as T)
  } catch (error) {
    debugHttp('error', {
      requestId,
      method,
      url: url.toString(),
      status: res.status,
      parseError: error instanceof Error ? error.message : String(error),
      responseText,
    })
    throw {
      code: 'INVALID_JSON',
      message: `响应解析失败：${method} ${url.toString()}`,
      retryable: false,
    } satisfies AppError
  }

  debugHttp('response', {
    requestId,
    method,
    url: url.toString(),
    data,
  })
  return data
}
