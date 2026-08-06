export const errorCodeMap = {
  COMMON_INVALID_PARAM: '请求参数不正确，请检查输入',
  COMMON_NOT_FOUND: '请求的资源不存在',
  COMMON_CONFLICT: '操作冲突，请稍后重试',
  COMMON_INTERNAL_ERROR: '服务器处理失败，请稍后重试',

  DB_UPDATE_RUNNING: '数据库更新任务正在执行，请稍后再试',
  DB_UPDATE_MISSING_HOST: '请填写服务器地址',
  DB_UPDATE_INVALID_HOST: '服务器地址格式无效',
  DB_UPDATE_MISSING_PASSWORD: '请填写 SSH 密码',
  DB_UPDATE_INVALID_PORT: 'SSH 端口号无效',
  DB_UPDATE_CONFIG_SAVE_FAILED: '保存服务器配置失败，请稍后重试',

  SCAN_MISSING_IP_SEGMENT: '缺少 IP 段参数',
  SCAN_INVALID_IP_SEGMENT: 'IP 段格式无效',
  SCAN_REPORT_DIR_MISSING: '扫描报告目录不存在',
  SCAN_REPORT_NOT_FOUND: '未找到该网段扫描报告',

  AUTH_UNAUTHORIZED: '请先登录',
  AUTH_INVALID_TOKEN: '登录信息无效，请重新登录',
  AUTH_TOKEN_EXPIRED: '登录已过期，请重新登录',
  AUTH_TOKEN_REVOKED: '登录状态已失效，请重新登录',
  AUTH_FORBIDDEN: '当前账号权限不足',
  AUTH_USER_NOT_FOUND: '用户不存在',
  AUTH_USER_DISABLED: '账号已禁用，请联系管理员',
  AUTH_LOGIN_INVALID_INPUT: '请输入用户名和密码',
  AUTH_LOGIN_FAILED: '用户名或密码错误',
  AUTH_LOGIN_RATE_LIMITED: '登录尝试过于频繁，请稍后重试',
  AUTH_CHANGE_PASSWORD_INVALID_INPUT: '密码参数无效',
  AUTH_CHANGE_PASSWORD_INVALID_OLD: '旧密码不正确',
  AUTH_RESET_TOKEN_DELIVERY_NOT_FOUND: '重置令牌投递单不存在或已失效',
  AUTH_RESET_TOKEN_DELIVERY_FORBIDDEN: '无权查看该重置令牌',
  AUTH_RESET_TOKEN_DELIVERY_EXPIRED: '重置令牌投递单已过期，请重新签发',
  AUTH_RESET_TOKEN_DELIVERY_USED: '重置令牌已被读取，请重新签发',
  AUTH_USER_CREATE_INVALID_INPUT: '创建用户参数无效',
  AUTH_USER_ALREADY_EXISTS: '用户名已存在',
  AUTH_USER_INVALID_ROLE: '角色无效',
  AUTH_USER_INVALID_STATUS: '用户状态无效',
  AUTH_DELETE_SELF_FORBIDDEN: '不能删除当前登录用户',
  AUTH_UPDATE_SELF_FORBIDDEN: '不能将当前登录管理员降权或禁用',
  AUTH_LAST_ADMIN_FORBIDDEN: '系统至少需要保留一个可用管理员',
}

export function messageByCode(code, fallback = '请求失败，请稍后重试') {
  if (!code) return fallback
  return errorCodeMap[code] || fallback
}
