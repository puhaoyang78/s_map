/**
 * 热力图相关 API
 */
import http from './index.js'

const HEATMAP_TIMEOUT_MS = 120_000

/** 获取热力图数据（支持可选区域和快照过滤） */
export const fetchHeatmapData = ({ minLat, maxLat, minLng, maxLng, minCount = 1, snapshot = null } = {}) =>
  http.get('/api/heatmap-data', { minLat, maxLat, minLng, maxLng, minCount, snapshot }, { timeout: HEATMAP_TIMEOUT_MS })

/** 强制刷新热力图缓存并获取数据 */
export const refreshHeatmap = ({ fast = false, snapshot = null } = {}) =>
  http.get('/api/refresh-heatmap', { fast, snapshot }, { timeout: HEATMAP_TIMEOUT_MS })

/** 获取热力图预热状态 */
export const fetchHeatmapStatus = () =>
  http.get('/api/heatmap-status')

/** 强制刷新统计数据（不使用缓存） */
export const refreshStats = ({ snapshot = null } = {}) =>
  http.get('/api/refresh-stats', { snapshot })

/** 获取当前缓存版本号 */
export const fetchCacheVersion = () =>
  http.get('/api/cache-version')

/** 清除后端缓存 */
export const clearCache = () =>
  http.post('/api/clear-cache')
