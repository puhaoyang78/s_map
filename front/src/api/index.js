import { messageByCode } from '../utils/errorCodeMap.js'

const configuredApiBase = (import.meta.env.VITE_API_BASE_URL || '').trim()
const localApiPattern = /^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/i
const shouldUseDevProxy = import.meta.env.DEV && (!configuredApiBase || localApiPattern.test(configuredApiBase))
const API_BASE = shouldUseDevProxy ? '' : configuredApiBase
const { fetch, AbortController, URLSearchParams, setTimeout, clearTimeout, document } = globalThis

function resolveApiUrl(path) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return API_BASE ? `${API_BASE}${normalizedPath}` : normalizedPath
}

function authHeaders() {
  return {}
}

function getCookie(name) {
  const raw = document?.cookie || ''
  if (!raw) return ''

  const parts = raw.split(';')
  for (const part of parts) {
    const index = part.indexOf('=')
    if (index <= 0) continue
    const key = part.slice(0, index).trim()
    if (key !== name) continue
    return decodeURIComponent(part.slice(index + 1).trim())
  }

  return ''
}

function csrfHeaders(method) {
  const normalizedMethod = (method || 'GET').toUpperCase()
  if (['GET', 'HEAD', 'OPTIONS'].includes(normalizedMethod)) {
    return {}
  }

  const token = getCookie('csrf_token')
  return token ? { 'X-CSRF-Token': token } : {}
}

function enrichWithMeta(payload, response) {
  const requestId = response.headers.get('x-request-id')
  if (payload && typeof payload === 'object' && requestId) {
    payload.requestId = requestId
  }
  return payload
}

function createApiError(message, status, code, requestId, rawMessage = null) {
  const userMessage = messageByCode(code, message || `HTTP ${status || 0}`)
  return new ApiError(userMessage, status, code, requestId, rawMessage || message)
}

function mergeAbortSignals(...signals) {
  const validSignals = signals.filter(Boolean)
  if (validSignals.length === 0) {
    return {
      signal: null,
      cleanup: () => {},
    }
  }

  if (validSignals.length === 1) {
    return {
      signal: validSignals[0],
      cleanup: () => {},
    }
  }

  const controller = new AbortController()
  const abort = () => controller.abort()

  for (const signal of validSignals) {
    if (signal.aborted) {
      controller.abort()
      return {
        signal: controller.signal,
        cleanup: () => {},
      }
    }
    signal.addEventListener('abort', abort, { once: true })
  }

  return {
    signal: controller.signal,
    cleanup: () => {
      for (const signal of validSignals) {
        signal.removeEventListener('abort', abort)
      }
    },
  }
}

async function request(path, options = {}) {
  const { timeout = 30_000, signal: externalSignal, ...fetchOptions } = options
  const url = resolveApiUrl(path)

  const timeoutController = new AbortController()
  const { signal, cleanup } = mergeAbortSignals(timeoutController.signal, externalSignal)
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    timeoutController.abort()
  }, timeout)

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      credentials: 'include',
      headers: {
        ...(fetchOptions.headers || {}),
        ...authHeaders(),
        ...csrfHeaders(fetchOptions.method),
      },
      signal,
    })

    let payload = null
    const contentType = response.headers.get('content-type') || ''
    if (contentType.includes('application/json')) {
      try {
        payload = await response.json()
      } catch {
        payload = null
      }
    }

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}`
      let errorCode = null

      if (payload && typeof payload === 'object') {
        errorMessage = payload.message || errorMessage
        errorCode = payload.code || null
      }

      if (response.status === 401 && !fetchOptions.suppressAuthExpiredEvent) {
        globalThis?.localStorage?.removeItem('auth_token')
        globalThis?.dispatchEvent?.(new CustomEvent('auth-expired', {
          detail: {
            path,
            status: response.status,
            code: errorCode,
            message: messageByCode(errorCode, errorMessage),
          },
        }))
      }

      throw createApiError(
        errorMessage,
        response.status,
        errorCode,
        response.headers.get('x-request-id'),
      )
    }

    if (payload && typeof payload === 'object' && payload.success === false) {
      throw createApiError(
        payload.message || '请求失败',
        400,
        payload.code || null,
        response.headers.get('x-request-id'),
      )
    }

    if (payload !== null) {
      return enrichWithMeta(payload, response)
    }

    return null
  } catch (error) {
    if (error?.name === 'AbortError') {
      if (timedOut) {
        throw new ApiError('请求超时，请稍后重试', 408)
      }
      throw new ApiError('请求已取消', -1, 'REQUEST_ABORTED')
    }

    if (error instanceof TypeError) {
      throw new ApiError('网络异常，请检查后端服务与连接', 0)
    }

    throw error
  } finally {
    clearTimeout(timer)
    cleanup()
  }
}

export class ApiError extends Error {
  constructor(message, status, code = null, requestId = null, rawMessage = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
    this.rawMessage = rawMessage || message
  }
}

export const http = {
  get: (path, params = {}, options = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '')
    ).toString()
    return request(query ? `${path}?${query}` : path, { method: 'GET', ...options })
  },

  post: (path, body = {}, options = {}) => request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    ...options,
  }),

  patch: (path, body = {}, options = {}) => request(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    ...options,
  }),

  delete: (path, options = {}) => request(path, { method: 'DELETE', ...options }),

  download: async (path, body = {}, options = {}) => {
    const { timeout = 30_000, signal: externalSignal } = options
    const url = resolveApiUrl(path)
    const timeoutController = new AbortController()
    const { signal, cleanup } = mergeAbortSignals(timeoutController.signal, externalSignal)
    let timedOut = false
    const timer = setTimeout(() => {
      timedOut = true
      timeoutController.abort()
    }, timeout)

    try {
      const response = await fetch(url, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
          ...csrfHeaders('POST'),
        },
        body: JSON.stringify(body),
        signal,
      })

      if (!response.ok) {
        throw new ApiError(`下载失败: HTTP ${response.status}`, response.status)
      }

      return response.blob()
    } catch (error) {
      if (error?.name === 'AbortError') {
        if (timedOut) {
          throw new ApiError('下载超时，请稍后重试', 408)
        }
        throw new ApiError('下载已取消', -1, 'REQUEST_ABORTED')
      }

      if (error instanceof TypeError) {
        throw new ApiError('网络异常，下载失败', 0)
      }

      throw error
    } finally {
      clearTimeout(timer)
      cleanup()
    }
  },
}

export default http
