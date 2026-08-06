/**
 * 快照管理相关 API
 */
import http from './index.js'

/** 获取所有可用快照列表 */
export const fetchSnapshots = () =>
  http.get('/api/snapshots')

export const deleteSnapshot = (snapshotKey) =>
  http.delete(`/api/snapshots/${snapshotKey}`)
