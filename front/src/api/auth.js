import http from './index.js'

export const login = ({ username, password }, options = {}) =>
  http.post('/api/auth/login', { username, password }, options)

export const logout = (options = {}) =>
  http.post('/api/auth/logout', {}, options)

export const fetchMe = (options = {}) =>
  http.get('/api/auth/me', {}, options)

export const changePassword = ({ oldPassword, newPassword }) =>
  http.post('/api/auth/change-password', { oldPassword, newPassword })

export const listUsers = ({ q = '', role = '', page = 1, pageSize = 20 } = {}) =>
  http.get('/api/users', { q, role, page, pageSize })

export const createUser = ({ username, password, role = 'user', status = 'active' }) =>
  http.post('/api/users', { username, password, role, status })

export const updateUser = (id, payload) =>
  http.patch(`/api/users/${id}`, payload)

export const deleteUser = (id) =>
  http.delete(`/api/users/${id}`)

export const issueUserPasswordResetToken = async (id) => {
  try {
    return await http.post(`/api/users/${id}/password-reset-token`, {})
  } catch (e) {
    // Backward compatibility: older backend only exposes /reset-password.
    if (e?.status === 404) {
      return http.post(`/api/users/${id}/reset-password`, {})
    }
    throw e
  }
}

export const revealUserPasswordResetToken = (deliveryId) =>
  http.post(`/api/users/password-reset-token-deliveries/${deliveryId}/reveal`, {})

export const confirmPasswordReset = ({ resetToken, newPassword }) =>
  http.post('/api/auth/password-reset/confirm', { resetToken, newPassword })

// Backward-compatible alias: old callers still invoke resetUserPassword().
export const resetUserPassword = (id) =>
  issueUserPasswordResetToken(id)
