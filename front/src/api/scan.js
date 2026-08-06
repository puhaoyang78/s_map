/**
 * 漏洞扫描报告相关 API
 */
import http from './index.js'

/** 根据 IP 段查找对应的扫描报告文件 */
export const findScanReport = (ipSegment) =>
  http.post('/api/scan-report/find', { ipSegment })
