<script setup>
import { computed, onMounted, onUnmounted, ref, defineAsyncComponent } from 'vue'
import PageHeader from './components/ui/PageHeader.vue'
import PageToolbar from './components/ui/PageToolbar.vue'
import PanelCard from './components/ui/PanelCard.vue'
import StateBlock from './components/ui/StateBlock.vue'
const MapComponent = defineAsyncComponent(() => import('./components/MapComponent.vue'))
import {
  login as apiLogin,
  logout as apiLogout,
  fetchMe,
  changePassword as apiChangePassword,
  listUsers,
  createUser as apiCreateUser,
  deleteUser as apiDeleteUser,
  issueUserPasswordResetToken,
  revealUserPasswordResetToken,
  confirmPasswordReset,
} from './api/auth.js'
import { notify, confirmAction } from './utils/notify.js'

const loading = ref(true)
const loginLoading = ref(false)
const user = ref(null)
const loginError = ref('')
const sessionNotice = ref('')

const username = ref('')
const password = ref('')
const showResetByToken = ref(false)
const resetTokenInput = ref('')
const resetNewPassword = ref('')
const resetConfirmPassword = ref('')
const resetByTokenLoading = ref(false)
const resetTokenModalVisible = ref(false)
const resetTokenModalLoading = ref(false)
const resetTokenModalValue = ref('')
const resetTokenModalExpiresAt = ref('')
const resetTokenModalUsername = ref('')

const showAccountPanel = ref(false)
const accountTab = ref('profile')
const users = ref([])
const usersLoading = ref(false)
const usersTotal = ref(0)
const userSearch = ref('')
const userRoleFilter = ref('all')
const userPage = ref(1)
const creating = ref(false)
const createUserFeedback = ref('')

const newUsername = ref('')
const newPassword = ref('')
const newRole = ref('user')

const oldPassword = ref('')
const selfNewPassword = ref('')
const selfConfirmPassword = ref('')
const changingPassword = ref(false)
const changePasswordFeedback = ref('')
const changePasswordFeedbackType = ref('error')
const resetByTokenFeedback = ref('')
const resetByTokenFeedbackType = ref('error')
const resetTokenModalError = ref('')
const resetTokenModalSuccess = ref('')
const resetTokenModalTargetUserId = ref(null)

const isAdmin = computed(() => user.value?.role === 'admin')
const initials = computed(() => (user.value?.username || 'U').slice(0, 1).toUpperCase())
const { addEventListener, removeEventListener } = globalThis
const USER_PAGE_SIZE = 8

function isStrongPassword(password) {
  if (!password || password.length < 12) return false
  const hasUpper = /[A-Z]/.test(password)
  const hasLower = /[a-z]/.test(password)
  const hasDigit = /\d/.test(password)
  const hasSpecial = /[^A-Za-z0-9]/.test(password)
  return hasUpper && hasLower && hasDigit && hasSpecial
}

const isSelf = (row) => Number(row?.id) === Number(user.value?.id)

function parseBackendUtcDate(value) {
  if (!value || typeof value !== 'string') return null

  const normalizedValue = value.trim()
  if (!normalizedValue) return null

  if (/([zZ]|[+-]\d{2}:\d{2})$/.test(normalizedValue)) {
    const parsed = new Date(normalizedValue)
    return Number.isNaN(parsed.getTime()) ? null : parsed
  }

  const match = normalizedValue.match(
    /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.(\d+))?$/
  )
  if (!match) {
    const fallback = new Date(normalizedValue)
    return Number.isNaN(fallback.getTime()) ? null : fallback
  }

  const base = match[1]
  const fraction = match[3] ? match[3].slice(0, 3).padEnd(3, '0') : '000'
  const parsed = new Date(`${base}.${fraction}Z`)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function formatResetTokenExpiresAt(value) {
  const parsed = parseBackendUtcDate(value)
  return parsed ? parsed.toLocaleString() : value
}

const userTotalPages = computed(() => Math.max(1, Math.ceil(usersTotal.value / USER_PAGE_SIZE)))

const paginatedUsers = computed(() => users.value)

const userPageSummary = computed(() => {
  if (!usersTotal.value) return '当前筛选条件下没有匹配的用户'
  const start = (userPage.value - 1) * USER_PAGE_SIZE + 1
  const end = start + users.value.length - 1
  return `显示 ${start}-${end} / ${usersTotal.value} 个用户`
})

function resetUserListView() {
  userPage.value = 1
}

function clampUserPage() {
  if (userPage.value > userTotalPages.value) {
    userPage.value = userTotalPages.value
  }
  if (userPage.value < 1) {
    userPage.value = 1
  }
}

async function applyUserFilters() {
  resetUserListView()
  await loadUsers()
}

async function resetUserFilters() {
  userSearch.value = ''
  userRoleFilter.value = 'all'
  resetUserListView()
  await loadUsers()
}

function closeResetTokenModal() {
  resetTokenModalVisible.value = false
  resetTokenModalLoading.value = false
  resetTokenModalValue.value = ''
  resetTokenModalExpiresAt.value = ''
  resetTokenModalUsername.value = ''
  resetTokenModalError.value = ''
  resetTokenModalSuccess.value = ''
  resetTokenModalTargetUserId.value = null
}

async function copyResetToken() {
  if (!resetTokenModalValue.value) {
    notify.warning('当前没有可复制的令牌')
    return
  }

  const fallbackCopy = (text) => {
    const textarea = globalThis.document?.createElement('textarea')
    if (!textarea || !globalThis.document?.body) return false

    textarea.value = text
    textarea.setAttribute('readonly', '')
    textarea.style.position = 'fixed'
    textarea.style.left = '-9999px'
    textarea.style.top = '0'
    textarea.style.opacity = '0'

    globalThis.document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()

    try {
      return globalThis.document.execCommand('copy')
    } catch {
      return false
    } finally {
      globalThis.document.body.removeChild(textarea)
    }
  }

  try {
    const canUseClipboardApi =
      globalThis.isSecureContext &&
      !!globalThis.navigator?.clipboard?.writeText

    if (canUseClipboardApi) {
      await globalThis.navigator.clipboard.writeText(resetTokenModalValue.value)
      notify.success('重置令牌已复制到剪贴板')
      return
    }
  } catch {
    // Continue with legacy fallback when Clipboard API is blocked.
  }

  if (fallbackCopy(resetTokenModalValue.value)) {
    notify.success('重置令牌已复制到剪贴板')
    return
  }

  notify.error('复制失败，请手动复制令牌')
}

function saveToken() {
  globalThis?.localStorage?.removeItem('auth_token')
}

function clearToken() {
  globalThis?.localStorage?.removeItem('auth_token')
}

async function restoreSession() {
  try {
    const res = await fetchMe({ suppressAuthExpiredEvent: true })
    user.value = res?.data?.user || null
    if (user.value?.forcePasswordChange) {
      notify.warning('当前账号需要先修改密码后才能继续使用')
      showAccountPanel.value = true
      accountTab.value = 'profile'
    }
  } catch {
    clearToken()
    user.value = null
  } finally {
    loading.value = false
  }
}

function clearLoginFeedback() {
  loginError.value = ''
  sessionNotice.value = ''
}

function clearCreateUserFeedback() {
  createUserFeedback.value = ''
}

function clearChangePasswordFeedback() {
  changePasswordFeedback.value = ''
}

function clearResetByTokenFeedback() {
  resetByTokenFeedback.value = ''
}

async function handleLogin() {
  if (!username.value || !password.value) {
    loginError.value = '请输入用户名和密码'
    notify.warning('请输入用户名和密码')
    return
  }

  clearLoginFeedback()
  loginLoading.value = true
  try {
    const res = await apiLogin(
      { username: username.value, password: password.value },
      { suppressAuthExpiredEvent: true }
    )
    const me = res?.data?.user
    if (!me) {
      loginError.value = '登录响应异常，请稍后重试'
      notify.error('登录响应异常')
      return
    }
    saveToken()
    user.value = me
    notify.success('登录成功')
    if (user.value?.forcePasswordChange) {
      notify.warning('当前账号需要先修改密码后才能继续使用')
      showAccountPanel.value = true
      accountTab.value = 'profile'
    }
  } catch (e) {
    loginError.value = e?.message || '登录失败'
    notify.error(loginError.value)
  } finally {
    loginLoading.value = false
  }
}

async function logout() {
  try {
    await apiLogout()
  } catch (e) {
    notify.warning(e?.message || '退出请求失败，已在本地退出登录')
  }
  clearToken()
  user.value = null
  showAccountPanel.value = false
  accountTab.value = 'profile'
}

async function toggleAccountPanel() {
  showAccountPanel.value = !showAccountPanel.value
  if (!showAccountPanel.value) return

  if (isAdmin.value) {
    accountTab.value = 'users'
    await loadUsers()
  } else {
    accountTab.value = 'profile'
  }
}

async function loadUsers() {
  usersLoading.value = true
  try {
    const res = await listUsers({
      q: userSearch.value.trim(),
      role: userRoleFilter.value === 'all' ? '' : userRoleFilter.value,
      page: userPage.value,
      pageSize: USER_PAGE_SIZE,
    })
    users.value = res?.data?.users || []
    usersTotal.value = Number(res?.data?.pagination?.total || 0)
    userPage.value = Number(res?.data?.pagination?.page || userPage.value)
    clampUserPage()
    if (usersTotal.value > 0 && users.value.length === 0 && userPage.value > 1) {
      userPage.value = userTotalPages.value
      return await loadUsers()
    }
  } catch (e) {
    notify.error(e?.message || '加载用户列表失败')
  } finally {
    usersLoading.value = false
  }
}

async function createUser() {
  if (!newUsername.value || !newPassword.value) {
    createUserFeedback.value = '请输入用户名和初始密码'
    notify.warning('请输入用户名和初始密码')
    return
  }
  if (!isStrongPassword(newPassword.value)) {
    createUserFeedback.value = '初始密码需至少 12 位，且包含大小写字母、数字和特殊字符'
    notify.warning('初始密码需至少 12 位，且包含大小写字母、数字和特殊字符')
    return
  }
  clearCreateUserFeedback()
  creating.value = true
  try {
    await apiCreateUser({ username: newUsername.value, password: newPassword.value, role: newRole.value })
    notify.success('用户创建成功')
    createUserFeedback.value = '用户创建成功'
    newUsername.value = ''
    newPassword.value = ''
    newRole.value = 'user'
    resetUserListView()
    await loadUsers()
  } catch (e) {
    notify.error(e?.message || '创建用户失败')
  } finally {
    creating.value = false
  }
}

async function changeOwnPassword() {
  if (!oldPassword.value || !selfNewPassword.value || !selfConfirmPassword.value) {
    changePasswordFeedbackType.value = 'error'
    changePasswordFeedback.value = '请完整填写密码修改表单'
    notify.warning('请完整填写密码修改表单')
    return
  }
  if (!isStrongPassword(selfNewPassword.value)) {
    changePasswordFeedbackType.value = 'error'
    changePasswordFeedback.value = '新密码需至少 12 位，且包含大小写字母、数字和特殊字符'
    notify.warning('新密码需至少 12 位，且包含大小写字母、数字和特殊字符')
    return
  }
  if (selfNewPassword.value !== selfConfirmPassword.value) {
    changePasswordFeedbackType.value = 'error'
    changePasswordFeedback.value = '新密码与确认密码不一致'
    notify.warning('新密码与确认密码不一致')
    return
  }

  clearChangePasswordFeedback()
  changingPassword.value = true
  try {
    await apiChangePassword({
      oldPassword: oldPassword.value,
      newPassword: selfNewPassword.value,
    })
    oldPassword.value = ''
    selfNewPassword.value = ''
    selfConfirmPassword.value = ''
    changePasswordFeedbackType.value = 'success'
    changePasswordFeedback.value = '密码修改成功，请重新登录'
    notify.success('密码修改成功，请重新登录')
    logout()
  } catch (e) {
    changePasswordFeedbackType.value = 'error'
    changePasswordFeedback.value = e?.message || '密码修改失败'
    notify.error(e?.message || '密码修改失败')
  } finally {
    changingPassword.value = false
  }
}

async function resetPassword(row) {
  resetTokenModalVisible.value = true
  resetTokenModalLoading.value = true
  resetTokenModalValue.value = ''
  resetTokenModalExpiresAt.value = ''
  resetTokenModalUsername.value = row?.username || ''
  resetTokenModalTargetUserId.value = row?.id ?? null
  resetTokenModalError.value = ''
  resetTokenModalSuccess.value = ''

  try {
    const res = await issueUserPasswordResetToken(row.id)
    const resetToken = res?.data?.resetToken || ''
    const expiresAt = res?.data?.expiresAt || ''
    if (resetToken) {
      resetTokenModalValue.value = resetToken
      resetTokenModalExpiresAt.value = expiresAt
      resetTokenModalLoading.value = false
      resetTokenModalSuccess.value = '重置令牌生成成功，请通过安全渠道转交用户。'
      notify.success('重置令牌签发成功')
      return
    }

    const deliveryId = res?.data?.deliveryId || ''
    if (!deliveryId) {
      resetTokenModalLoading.value = false
      const msg = res?.message || '重置令牌签发成功（按安全策略未返回明文令牌）'
      resetTokenModalSuccess.value = msg
      notify.success(msg)
      return
    }

    const revealRes = await revealUserPasswordResetToken(deliveryId)
    resetTokenModalValue.value = revealRes?.data?.resetToken || ''
    resetTokenModalExpiresAt.value = revealRes?.data?.expiresAt || expiresAt
    resetTokenModalLoading.value = false
    resetTokenModalSuccess.value = '重置令牌已生成，请通过安全渠道转交用户。'
    notify.success('重置令牌已生成，请安全转交用户')

  } catch (e) {
    resetTokenModalLoading.value = false
    resetTokenModalError.value = e?.message || '重置令牌生成失败'
    notify.error(e?.message || '重置令牌生成失败')
  }
}

async function retryResetPasswordToken() {
  if (!resetTokenModalTargetUserId.value) {
    resetTokenModalError.value = '缺少目标用户，无法重新签发令牌'
    return
  }
  await resetPassword({
    id: resetTokenModalTargetUserId.value,
    username: resetTokenModalUsername.value,
  })
}

async function handleResetByToken() {
  if (!resetTokenInput.value || !resetNewPassword.value || !resetConfirmPassword.value) {
    resetByTokenFeedbackType.value = 'error'
    resetByTokenFeedback.value = '请完整填写重置表单'
    notify.warning('请完整填写重置表单')
    return
  }
  if (!isStrongPassword(resetNewPassword.value)) {
    resetByTokenFeedbackType.value = 'error'
    resetByTokenFeedback.value = '新密码需至少 12 位，且包含大小写字母、数字和特殊字符'
    notify.warning('新密码需至少 12 位，且包含大小写字母、数字和特殊字符')
    return
  }
  if (resetNewPassword.value !== resetConfirmPassword.value) {
    resetByTokenFeedbackType.value = 'error'
    resetByTokenFeedback.value = '两次输入的新密码不一致'
    notify.warning('两次输入的新密码不一致')
    return
  }

  clearResetByTokenFeedback()
  resetByTokenLoading.value = true
  try {
    await confirmPasswordReset({
      resetToken: resetTokenInput.value.trim(),
      newPassword: resetNewPassword.value,
    })
    resetByTokenFeedbackType.value = 'success'
    resetByTokenFeedback.value = '密码重置成功，请使用新密码登录'
    notify.success('密码重置成功，请使用新密码登录')
    showResetByToken.value = false
    resetTokenInput.value = ''
    resetNewPassword.value = ''
    resetConfirmPassword.value = ''
  } catch (e) {
    resetByTokenFeedbackType.value = 'error'
    resetByTokenFeedback.value = e?.message || '令牌重置失败'
    notify.error(e?.message || '令牌重置失败')
  } finally {
    resetByTokenLoading.value = false
  }
}

async function removeUser(row) {
  const ok = await confirmAction({
    title: '删除用户',
    content: `确认删除用户 ${row.username} 吗？该操作不可恢复。`,
    okText: '删除',
    cancelText: '取消',
    danger: true,
  })
  if (!ok) return

  try {
    await apiDeleteUser(row.id)
    notify.success('用户已删除')
    await loadUsers()
  } catch (e) {
    notify.error(e?.message || '删除用户失败')
  }
}

const onAuthExpired = () => {
  if (user.value) {
    sessionNotice.value = '登录状态已失效，请重新登录'
    notify.warning('登录状态已失效，请重新登录')
  }
  clearToken()
  user.value = null
  showAccountPanel.value = false
}

onMounted(() => {
  restoreSession()
  addEventListener('auth-expired', onAuthExpired)
})

onUnmounted(() => {
  removeEventListener('auth-expired', onAuthExpired)
})
</script>

<template>
  <div v-if="loading" class="screen flex-center">
    <div class="glass-panel p-lg text-center">
      <div class="spinner"></div>
      <p class="mt-sm text-secondary">正在校验登录状态...</p>
    </div>
  </div>

  <div v-else-if="!user" class="screen flex-center bg-pattern">
    <Transition name="fade-up" appear>
      <div class="glass-panel ds-glass-card login-card">
        <div class="text-center mb-lg">
          <p class="brand-text">GLOBAL DEVICE MAP</p>
          <h2 class="welcome-text">欢迎登录</h2>
          <p class="sub-text">登录以访问全球设备态势感知系统</p>
        </div>

        <StateBlock
          v-if="sessionNotice"
          class="mb-md"
          type="empty"
          title="登录状态已失效"
          :description="sessionNotice"
        />

        <StateBlock
          v-if="loginError"
          class="mb-md"
          type="error"
          title="登录失败"
          :description="loginError"
          role="alert"
        />

        <div class="form-group ds-field">
          <label class="u-sr-only" for="login-username">用户名</label>
          <input
            id="login-username"
            v-model="username"
            class="input"
            name="username"
            placeholder="用户名"
            autocomplete="username"
            @input="clearLoginFeedback"
            @keyup.enter="handleLogin"
          />
        </div>

        <div class="form-group ds-field">
          <label class="u-sr-only" for="login-password">密码</label>
          <input
            id="login-password"
            v-model="password"
            class="input"
            name="password"
            type="password"
            placeholder="密码"
            autocomplete="current-password"
            @input="clearLoginFeedback"
            @keyup.enter="handleLogin"
          />
        </div>

        <button type="button" class="btn btn-primary ds-btn-primary w-full mt-md" :disabled="loginLoading" @click="handleLogin">
          <span v-if="loginLoading" class="spinner-sm"></span>
          {{ loginLoading ? '登录中...' : '进入系统' }}
        </button>

        <button
          type="button"
          class="btn btn-text ds-btn-ghost w-full mt-sm text-sm"
          :aria-expanded="showResetByToken"
          aria-controls="reset-by-token-panel"
          @click="showResetByToken = !showResetByToken"
        >
          {{ showResetByToken ? '收起重置面板' : '使用重置令牌设置新密码' }}
        </button>

        <div v-if="showResetByToken" id="reset-by-token-panel" class="reset-panel mt-md pt-md border-t">
          <StateBlock
            v-if="resetByTokenFeedback"
            class="mb-sm"
            :type="resetByTokenFeedbackType === 'success' ? 'info' : 'error'"
            :title="resetByTokenFeedbackType === 'success' ? '密码重置成功' : '密码重置失败'"
            :description="resetByTokenFeedback"
          />
          <label class="u-sr-only" for="reset-token-input">重置令牌</label>
          <input
            id="reset-token-input"
            v-model="resetTokenInput"
            class="input mb-sm"
            name="reset_token"
            placeholder="重置令牌"
            autocomplete="one-time-code"
            @input="clearResetByTokenFeedback"
          />
          <label class="u-sr-only" for="reset-new-password">新密码</label>
          <input
            id="reset-new-password"
            v-model="resetNewPassword"
            class="input mb-sm"
            name="new_password"
            type="password"
            placeholder="新密码"
            autocomplete="new-password"
            @input="clearResetByTokenFeedback"
          />
          <label class="u-sr-only" for="reset-confirm-password">确认新密码</label>
          <input
            id="reset-confirm-password"
            v-model="resetConfirmPassword"
            class="input mb-sm"
            name="confirm_new_password"
            type="password"
            placeholder="确认新密码"
            autocomplete="new-password"
            @input="clearResetByTokenFeedback"
          />
          <button type="button" class="btn btn-secondary ds-btn-secondary w-full" :disabled="resetByTokenLoading" @click="handleResetByToken">
            {{ resetByTokenLoading ? '提交中...' : '确认重置密码' }}
          </button>
        </div>

        <p class="footer-tip text-center mt-lg">忘记密码请联系管理员获取重置令牌重置密码</p>
        <p class="footer-tip text-center mt-sm">请使用管理员分配的账号登录</p>
      </div>
    </Transition>
  </div>

  <div v-else class="app-shell">
    <div class="map-layer">
      <MapComponent />
    </div>

    <button
      type="button"
      class="account-fab shadow-lg"
      :class="{ open: showAccountPanel }"
      :title="showAccountPanel ? '收起账户中心' : '打开账户中心'"
      :aria-label="showAccountPanel ? `收起 ${user.username} 的账户中心` : `打开 ${user.username} 的账户中心`"
      @click="toggleAccountPanel"
    >
      <span class="avatar">{{ initials }}</span>
      <span class="username">{{ user.username }}</span>
    </button>

    <Transition name="slide-right">
      <div v-if="showAccountPanel" class="sidebar-mask" @click="showAccountPanel = false">
        <aside class="sidebar glass-panel ds-sidebar-shell" @click.stop>
          <PageHeader
            eyebrow="账户中心"
            :title="user.username"
            description="管理当前账户、密码和用户权限，保持账号设置与系统管理入口在同一工作台内。"
            class="sidebar-header"
          >
            <template #meta>
              <span class="ds-badge-info">{{ user.role }}</span>
            </template>
            <template #extra>
              <button type="button" class="btn-icon ds-icon-btn close-btn" title="关闭账户中心" aria-label="关闭账户中心" @click="showAccountPanel = false">×</button>
            </template>
          </PageHeader>

          <div v-if="isAdmin" class="tabs-nav">
            <button type="button" class="tab-btn" :class="{ active: accountTab === 'users' }" :aria-pressed="accountTab === 'users'" @click="accountTab = 'users'">
              用户管理
            </button>
            <button type="button" class="tab-btn" :class="{ active: accountTab === 'profile' }" :aria-pressed="accountTab === 'profile'" @click="accountTab = 'profile'">
              当前用户
            </button>
          </div>

          <div class="sidebar-content">
            <div v-if="accountTab === 'users'" class="tab-content u-stack">
              <PageHeader
                eyebrow="用户管理"
                title="账户与权限"
                description="统一管理账户创建、角色筛选与密码重置，让管理区和工作台保持同一套产品语言。"
                class="account-page-header"
              >
                <template #meta>
                  <span class="ds-badge">{{ usersTotal }} 个用户</span>
                </template>
              </PageHeader>

              <PanelCard class="card mb-md account-panel-card">
                <template #header>
                  <h4 class="card-title">添加用户</h4>
                </template>
                <div class="create-user-form">
                  <StateBlock
                    v-if="createUserFeedback"
                    class="create-user-feedback"
                    type="info"
                    title="用户创建成功"
                    :description="createUserFeedback"
                  />
                  <label class="u-sr-only" for="create-user-username">新用户名</label>
                  <input
                    id="create-user-username"
                    v-model="newUsername"
                    class="input"
                    name="new_username"
                    placeholder="用户名"
                    autocomplete="username"
                    @input="clearCreateUserFeedback"
                  />
                  <label class="u-sr-only" for="create-user-password">初始密码</label>
                  <input
                    id="create-user-password"
                    v-model="newPassword"
                    class="input"
                    name="new_user_password"
                    type="password"
                    placeholder="初始密码"
                    autocomplete="new-password"
                    @input="clearCreateUserFeedback"
                  />
                  <label class="u-sr-only" for="create-user-role">用户角色</label>
                  <select id="create-user-role" v-model="newRole" class="input" name="new_user_role">
                    <option value="user">普通用户</option>
                    <option value="admin">管理员</option>
                  </select>
                  <button type="button" class="btn btn-primary ds-btn-primary" :disabled="creating" @click="createUser">
                    {{ creating ? '创建中...' : '添加用户' }}
                  </button>
                </div>
              </PanelCard>

              <div class="card ds-table-shell p-0 overflow-hidden">
                <PageToolbar class="user-table-toolbar">
                  <div class="user-toolbar-fields">
                    <label class="u-sr-only" for="user-search-input">搜索用户</label>
                    <input
                      id="user-search-input"
                      v-model="userSearch"
                      class="input user-search-input"
                      name="user_search"
                      placeholder="搜索用户名、角色或用户 ID"
                      autocomplete="off"
                      @keyup.enter="applyUserFilters"
                    />
                    <label class="u-sr-only" for="user-role-filter">按角色筛选用户</label>
                    <select id="user-role-filter" v-model="userRoleFilter" class="input user-filter-select" name="user_role_filter" @change="applyUserFilters">
                      <option value="all">全部角色</option>
                      <option value="user">普通用户</option>
                      <option value="admin">管理员</option>
                    </select>
                  </div>
                  <template #actions>
                    <div class="user-toolbar-actions">
                      <button type="button" class="btn btn-secondary ds-btn-secondary btn-sm" :disabled="usersLoading" @click="resetUserFilters">
                        重置
                      </button>
                      <button type="button" class="btn btn-primary ds-btn-primary btn-sm" :disabled="usersLoading" @click="applyUserFilters">
                        {{ usersLoading ? '加载中...' : '搜索' }}
                      </button>
                    </div>
                  </template>
                </PageToolbar>

                <div class="user-table-summary">
                  <span>{{ userPageSummary }}</span>
                  <span>第 {{ userPage }} / {{ userTotalPages }} 页</span>
                </div>

                <StateBlock
                  v-if="usersLoading"
                  class="empty-state-inline account-state-block"
                  type="loading"
                  title="用户列表加载中"
                  description="正在同步当前筛选条件下的用户数据，请稍候。"
                />

                <table v-else-if="paginatedUsers.length" class="data-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>用户名</th>
                      <th>角色</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in paginatedUsers" :key="row.id">
                      <td>{{ row.id }}</td>
                      <td>{{ row.username }}</td>
                      <td>
                        <span class="badge" :class="row.role === 'admin' ? 'badge-primary ds-badge-info' : 'badge-secondary ds-badge'">
                          {{ row.role === 'admin' ? '管理员' : '普通用户' }}
                        </span>
                      </td>
                      <td class="actions">
                        <button v-if="!isSelf(row)" type="button" class="btn btn-sm btn-secondary ds-btn-secondary" @click="resetPassword(row)">
                          重置密码
                        </button>
                        <button v-if="!isSelf(row)" type="button" class="btn btn-sm btn-danger ds-btn-danger" @click="removeUser(row)">
                          删除
                        </button>
                        <span v-if="isSelf(row)" class="text-tertiary text-xs">当前用户</span>
                      </td>
                    </tr>
                  </tbody>
                </table>

                <StateBlock
                  v-else
                  class="empty-state-inline account-state-block"
                  type="empty"
                  title="没有匹配的用户"
                  description="当前筛选条件下没有匹配结果，可以清除筛选后重新查看全部用户。"
                >
                  <template #action>
                    <button type="button" class="btn btn-text ds-btn-ghost text-sm" @click="resetUserFilters">清除筛选</button>
                  </template>
                </StateBlock>

                <div class="user-table-pagination">
                  <button
                    type="button"
                    class="btn btn-secondary ds-btn-secondary btn-sm"
                    :disabled="usersLoading || userPage <= 1"
                    @click="userPage = Math.max(1, userPage - 1); loadUsers()"
                  >
                    上一页
                  </button>
                  <button
                    type="button"
                    class="btn btn-secondary ds-btn-secondary btn-sm"
                    :disabled="usersLoading || userPage >= userTotalPages"
                    @click="userPage = Math.min(userTotalPages, userPage + 1); loadUsers()"
                  >
                    下一页
                  </button>
                </div>
              </div>
            </div>

            <div v-if="accountTab === 'profile'" class="tab-content u-stack">
              <PageHeader
                eyebrow="当前账户"
                title="个人信息与安全"
                description="查看当前账户身份信息，统一在同一侧栏里完成密码修改和安全操作。"
                class="account-page-header"
              >
                <template #meta>
                  <span class="ds-badge-info">{{ user.role === 'admin' ? '管理员' : '普通用户' }}</span>
                </template>
              </PageHeader>

              <PanelCard class="card mb-md account-panel-card">
                <template #header>
                  <h4 class="card-title">基本信息</h4>
                </template>
                <div class="info-grid">
                  <div class="info-item">
                    <label>用户 ID</label>
                    <p>{{ user.id }}</p>
                  </div>
                  <div class="info-item">
                    <label>用户名</label>
                    <p>{{ user.username }}</p>
                  </div>
                  <div class="info-item">
                    <label>角色权限</label>
                    <p>{{ user.role === 'admin' ? '系统管理员' : '普通用户' }}</p>
                  </div>
                </div>
              </PanelCard>

              <PanelCard class="card account-panel-card">
                <template #header>
                  <h4 class="card-title">修改密码</h4>
                </template>
                <div class="form-stack">
                  <StateBlock
                    v-if="changePasswordFeedback"
                    :type="changePasswordFeedbackType === 'success' ? 'info' : 'error'"
                    :title="changePasswordFeedbackType === 'success' ? '密码修改成功' : '密码修改失败'"
                    :description="changePasswordFeedback"
                  />
                  <label class="u-sr-only" for="current-password-input">当前密码</label>
                  <input
                    id="current-password-input"
                    v-model="oldPassword"
                    class="input"
                    name="current_password"
                    type="password"
                    placeholder="当前密码"
                    autocomplete="current-password"
                    @input="clearChangePasswordFeedback"
                  />
                  <label class="u-sr-only" for="self-new-password-input">新密码</label>
                  <input
                    id="self-new-password-input"
                    v-model="selfNewPassword"
                    class="input"
                    name="self_new_password"
                    type="password"
                    placeholder="新密码"
                    autocomplete="new-password"
                    @input="clearChangePasswordFeedback"
                  />
                  <label class="u-sr-only" for="self-confirm-password-input">确认新密码</label>
                  <input
                    id="self-confirm-password-input"
                    v-model="selfConfirmPassword"
                    class="input"
                    name="self_confirm_password"
                    type="password"
                    placeholder="确认新密码"
                    autocomplete="new-password"
                    @input="clearChangePasswordFeedback"
                  />
                  <button type="button" class="btn btn-primary ds-btn-primary w-full mt-sm" :disabled="changingPassword" @click="changeOwnPassword">
                    {{ changingPassword ? '提交中...' : '修改密码' }}
                  </button>
                </div>
              </PanelCard>

              <button type="button" class="btn btn-danger ds-btn-danger w-full mt-xl" @click="logout">
                退出登录
              </button>
            </div>
          </div>
        </aside>
      </div>
    </Transition>

    <Transition name="fade">
      <div v-if="resetTokenModalVisible" class="modal-overlay" @click="closeResetTokenModal">
        <div class="glass-panel modal-card ds-modal-shell" @click.stop>
          <div class="modal-header">
            <h3>重置令牌生成成功</h3>
            <button type="button" class="btn-icon ds-icon-btn" title="关闭重置令牌弹窗" aria-label="关闭重置令牌弹窗" @click="closeResetTokenModal">×</button>
          </div>
          <div class="modal-body">
            <div v-if="resetTokenModalLoading" class="text-center p-md">
              <div class="spinner"></div>
              <p class="text-secondary mt-sm">正在签发重置令牌，请稍候...</p>
            </div>
            <template v-else>
              <p class="text-secondary mb-md">
                请将以下令牌安全转交给用户 <strong>{{ resetTokenModalUsername }}</strong>，有效期 10 分钟。
              </p>
              <StateBlock
                v-if="resetTokenModalSuccess"
                class="mb-md"
                type="info"
                title="令牌签发成功"
                :description="resetTokenModalSuccess"
              />
              <StateBlock
                v-if="resetTokenModalError"
                class="mb-md"
                type="error"
                title="令牌签发失败"
                :description="resetTokenModalError"
              />
              <div v-if="resetTokenModalValue" class="token-box" @click="copyResetToken">
                {{ resetTokenModalValue }}
                <span class="copy-hint">点击复制</span>
              </div>
              <div v-else-if="resetTokenModalError" class="modal-actions">
                <button type="button" class="btn btn-secondary ds-btn-secondary" @click="retryResetPasswordToken">重新签发</button>
              </div>
              <p v-if="resetTokenModalExpiresAt" class="text-xs text-tertiary mt-sm">
                过期时间: {{ formatResetTokenExpiresAt(resetTokenModalExpiresAt) }}
              </p>
            </template>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
:global(:root) {
  --color-bg-soft: #eef3f8;
  --color-panel: #fbfcfe;
  --color-brand: #2563eb;
  --color-brand-hover: #1d4ed8;
  --color-text-primary: #1a1a1a;
  --color-text-secondary: #4a4a4a;
  --color-text-tertiary: #9ca3af;
  --color-border: #e5e7eb;
  --color-danger: #ef4444;
  --color-danger-hover: #dc2626;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-pill: 999px;
  --shadow-sm: 0 8px 20px rgba(17, 24, 39, 0.05);
  --shadow-md: 0 14px 34px rgba(17, 24, 39, 0.07);
  --shadow-lg: 0 22px 42px rgba(17, 24, 39, 0.1);
  --transition-base: all 0.3s ease;
}

:global(body) {
  font-family: 'Plus Jakarta Sans', 'Segoe UI Variable', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  line-height: 1.6;
  color: var(--color-text-primary);
  background: var(--color-bg-soft);
}

/* Layout Utilities */
.screen {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.flex-center {
  display: flex;
  align-items: center;
  justify-content: center;
}

.w-full { width: 100%; }
.text-center { text-align: center; }
.mb-sm { margin-bottom: 8px; }
.mb-md { margin-bottom: 16px; }
.mb-lg { margin-bottom: 24px; }
.mt-sm { margin-top: 8px; }
.mt-md { margin-top: 16px; }
.mt-lg { margin-top: 24px; }
.mt-xl { margin-top: 32px; }
.p-0 { padding: 0; }
.p-md { padding: 16px; }
.p-lg { padding: 32px; }
.pt-md { padding-top: 16px; }
.border-t { border-top: 1px solid var(--color-border); }

.text-secondary { color: var(--color-text-secondary); }
.text-tertiary { color: var(--color-text-tertiary); }
.text-sm { font-size: 13px; }
.text-xs { font-size: 12px; }
.overflow-hidden { overflow: hidden; }

.bg-pattern {
  background:
    radial-gradient(1000px 500px at 10% -10%, rgba(37, 99, 235, 0.1), transparent 60%),
    radial-gradient(800px 420px at 100% 0%, rgba(59, 130, 246, 0.09), transparent 65%),
    linear-gradient(180deg, #f4f7fb 0%, #eef3f8 100%),
    var(--color-bg-soft);
}

.glass-panel {
  background: rgba(251, 252, 254, 0.94);
  border: 1px solid rgba(226, 232, 240, 0.85);
  box-shadow: var(--shadow-md);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.input {
  width: 100%;
  height: 44px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 0 14px;
  background: #ffffff;
  color: var(--color-text-primary);
  font-size: 14px;
  transition: var(--transition-base);
  outline: none;
}

.input:hover {
  border-color: #d1d5db;
}

.input:focus {
  border-color: var(--color-brand);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.14);
}

.btn {
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  height: 42px;
  padding: 0 16px;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.01em;
  cursor: pointer;
  transition: var(--transition-base);
}

.btn:disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--color-brand);
  color: #ffffff;
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.25);
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  background: var(--color-brand-hover);
  box-shadow: 0 14px 30px rgba(37, 99, 235, 0.28);
}

.btn-secondary {
  background: #f1f5f9;
  color: var(--color-text-primary);
  border-color: #e2e8f0;
}

.btn-secondary:hover:not(:disabled) {
  transform: translateY(-2px);
  background: #e8eef5;
}

.btn-danger {
  background: var(--color-danger);
  color: #ffffff;
}

.btn-danger:hover:not(:disabled) {
  transform: translateY(-2px);
  background: var(--color-danger-hover);
}

.btn-icon {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: var(--radius-pill);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  background: #f1f5f9;
  color: var(--color-text-secondary);
  transition: var(--transition-base);
}

.btn-icon:hover {
  transform: translateY(-1px);
  background: #e2e8f0;
  color: var(--color-text-primary);
}

.spinner,
.spinner-sm {
  border-radius: var(--radius-pill);
  border: 2px solid rgba(37, 99, 235, 0.2);
  border-top-color: var(--color-brand);
  animation: spin 0.9s linear infinite;
}

.spinner {
  width: 30px;
  height: 30px;
  margin: 0 auto;
}

.spinner-sm {
  width: 14px;
  height: 14px;
  display: inline-block;
  margin-right: 6px;
  vertical-align: -2px;
}

/* Login */
.login-card {
  width: min(92vw, 420px);
  padding: 40px;
  border-radius: 24px;
}

.brand-text {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
  color: var(--color-brand);
  margin-bottom: 8px;
}

.welcome-text {
  font-size: 30px;
  line-height: 1.25;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.sub-text {
  color: var(--color-text-secondary);
  font-size: 14px;
  line-height: 1.6;
}

.form-group {
  margin-bottom: 16px;
}

.footer-tip {
  font-size: 12px;
  color: var(--color-text-tertiary);
  line-height: 1.7;
}

.btn-text {
  background: transparent;
  color: var(--color-text-secondary);
  box-shadow: none;
}

.btn-text:hover {
  color: var(--color-brand);
  background: rgba(37, 99, 235, 0.06);
}

/* App Shell & FAB */
.app-shell,
.map-layer {
  position: fixed;
  inset: 0;
  overflow: hidden;
}

.account-fab {
  position: fixed;
  top: 24px;
  right: 84px;
  z-index: 2000;
  border: 1px solid rgba(255, 255, 255, 0.7);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 16px 6px 6px;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-md);
  transition: var(--transition-base);
}

.account-fab.open {
  box-shadow: var(--shadow-lg);
}

.account-fab:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
  background: #ffffff;
}

.shadow-lg {
  box-shadow: var(--shadow-lg);
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
}

.username {
  font-weight: 600;
  font-size: 14px;
  color: var(--color-text-primary);
}

/* Sidebar */
.sidebar-mask {
  position: fixed;
  inset: 0;
  z-index: 3000;
  background: rgba(15, 23, 42, 0.22);
  backdrop-filter: blur(2px);
  display: flex;
  justify-content: flex-end;
}

.sidebar {
  width: 496px;
  max-width: 92vw;
  height: 100%;
  background: rgba(255, 255, 255, 0.95);
  display: flex;
  flex-direction: column;
  padding: 24px;
  border-left: 1px solid var(--color-border);
  box-shadow: -24px 0 46px rgba(17, 24, 39, 0.08);
  animation: slideInRight 0.32s cubic-bezier(0.16, 1, 0.3, 1);
}

.sidebar-content {
  flex: 1;
  overflow: auto;
  padding-right: 2px;
}

.sidebar-content::-webkit-scrollbar {
  width: 8px;
}

.sidebar-content::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: var(--radius-pill);
}

.form-stack {
  display: grid;
  gap: 12px;
}

.reset-panel {
  margin-top: 16px;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.overline {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--color-text-tertiary);
  margin-bottom: 4px;
}

.sidebar-header h3 {
  font-size: 22px;
  line-height: 1.3;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
}

.badge {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  background: #eff6ff;
  color: var(--color-brand);
  font-weight: 700;
}

.badge-primary {
  background: #eff6ff;
  color: var(--color-brand);
}

.badge-secondary {
  background: #f3f4f6;
  color: var(--color-text-secondary);
}

.tabs-nav {
  display: flex;
  gap: 8px;
  padding: 4px;
  background: #f3f4f6;
  border-radius: var(--radius-md);
  margin-bottom: 24px;
}

.tab-btn {
  flex: 1;
  padding: 10px 8px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  font-weight: 600;
  font-size: 14px;
  transition: var(--transition-base);
}

.tab-btn:hover {
  background: rgba(255, 255, 255, 0.75);
}

.tab-btn.active {
  background: #ffffff;
  color: var(--color-text-primary);
  box-shadow: var(--shadow-sm);
}

/* Cards & Tables */
.card {
  background: #ffffff;
  border-radius: var(--radius-lg);
  padding: 20px;
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
}

.card-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 16px;
  color: var(--color-text-primary);
}

.info-grid {
  display: grid;
  gap: 16px;
}

.info-item label {
  font-size: 12px;
  color: var(--color-text-tertiary);
  display: block;
  margin-bottom: 4px;
}

.info-item p {
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-primary);
  font-weight: 600;
}

.create-user-form {
  display: grid;
  gap: 12px;
  grid-template-columns: 1fr 1fr 112px auto;
}

.create-user-feedback {
  grid-column: 1 / -1;
}

.user-table-toolbar {
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
}

.user-toolbar-fields {
  min-width: 0;
}

.user-search-input {
  width: 100%;
  min-width: 0;
  max-width: 220px;
  flex: 0 1 220px;
  box-sizing: border-box;
}

.user-filter-select {
  width: 100%;
  min-width: 0;
  max-width: 140px;
  flex: 0 1 140px;
  box-sizing: border-box;
}

.user-toolbar-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.user-table-summary,
.user-table-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 16px 16px;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.user-table-summary {
  padding-top: 12px;
}

.empty-state-inline {
  display: grid;
  gap: 10px;
  justify-items: start;
  padding: 20px 16px;
  color: var(--color-text-secondary);
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th {
  text-align: left;
  padding: 12px 16px;
  font-size: 12px;
  font-weight: 700;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
  background: #f8fafc;
}

.data-table td {
  padding: 14px 16px;
  border-bottom: 1px solid var(--color-border);
  font-size: 14px;
  line-height: 1.55;
}

.data-table tbody tr {
  transition: var(--transition-base);
}

.data-table tbody tr:hover {
  background: #f8fafc;
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.btn-sm {
  padding: 4px 12px;
  font-size: 12px;
  height: 30px;
  border-radius: var(--radius-sm);
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 4000;
  backdrop-filter: blur(4px);
}

.modal-card {
  background: #ffffff;
  width: min(92vw, 420px);
  max-width: 100%;
  padding: 24px;
  border-radius: 20px;
  box-shadow: var(--shadow-lg);
  min-width: 0;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  gap: 12px;
  min-width: 0;
}

.modal-header h3 {
  font-size: 18px;
  line-height: 1.4;
  font-weight: 700;
  min-width: 0;
}

.token-box {
  background: #f3f4f6;
  border: 1px dashed #d1d5db;
  padding: 16px;
  border-radius: var(--radius-md);
  font-family: 'Cascadia Mono', 'Consolas', monospace;
  font-size: 16px;
  line-height: 1.6;
  text-align: left;
  cursor: pointer;
  position: relative;
  transition: var(--transition-base);
  display: block;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-all;
  box-sizing: border-box;
}

.token-box:hover {
  transform: translateY(-2px);
  background: #eef2f7;
  border-color: #94a3b8;
}

.copy-hint {
  display: block;
  font-size: 10px;
  color: var(--color-text-tertiary);
  margin-top: 12px;
  font-family: 'Plus Jakarta Sans', 'Segoe UI Variable', sans-serif;
  text-align: right;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
}

@keyframes slideInRight {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Transitions */
.fade-up-enter-active,
.fade-up-leave-active {
  transition: opacity 0.34s ease, transform 0.34s ease;
}

.fade-up-enter-from,
.fade-up-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.24s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.32s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.32s ease;
}

.slide-right-enter-from,
.slide-right-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

@media (max-width: 900px) {
  .account-fab {
    top: 16px;
    right: 16px;
    padding-right: 12px;
  }

  .username {
    max-width: 120px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .sidebar {
    width: 100vw;
    max-width: 100vw;
    padding: 16px;
  }

  .create-user-form {
    grid-template-columns: 1fr;
  }

  .user-table-toolbar,
  .user-table-summary,
  .user-table-pagination {
    grid-template-columns: 1fr;
    flex-direction: column;
    align-items: stretch;
  }

  .user-toolbar-actions {
    justify-content: stretch;
  }

  .data-table {
    min-width: 560px;
  }
}

@media (max-width: 640px) {
  .login-card {
    padding: 24px;
    border-radius: var(--radius-lg);
  }

  .welcome-text {
    font-size: 24px;
  }

  .btn,
  .input {
    height: 42px;
  }

  .actions {
    gap: 6px;
  }
}
</style>

<style scoped>
.login-card {
  border-radius: var(--ds-radius-xl);
  border-color: rgba(255, 255, 255, 0.68);
  box-shadow: var(--ds-shadow-lg);
}

.login-card .input,
.reset-panel .input,
.create-user-form .input,
.form-stack .input,
.user-table-toolbar :deep(input),
.user-table-toolbar :deep(select) {
  min-height: 44px;
  border-radius: 14px;
  border-color: var(--ds-border-strong);
  background: rgba(255, 255, 255, 0.92);
}

.sidebar.ds-sidebar-shell {
  border-left-color: var(--ds-border-soft);
  box-shadow: -24px 0 46px rgba(15, 23, 42, 0.08);
}

.sidebar-header {
  padding: 0;
  margin-bottom: var(--ds-space-5);
  border: none;
  background: transparent;
  box-shadow: none;
}

.account-page-header {
  padding: var(--ds-space-5);
}

.account-panel-card {
  border-radius: var(--ds-radius-xl);
  border-color: var(--ds-card-border);
  box-shadow: var(--ds-shadow-sm);
}

.user-table-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  border-radius: 0;
  border-top: 0;
  border-left: 0;
  border-right: 0;
  box-shadow: none;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.86), rgba(255, 255, 255, 0.92));
}

.user-table-toolbar :deep(.ds-page-toolbar__content) {
  display: block;
  min-width: 0;
}

.user-table-toolbar :deep(.ds-page-toolbar__actions) {
  width: auto;
  min-width: max-content;
  flex-wrap: nowrap;
  justify-content: flex-end;
}

.user-toolbar-fields {
  display: grid;
  grid-template-columns: minmax(0, 220px) minmax(0, 140px);
  gap: 12px;
  align-items: center;
  justify-content: start;
  width: max-content;
  max-width: 100%;
}

.account-state-block {
  margin: 16px;
}

.badge,
.badge-primary {
  color: var(--ds-primary-600);
  border: 1px solid rgba(37, 99, 235, 0.16);
  background: rgba(219, 234, 254, 0.88);
}

.badge-secondary {
  color: var(--ds-text-secondary);
  border: 1px solid var(--ds-border-soft);
  background: rgba(255, 255, 255, 0.82);
}

.modal-card.ds-modal-shell {
  border-radius: var(--ds-radius-xl);
  border-color: rgba(255, 255, 255, 0.68);
  padding: var(--ds-space-6);
}

.modal-header {
  margin-bottom: var(--ds-space-5);
}

.token-box {
  border-radius: var(--ds-radius-lg);
  border-color: var(--ds-border-strong);
  background: rgba(248, 250, 252, 0.92);
}

@media (max-width: 900px) {
  .user-table-toolbar {
    grid-template-columns: 1fr;
  }

  .user-table-toolbar :deep(.ds-page-toolbar__content) {
    display: block;
  }

  .user-table-toolbar :deep(.ds-page-toolbar__actions) {
    justify-content: stretch;
    min-width: 0;
    flex-wrap: wrap;
  }

  .user-toolbar-fields {
    grid-template-columns: 1fr;
  }

  .user-search-input,
  .user-filter-select {
    min-width: 0;
    flex-basis: auto;
  }
}
</style>
