import { message, Modal } from 'ant-design-vue'

export const notify = {
  success: (content) => message.open({ type: 'success', content, duration: 2.8 }),
  error: (content) => message.open({ type: 'error', content, duration: 4 }),
  info: (content) => message.open({ type: 'info', content, duration: 3 }),
  warning: (content) => message.open({ type: 'warning', content, duration: 3.5 }),
}

export function confirmAction({ title, content, okText = '确定', cancelText = '取消', danger = false }) {
  return new Promise((resolve) => {
    Modal.confirm({
      title,
      content,
      okText,
      cancelText,
      okButtonProps: danger ? { danger: true } : undefined,
      onOk: () => resolve(true),
      onCancel: () => resolve(false),
    })
  })
}
