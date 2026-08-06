import http from './index.js'

const DEVICE_CACHE_TTL_MS = 15_000
const deviceQueryCache = new Map()

const buildDeviceQueryKey = ({
  page = 1,
  pageSize = 10,
  country = '',
  city = '',
  keyword = '',
  snapshot = null,
} = {}) => JSON.stringify({ page, pageSize, country, city, keyword, snapshot })

export const clearDevicesCache = () => {
  deviceQueryCache.clear()
}

if (typeof globalThis?.addEventListener === 'function') {
  globalThis.addEventListener('cache-cleared', clearDevicesCache)
  globalThis.addEventListener('snapshots:changed', clearDevicesCache)
}

export const fetchDevices = async (
  {
    page = 1,
    pageSize = 10,
    country = '',
    city = '',
    keyword = '',
    snapshot = null,
  } = {},
  options = {},
) => {
  const params = { page, pageSize, country, city, keyword, snapshot }
  const key = buildDeviceQueryKey(params)
  const now = Date.now()
  const cached = deviceQueryCache.get(key)

  if (cached?.data && cached.expiresAt > now) {
    return cached.data
  }

  if (cached?.promise) {
    return cached.promise
  }

  const request = http.get('/api/devices', params, options)
    .then((data) => {
      deviceQueryCache.set(key, {
        data,
        expiresAt: Date.now() + DEVICE_CACHE_TTL_MS,
      })
      return data
    })
    .catch((error) => {
      deviceQueryCache.delete(key)
      throw error
    })

  deviceQueryCache.set(key, {
    promise: request,
    expiresAt: now + DEVICE_CACHE_TTL_MS,
  })

  return request
}

export const exportDevices = ({ keyword = '', snapshot = null } = {}, options = {}) =>
  http.download('/api/devices/export', { keyword, snapshot }, options)
