import http from './index.js'

export const createDetectionJob = (payload = {}) =>
  http.post('/api/detection/jobs', payload)

export const listDetectionRegions = () =>
  http.get('/api/detection/regions')

export const listDetectionJobs = (params = {}) =>
  http.get('/api/detection/jobs', params)

export const getDetectionJob = (jobId) =>
  http.get(`/api/detection/jobs/${jobId}`)

export const cancelDetectionJob = (jobId) =>
  http.post(`/api/detection/jobs/${jobId}/cancel`, {})

export const clearDetectionHistory = async () => {
  try {
    return await http.delete('/api/detection/jobs/history')
  } catch (err) {
    if (err?.status === 405 || err?.status === 404) {
      return http.post('/api/detection/jobs/history', {})
    }
    throw err
  }
}
