import { message } from 'ant-design-vue'
import { ApiError } from '../api/index.js'
import { messageByCode } from './errorCodeMap.js'

let isShowing = false

function showError(text) {
  if (isShowing) return
  isShowing = true
  message.error(text)
  setTimeout(() => {
    isShowing = false
  }, 1800)
}

export function installGlobalErrorHandler(app) {
  app.config.errorHandler = (err) => {
    const text = err instanceof ApiError
      ? messageByCode(err.code, err.message)
      : (err?.message || '页面发生异常，请稍后重试')
    console.error('Vue error:', err)
    showError(text)
  }

  window.addEventListener('unhandledrejection', (event) => {
    const reason = event?.reason
    const text = reason instanceof ApiError
      ? messageByCode(reason.code, reason.message)
      : (reason?.message || '请求处理失败，请重试')
    console.error('Unhandled rejection:', reason)
    showError(text)
  })
}
