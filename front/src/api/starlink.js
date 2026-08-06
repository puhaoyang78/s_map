import http from './index.js'

export const fetchStarlinkVisualization = (params = {}) =>
  http.get('/api/starlink/visualization', params)

export const fetchStarlinkVisualizationDetail = (satelliteId, params = {}) =>
  http.get(`/api/starlink/visualization/${encodeURIComponent(satelliteId)}`, params)
