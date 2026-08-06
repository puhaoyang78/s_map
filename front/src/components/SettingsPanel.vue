<template>
  <div v-if="visible" class="panel-overlay" @click="$emit('close')">
    <div class="panel-content ds-modal-shell" @click.stop>
      <div class="panel-header-shell">
        <PageHeader
          eyebrow="探测任务"
          title="任务工作台"
          description="创建、跟踪和回看探测任务，统一承接任务草稿、执行状态、历史记录与日志详情。"
          class="panel-page-header"
        >
          <template #meta>
            <span class="ds-badge-info">{{ detecting ? '执行中' : '待命中' }}</span>
            <span class="ds-badge">{{ historyJobs.length }} 条历史</span>
          </template>
          <template #extra>
            <button class="close-btn ds-icon-btn" @click="$emit('close')">×</button>
          </template>
        </PageHeader>
      </div>

      <div class="panel-body u-stack">
        <PanelCard as="section" class="panel-section task-workbench-panel">
          <h4>新建探测任务</h4>
          <p>支持全球探测或定向区域探测。定向模式最多可选择 5 个区域，优先展示中国周边重点区域。</p>

          <div class="detection-form">
            <div class="form-group">
              <label>探测范围：</label>
              <select v-model="detectionScope" :disabled="detecting">
                <option value="global">全球探测</option>
                <option value="selected">定向区域（最多 5 个）</option>
              </select>
            </div>

            <div v-if="detectionScope === 'selected'" class="form-group">
              <StateBlock
                v-if="detecting"
                class="form-group-help-block"
                type="info"
                title="当前区域列表作为下一次任务草稿"
                description="执行中的任务范围以下方任务摘要为准，这里的区域选择只保留为下一次新建任务的草稿。"
              />
              <label>区域列表：</label>
              <PageToolbar class="region-toolbar region-toolbar-shell">
                <input
                  v-model="regionKeyword"
                  type="text"
                  :disabled="detecting || loadingRegions"
                  placeholder="搜索国家、州、城市或代码"
                />
                <template #actions>
                  <button
                    type="button"
                    class="region-clear-btn ds-btn-secondary"
                    :disabled="detecting || loadingRegions || selectedRegions.length === 0"
                    @click="selectedRegions = []"
                  >
                    清空
                  </button>
                </template>
              </PageToolbar>

              <div class="region-checklist" :class="{ disabled: detecting || loadingRegions }">
                <div v-if="loadingRegions" class="region-empty">区域加载中...</div>
                <template v-else>
                  <button
                    v-for="region in filteredRegionOptions"
                    :key="region.value"
                    type="button"
                    class="region-option"
                    :class="{ selected: isRegionSelected(region.value) }"
                    :disabled="detecting"
                    @click="toggleRegionSelection(region.value)"
                  >
                    <span class="region-checkbox" :class="{ checked: isRegionSelected(region.value) }">
                      <span class="region-checkmark">✓</span>
                    </span>
                    <span class="region-labels">
                      <span class="region-primary">{{ region.city || region.code3 }}</span>
                      <span class="region-secondary">{{ region.country }} 路 {{ region.state }}</span>
                    </span>
                  </button>
                  <div v-if="filteredRegionOptions.length === 0" class="region-empty">未找到匹配区域</div>
                </template>
              </div>

              <div class="region-meta">
                  <span>已选 {{ selectedRegions.length }} / {{ maxSelectableRegions }}</span>
                <span>{{ filteredRegionOptions.length }} / {{ regionOptions.length }}</span>
              </div>

              <div v-if="draftRegionSummary.length > 0" class="draft-region-summary">
                <div class="draft-region-summary-header">
                  <strong>当前草稿探测范围</strong>
                  <span>{{ draftRegionSummary.length }} 个区域</span>
                </div>
                <div class="task-region-tags">
                  <span v-for="item in draftRegionSummary" :key="item.key" class="task-region-tag">
                    <strong>{{ item.primary }}</strong>
                    <span v-if="item.secondary">{{ item.secondary }}</span>
                  </span>
                </div>
              </div>

              <StateBlock v-if="regionLoadError" type="error" title="区域列表加载失败" :description="regionLoadError">
                <template #action>
                  <button type="button" class="feedback-btn ds-btn-secondary" :disabled="loadingRegions" @click="loadDetectionRegions">
                      {{ loadingRegions ? '重试中...' : '重试' }}
                  </button>
                </template>
              </StateBlock>
            </div>

            <div class="form-actions">
              <button class="detection-btn ds-btn-primary" :disabled="detecting" @click="startDetection">
                <span v-if="detecting">探测中...</span>
                <span v-else>{{ detectionScope === 'selected' ? '开始定向探测' : '开始全球探测' }}</span>
              </button>

              <button v-if="detecting" class="stop-btn ds-btn-danger" :disabled="stoppingDetection" @click="stopDetection">
                {{ stoppingDetection ? '停止中...' : '停止探测' }}
              </button>
            </div>

            <StateBlock
              v-if="taskFeedback"
              :type="taskFeedbackType === 'error' ? 'error' : taskFeedbackType === 'success' ? 'info' : 'loading'"
              :title="taskFeedbackType === 'error' ? '操作失败' : taskFeedbackType === 'success' ? '操作成功' : '操作提示'"
              :description="taskFeedback"
            />
          </div>

          <div v-if="hasTaskSummary" class="task-summary-card ds-surface-card">
            <div class="task-summary-header">
              <div class="task-summary-heading">
                <span class="task-summary-eyebrow">{{ currentTaskSummaryTitle }}</span>
                <div class="task-summary-title-row">
                  <span class="task-status-pill" :class="`task-status-pill-${currentTaskStatusTone}`">
                    {{ currentTaskStatusLabel }}
                  </span>
                  <span class="task-scope-pill">{{ currentTaskScopeLabel }}</span>
                </div>
              </div>
              <button
                v-if="selectedHistoryJobId || currentJobId"
                type="button"
                class="feedback-btn feedback-btn-quiet"
                @click="retrySelectedJob"
              >
                刷新详情
              </button>
            </div>

            <div class="task-summary-grid">
              <div class="task-summary-item">
                <span>任务 ID</span>
                <strong>{{ currentTaskShortId }}</strong>
              </div>
              <div class="task-summary-item">
                <span>创建时间</span>
                <strong>{{ currentTaskCreatedAtLabel }}</strong>
              </div>
              <div class="task-summary-item">
                <span>探测范围</span>
                <strong>{{ currentTaskScopeLabel }}</strong>
              </div>
              <div class="task-summary-item">
                <span>区域数量</span>
                <strong>{{ currentTaskRegionCountLabel }}</strong>
              </div>
            </div>

            <div class="task-summary-range">
              <div class="task-summary-range-label">当前探测范围</div>
              <div v-if="currentTaskContext.scope === 'global'" class="task-summary-note">
                全球探测，覆盖全部可用区域。
              </div>
              <div v-else-if="currentTaskRegionSummary.length > 0" class="task-region-tags">
                <span v-for="item in currentTaskRegionSummary" :key="item.key" class="task-region-tag">
                  <strong>{{ item.primary }}</strong>
                  <span v-if="item.secondary">{{ item.secondary }}</span>
                </span>
              </div>
              <div v-else class="task-summary-note task-summary-note-warning">
                当前任务暂未返回区域列表，请点击“刷新详情”重新获取。
              </div>
            </div>
          </div>

          <div v-if="detecting || detectionProgress.show" class="detection-progress ds-surface-card">
            <h5>探测进度</h5>
            <div class="progress-bar-container">
              <div class="progress-bar" :style="{ width: detectionProgress.percentage + '%' }">
                <span v-if="detectionProgress.percentage > 10" class="progress-text">{{ detectionProgress.percentage }}%</span>
              </div>
            </div>
            <div class="progress-info">
              <span>{{ detectionProgress.current }} / {{ detectionProgress.total }}</span>
              <span v-if="detectionProgress.eta">预计剩余：{{ detectionProgress.eta }}</span>
            </div>
            <div class="current-task">当前任务：{{ detectionProgress.currentTask }}</div>
          </div>

          <div class="detection-logs ds-surface-card">
            <h5>探测记录</h5>
            <PageToolbar class="history-toolbar history-toolbar-shell">
              <input
                v-model="historyKeyword"
                type="text"
                placeholder="按任务 ID、状态或消息搜索"
              />
              <select v-model="historyStatus">
                <option
                  v-for="option in HISTORY_STATUS_OPTIONS"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
              <template #actions>
                <button class="clear-btn ds-btn-secondary" :disabled="clearingHistory" @click="clearHistory">
                  {{ clearingHistory ? '清空中...' : '清空历史' }}
                </button>
              </template>
            </PageToolbar>

            <div class="history-list">
              <div v-if="historyLoading" class="no-logs">正在加载历史任务...</div>
              <StateBlock
                v-else-if="historyLoadError"
                class="history-state-block"
                type="error"
                title="历史任务加载失败"
                :description="historyLoadError"
              >
                <template #action>
                  <button type="button" class="feedback-btn ds-btn-secondary" @click="reloadHistory">重试</button>
                </template>
              </StateBlock>
              <StateBlock
                v-else-if="historyJobs.length === 0"
                class="history-state-block"
                type="empty"
                :title="historyEmptyState.title"
                :description="historyEmptyState.message"
              >
                <template #action>
                  <button
                    v-if="hasHistoryFilters"
                    type="button"
                    class="feedback-btn ds-btn-secondary"
                    @click="resetHistoryFilters"
                  >
                    清除筛选
                  </button>
                </template>
              </StateBlock>
              <div v-else class="history-items">
                <button
                  v-for="job in historyJobs"
                  :key="job.id"
                  class="history-item"
                  :class="{ active: selectedHistoryJobId === job.id }"
                  @click="selectHistoryJob(job.id)"
                >
                  <span class="history-job-id">{{ job.id.slice(0, 8) }}</span>
                  <span class="history-job-status">{{ mapStatusLabel(job.status) }}</span>
                  <span class="history-job-time">{{ formatDateTime(job.created_at) }}</span>
                  <span class="history-job-scope">{{ formatJobScopeSummary(job) }}</span>
                </button>
              </div>
            </div>

            <div class="logs-container">
              <StateBlock
                v-if="jobDetailError || pollingError"
                class="logs-empty-state"
                type="error"
                :title="jobDetailError ? '任务详情加载失败' : '任务状态刷新失败'"
                :description="jobDetailError || pollingError"
              >
                <template #action>
                  <button type="button" class="feedback-btn ds-btn-secondary" @click="retrySelectedJob">重试</button>
                </template>
              </StateBlock>
              <StateBlock
                v-else-if="!selectedHistoryJobId"
                class="logs-empty-state"
                type="empty"
                title="请选择历史任务"
                description="选择左侧历史任务后，这里会显示任务日志和执行状态。"
              />
              <StateBlock
                v-else-if="detectionLogs.length === 0"
                class="logs-empty-state"
                type="empty"
                title="暂无任务日志"
                description="当前任务还没有可展示的执行日志。"
              />
              <div v-else class="log-list">
                <div v-for="(log, index) in detectionLogs" :key="index" class="log-item" :class="log.type">
                  <div class="log-time">{{ formatLogTime(log.timestamp) }}</div>
                  <div class="log-message">{{ log.message }}</div>
                  <div v-if="log.details" class="log-details">{{ log.details }}</div>
                </div>
              </div>
            </div>
          </div>
        </PanelCard>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, onUnmounted, ref, watch } from 'vue'
import PageHeader from './ui/PageHeader.vue'
import PageToolbar from './ui/PageToolbar.vue'
import PanelCard from './ui/PanelCard.vue'
import StateBlock from './ui/StateBlock.vue'
import { notify, confirmAction } from '../utils/notify.js'
import {
  createDetectionJob,
  getDetectionJob,
  cancelDetectionJob,
  listDetectionJobs,
  listDetectionRegions,
  clearDetectionHistory,
} from '../api/detection.js'

const { setInterval, clearInterval, setTimeout, clearTimeout } = globalThis

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['close'])
const setSnapshot = inject('setSnapshot', null)

const detecting = ref(false)
const detectionProgress = ref({
  show: false,
  percentage: 0,
  current: 0,
  total: 0,
  eta: '',
  currentTask: '',
})
const detectionLogs = ref([])
const currentJobId = ref('')
const allHistoryJobs = ref([])
const historyJobs = ref([])
const historyKeyword = ref('')
const historyStatus = ref('')
const historyLoading = ref(false)
const clearingHistory = ref(false)
const stoppingDetection = ref(false)
const selectedHistoryJobId = ref('')
const detectionScope = ref('global')
const regionOptions = ref([])
const loadingRegions = ref(false)
const regionLoadError = ref('')
const historyLoadError = ref('')
const jobDetailError = ref('')
const pollingError = ref('')
const taskFeedback = ref('')
const taskFeedbackType = ref('info')
const selectedRegions = ref([])
const maxSelectableRegions = ref(5)
const regionKeyword = ref('')
const currentTaskContext = ref({
  jobId: '',
  status: '',
  scope: 'global',
  regions: [],
  createdAt: '',
  message: '',
})
let pollingTimer = null
let pollingErrorNotified = false
let pollingConsecutiveFailures = 0
let historyFilterTimer = null
const taskViewEpoch = ref(0)

const bumpTaskViewEpoch = () => {
  taskViewEpoch.value += 1
  return taskViewEpoch.value
}

const setTaskFeedback = (message, type = 'info') => {
  taskFeedback.value = message
  taskFeedbackType.value = type
}

const clearTaskFeedback = () => {
  taskFeedback.value = ''
  taskFeedbackType.value = 'info'
}

const stopPolling = () => {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

const resetTaskViewState = () => {
  bumpTaskViewEpoch()
  detecting.value = false
  stoppingDetection.value = false
  currentJobId.value = ''
  selectedHistoryJobId.value = ''
  jobDetailError.value = ''
  pollingError.value = ''
  clearCurrentTaskContext()
  detectionLogs.value = []
  detectionProgress.value = {
    show: false,
    percentage: 0,
    current: 0,
    total: 0,
    eta: '',
    currentTask: '',
  }
}

const normalizeProbeRegions = (rawRegions) => {
  if (!Array.isArray(rawRegions)) return []
  const normalized = []
  const seen = new Set()
  for (const item of rawRegions) {
    if (typeof item !== 'string') continue
    const parts = item.split(',').map((p) => p.trim())
    if (parts.length !== 3 || parts.some((p) => !p)) continue
    const key = parts.join(',')
    if (seen.has(key)) continue
    seen.add(key)
    normalized.push(key)
  }
  return normalized
}

const applySelectedRegionsLimit = (regions) => {
  const normalized = normalizeProbeRegions(regions)
  if (normalized.length <= maxSelectableRegions.value) {
    return normalized
  }
  return normalized.slice(0, maxSelectableRegions.value)
}

const clearCurrentTaskContext = () => {
  currentTaskContext.value = {
    jobId: '',
    status: '',
    scope: 'global',
    regions: [],
    createdAt: '',
    message: '',
  }
}

const regionDisplayMap = computed(() => {
  const map = new Map()
  for (const region of regionOptions.value) {
    const primary = region?.city || region?.code3 || region?.value || '未命名区域'
    const secondary = [region?.country, region?.state].filter(Boolean).join(' 路 ')
    map.set(region.value, {
      key: region.value,
      primary,
      secondary,
      text: [primary, secondary].filter(Boolean).join(' 路 '),
    })
  }
  return map
})

const buildRegionSummary = (regions = []) =>
  applySelectedRegionsLimit(regions).map((value) => {
    const known = regionDisplayMap.value.get(value)
    if (known) {
      return known
    }
    const parts = String(value || '')
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
    const [country, state, city] = parts
    const primary = city || state || country || value
    const secondary = [country, state]
      .filter(Boolean)
      .filter((item, index, list) => item !== primary && list.indexOf(item) === index)
      .join(' 路 ')
    return {
      key: value,
      primary,
      secondary,
      text: [primary, secondary].filter(Boolean).join(' 路 '),
    }
  })

const draftRegionSummary = computed(() => buildRegionSummary(selectedRegions.value))

const currentTaskRegionSummary = computed(() => buildRegionSummary(currentTaskContext.value.regions))

const hasHistoryFilters = computed(() => Boolean((historyKeyword.value || '').trim() || historyStatus.value))

const historyEmptyState = computed(() => {
  if (hasHistoryFilters.value && allHistoryJobs.value.length > 0) {
    return {
      title: '没有匹配的历史任务',
      message: '请调整筛选条件，或清除筛选后重新查看全部记录。',
    }
  }
  return {
    title: '暂无历史任务',
    message: '创建或恢复探测任务后，这里会显示执行记录。',
  }
})

const currentTaskScopeLabel = computed(() =>
  currentTaskContext.value.scope === 'selected' ? '定向探测' : '全球探测'
)

const currentTaskStatusLabel = computed(() => {
  if (currentTaskContext.value.status) {
    return mapStatusLabel(currentTaskContext.value.status)
  }
  return detecting.value ? '执行中' : '待查看'
})

const currentTaskStatusTone = computed(() => {
  const status = currentTaskContext.value.status
  if (status === 'failed') return 'error'
  if (status === 'activated') return 'success'
  if (status === 'canceled') return 'warning'
  if (isActiveStatus(status) || detecting.value) return 'info'
  return 'muted'
})

const currentTaskSummaryTitle = computed(() => {
  if (detecting.value) return '当前执行任务'
  if (selectedHistoryJobId.value) return '当前查看任务'
  return '最近任务摘要'
})

const currentTaskShortId = computed(() =>
  currentTaskContext.value.jobId ? currentTaskContext.value.jobId.slice(0, 8) : '—'
)

const currentTaskCreatedAtLabel = computed(() =>
  currentTaskContext.value.createdAt ? formatDateTime(currentTaskContext.value.createdAt) : '—'
)

const currentTaskRegionCountLabel = computed(() => {
  if (currentTaskContext.value.scope === 'global') {
    return '全部区域'
  }
  return `${currentTaskRegionSummary.value.length} 个区域`
})

const hasTaskSummary = computed(() =>
  Boolean(currentTaskContext.value.jobId || currentTaskContext.value.message || detectionProgress.value.show)
)

const setCurrentTaskContext = (job = null, fallback = {}) => {
  const scopeRaw = (job?.target_scope || fallback.scope || 'global').toLowerCase()
  const scope = scopeRaw === 'selected' ? 'selected' : 'global'
  currentTaskContext.value = {
    jobId: job?.id || fallback.jobId || '',
    status: job?.status || fallback.status || '',
    scope,
    regions: applySelectedRegionsLimit(job?.target_regions || fallback.regions || []),
    createdAt: job?.created_at || fallback.createdAt || '',
    message: job?.message || job?.step || fallback.message || '',
  }
}

const formatJobScopeSummary = (job) => {
  const scope = (job?.target_scope || 'global').toLowerCase() === 'selected' ? 'selected' : 'global'
  if (scope === 'global') {
    return '全球探测'
  }
  const regions = buildRegionSummary(job?.target_regions || [])
  if (regions.length === 0) {
    return '定向探测'
  }
  const preview = regions.slice(0, 2).map((item) => item.primary).join('、')
  return regions.length > 2 ? `${preview} 等 ${regions.length} 个区域` : `${preview} · ${regions.length} 个区域`
}

const resetHistoryFilters = async () => {
  historyKeyword.value = ''
  historyStatus.value = ''
  await runHistoryFilter()
}

const filteredRegionOptions = computed(() => {
  const keyword = (regionKeyword.value || '').trim().toLowerCase()
  if (!keyword) {
    return regionOptions.value
  }
  return regionOptions.value.filter((region) => {
    const fields = [
      region?.display_name,
      region?.value,
      region?.country,
      region?.state,
      region?.city,
      region?.code1,
      region?.code2,
      region?.code3,
    ]
    return fields.some((field) => toLowerText(field).includes(keyword))
  })
})

const isRegionSelected = (value) => selectedRegions.value.includes(value)

const toggleRegionSelection = (value) => {
  if (!value || detecting.value || loadingRegions.value) {
    return
  }
  const idx = selectedRegions.value.indexOf(value)
  if (idx >= 0) {
    selectedRegions.value = selectedRegions.value.filter((item) => item !== value)
    return
  }
  if (selectedRegions.value.length >= maxSelectableRegions.value) {
    notify.warning(`最多可选择 ${maxSelectableRegions.value} 个区域`)
    return
  }
  selectedRegions.value = [...selectedRegions.value, value]
}

const HISTORY_STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'queued', label: '排队中' },
  { value: 'dispatching', label: '下发中' },
  { value: 'running', label: '执行中' },
  { value: 'artifact_ready', label: '产物就绪' },
  { value: 'importing', label: '导入中' },
  { value: 'activated', label: '已激活' },
  { value: 'failed', label: '失败' },
  { value: 'canceled', label: '已取消' },
]

const STATUS_LABELS = HISTORY_STATUS_OPTIONS.reduce((acc, item) => {
  if (item.value) {
    acc[item.value] = item.label
  }
  return acc
}, {})

const isTerminalStatus = (status) => ['activated', 'failed', 'canceled'].includes(status)

const isActiveStatus = (status) => ['queued', 'dispatching', 'running', 'artifact_ready', 'importing'].includes(status)

const parseBackendUtcDate = (value) => {
  if (!value) return null
  const normalized = String(value).trim().replace(' ', 'T')
  const isoText = /(?:Z|[+-]\d{2}:\d{2})$/.test(normalized) ? normalized : `${normalized}Z`
  const parsed = new Date(isoText)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const formatLocalDateTime = (value) => {
  const parsed = parseBackendUtcDate(value)
  if (!parsed) {
    return value ? String(value).replace('T', ' ').split('.')[0] : '-'
  }
  const parts = [
    parsed.getFullYear(),
    String(parsed.getMonth() + 1).padStart(2, '0'),
    String(parsed.getDate()).padStart(2, '0'),
  ]
  const time = [
    String(parsed.getHours()).padStart(2, '0'),
    String(parsed.getMinutes()).padStart(2, '0'),
    String(parsed.getSeconds()).padStart(2, '0'),
  ]
  return `${parts.join('-')} ${time.join(':')}`
}

const toLogItems = (events = []) =>
  events.map((ev) => ({
    type: ev.level === 'error' ? 'warning' : ev.level,
    message: ev.message,
    details: ev.created_at,
    timestamp: parseBackendUtcDate(ev.created_at) || new Date(ev.created_at),
  }))

const mapStatusLabel = (status) => STATUS_LABELS[status] || status || '未知'

const formatDateTime = (value) => {
  return formatLocalDateTime(value)
}

const toLowerText = (value) => (value || '').toString().toLowerCase()

const applyLocalHistoryFilter = () => {
  const keyword = historyKeyword.value.trim().toLowerCase()
  const status = historyStatus.value
  const filtered = allHistoryJobs.value.filter((job) => {
    if (status && job.status !== status) {
      return false
    }
    if (!keyword) {
      return true
    }

    const fields = [
      job.id,
      job.target_scope,
      job.status,
      mapStatusLabel(job.status),
      job.step,
      job.message,
      job.error_message,
      job.created_by_username,
      job.created_at,
    ]
    return fields.some((field) => toLowerText(field).includes(keyword))
  })

  historyJobs.value = filtered
}

const syncSelectionAfterFilter = async () => {
  const jobs = historyJobs.value
  if (jobs.length === 0) {
    selectedHistoryJobId.value = ''
    detectionLogs.value = []
    detectionProgress.value.show = false
    return
  }

  const existed = jobs.find((job) => job.id === selectedHistoryJobId.value)
  if (existed) {
    return
  }

  const next = jobs[0]
  selectedHistoryJobId.value = next.id
  await selectHistoryJob(next.id)
}

const runHistoryFilter = async () => {
  applyLocalHistoryFilter()
  await syncSelectionAfterFilter()
}

const retrySelectedJob = async () => {
  const jobId = selectedHistoryJobId.value || currentJobId.value
  if (!jobId) {
    setTaskFeedback('当前没有可重试的任务详情，请先选择历史任务', 'error')
    return
  }
  pollingError.value = ''
  jobDetailError.value = ''
  const current = allHistoryJobs.value.find((job) => job.id === jobId)
  if (current && isActiveStatus(current.status)) {
    detecting.value = true
    startPollingJob(jobId)
    return
  }
  await selectHistoryJob(jobId)
}

onUnmounted(() => {
  stopPolling()
  if (historyFilterTimer) {
    clearTimeout(historyFilterTimer)
    historyFilterTimer = null
  }
})

const startDetection = () => {
  if (detecting.value) return

  const payload = {}
  clearTaskFeedback()
  let taskRegions = []

  if (detectionScope.value === 'selected') {
    const normalized = applySelectedRegionsLimit(selectedRegions.value)
    if (normalized.length === 0) {
      setTaskFeedback('请先选择至少一个探测区域', 'error')
      notify.warning('请先选择至少一个探测区域')
      return
    }
    if (normalized.length !== selectedRegions.value.length) {
      selectedRegions.value = normalized
      notify.warning(`最多选择 ${maxSelectableRegions.value} 个区域，已自动截取前 ${maxSelectableRegions.value} 个`)
    }
    payload.target_scope = 'selected'
    payload.target_regions = normalized
    payload.probe_regions = normalized
    payload.probe_region_list = normalized.join(';')
    taskRegions = normalized
  }

  detecting.value = true
  detectionProgress.value = {
    show: true,
    percentage: 0,
    current: 0,
    total: 100,
    eta: '',
    currentTask: detectionScope.value === 'selected' ? '正在创建定向探测任务...' : '正在创建全球探测任务...',
  }
  setCurrentTaskContext(null, {
    scope: detectionScope.value,
    regions: taskRegions,
    status: 'queued',
    message: detectionProgress.value.currentTask,
  })

  createDetectionJob(payload)
    .then((res) => {
      const jobId = res?.data?.job?.id
      if (!jobId) {
        throw new Error('未获取到任务 ID')
      }
      currentJobId.value = jobId
      selectedHistoryJobId.value = jobId
      jobDetailError.value = ''
      pollingError.value = ''
      setCurrentTaskContext(res?.data?.job, {
        jobId,
        scope: detectionScope.value,
        regions: taskRegions,
        status: res?.data?.job?.status || 'queued',
        message: detectionProgress.value.currentTask,
      })
      addDetectionLog('info', '开始探测任务', `任务 ID: ${jobId}`)
      setTaskFeedback(
        detectionScope.value === 'selected' ? '定向探测任务已提交，正在等待执行' : '全球探测任务已提交，正在等待执行',
        'success',
      )
      notify.info(detectionScope.value === 'selected' ? '已提交定向探测任务' : '已提交全球探测任务')
      reloadHistory()
      startPollingJob(jobId)
    })
    .catch((e) => {
      detecting.value = false
      detectionProgress.value.show = false
      clearCurrentTaskContext()
      setTaskFeedback(e?.message || '创建探测任务失败，请稍后重试', 'error')
      notify.error(e?.message || '创建探测任务失败')
    })
}

const stopDetection = async () => {
  if (!currentJobId.value || stoppingDetection.value) return
  const confirmed = await confirmAction({
    title: '停止探测任务',
    content: '确认停止当前探测任务吗？任务会保留历史记录，但不会继续执行。',
    okText: '停止任务',
    cancelText: '继续执行',
    danger: true,
  })
  if (!confirmed) return
  clearTaskFeedback()
  stoppingDetection.value = true
  cancelDetectionJob(currentJobId.value)
    .then(() => {
      addDetectionLog('warning', '取消请求已提交', `任务 ID: ${currentJobId.value}`)
      setTaskFeedback('已提交取消请求，请等待任务状态刷新', 'info')
      notify.warning('已提交取消请求')
    })
    .catch((e) => {
      setTaskFeedback(e?.message || '取消任务失败，请稍后重试', 'error')
      notify.error(e?.message || '取消任务失败')
    })
    .finally(() => {
      stoppingDetection.value = false
    })
}

const reloadHistory = async () => {
  historyLoading.value = true
  historyLoadError.value = ''
  try {
    const res = await listDetectionJobs({
      limit: 300,
    })
    allHistoryJobs.value = res?.data?.jobs || []
    await runHistoryFilter()
  } catch (e) {
    historyLoadError.value = e?.message || '加载探测历史失败，请稍后重试'
    notify.error(e?.message || '加载探测历史失败')
  } finally {
    historyLoading.value = false
  }
}

const loadDetectionRegions = async () => {
  if (loadingRegions.value) return
  loadingRegions.value = true
  regionLoadError.value = ''
  try {
    const res = await listDetectionRegions()
    regionOptions.value = res?.data?.regions || []
    const maxSelections = Number(res?.data?.maxSelections || 5)
    maxSelectableRegions.value = Number.isFinite(maxSelections) && maxSelections > 0 ? maxSelections : 5
  } catch (e) {
    regionLoadError.value = e?.message || '加载探测区域列表失败，请稍后重试'
    notify.error(e?.message || '加载探测区域列表失败')
  } finally {
    loadingRegions.value = false
  }
}

const selectHistoryJob = async (jobId) => {
  if (!jobId) return
  const selectEpoch = taskViewEpoch.value
  selectedHistoryJobId.value = jobId
  jobDetailError.value = ''
  pollingError.value = ''
  try {
    const detail = await getDetectionJob(jobId)
    if (selectEpoch !== taskViewEpoch.value) {
      return
    }
    const job = detail?.data?.job
    const events = detail?.data?.events || []
    setCurrentTaskContext(job)
    detectionLogs.value = toLogItems(events)
    detectionProgress.value = {
      show: true,
      percentage: Number(job?.progress || mapStatusToProgress(job?.status)),
      current: Number(job?.progress || mapStatusToProgress(job?.status)),
      total: 100,
      eta: '',
      currentTask: job?.message || job?.step || '任务详情',
    }
    if (isActiveStatus(job?.status)) {
      currentJobId.value = jobId
    }
    detecting.value = isActiveStatus(job?.status)
  } catch (e) {
    if (selectEpoch !== taskViewEpoch.value) {
      return
    }
    if (e?.status === 404) {
      allHistoryJobs.value = allHistoryJobs.value.filter((j) => j.id !== jobId)
      await runHistoryFilter()
      if (currentJobId.value === jobId) {
        resetTaskViewState()
      }
      notify.warning('任务不存在，已从历史列表移除')
      return
    }
    jobDetailError.value = e?.message || '加载任务详情失败，请稍后重试'
    notify.error(e?.message || '加载任务详情失败')
  }
}

const clearHistory = async () => {
  if (clearingHistory.value) return
  const confirmed = await confirmAction({
    title: '清空探测历史',
    content: '确认清空当前探测历史吗？该操作会移除历史记录，且不可恢复。',
    okText: '清空历史',
    cancelText: '取消',
    danger: true,
  })
  if (!confirmed) return
  clearingHistory.value = true
  clearTaskFeedback()
  try {
    stopPolling()
    const res = await clearDetectionHistory()
    const deletedJobs = res?.data?.deletedJobs || 0
    const deletedOrphanJobs = res?.data?.deletedOrphanJobs || 0
    resetTaskViewState()
    allHistoryJobs.value = []
    await reloadHistory()
    setTaskFeedback(`历史已清空，共删除 ${deletedJobs} 条任务记录`, 'success')
    notify.success(`历史已清空，共删除 ${deletedJobs} 条任务记录（含 ${deletedOrphanJobs} 条孤儿任务）`)
  } catch (e) {
    setTaskFeedback(e?.message || '清空历史失败，请稍后重试', 'error')
    notify.error(e?.message || '清空历史失败')
  } finally {
    clearingHistory.value = false
  }
}

const restoreLatestJob = async () => {
  try {
    await reloadHistory()
    const jobs = historyJobs.value
    if (jobs.length === 0) return

    const activeJob = jobs.find((j) => isActiveStatus(j.status))
    const latest = activeJob || jobs[0]
    if (!latest?.id) return

    currentJobId.value = latest.id
    if (isActiveStatus(latest.status)) {
      detecting.value = true
      setCurrentTaskContext(latest)
      startPollingJob(latest.id)
    } else {
      detecting.value = false
      setCurrentTaskContext(latest)
      detectionProgress.value = {
        show: true,
        percentage: Number(latest.progress || mapStatusToProgress(latest.status)),
        current: Number(latest.progress || mapStatusToProgress(latest.status)),
        total: 100,
        eta: '',
        currentTask: latest.message || latest.step || '任务已结束',
      }
      if (isTerminalStatus(latest.status)) {
        const detail = await getDetectionJob(latest.id)
        const events = detail?.data?.events || []
        detectionLogs.value = toLogItems(events)
      }
    }
  } catch {
    // 璁剧疆闈㈡澘鎵撳紑鏃剁殑鎭㈠澶辫触涓嶉樆鏂敤鎴锋墜鍔ㄥ惎鍔?
  }
}

const mapStatusToProgress = (status) => {
  const mapping = {
    queued: 5,
    dispatching: 15,
    running: 35,
    artifact_ready: 60,
    importing: 80,
    activated: 100,
    failed: 100,
    canceled: 100,
  }
  return mapping[status] ?? 0
}

const startPollingJob = (jobId) => {
  stopPolling()
  const pollingEpoch = bumpTaskViewEpoch()
  pollingErrorNotified = false
  pollingConsecutiveFailures = 0
  pollingError.value = ''
  const fetchAndUpdate = async () => {
    try {
      const res = await getDetectionJob(jobId)
      if (pollingEpoch !== taskViewEpoch.value) {
        return
      }
      const job = res?.data?.job
      const events = res?.data?.events || []
      if (!job) return
      pollingConsecutiveFailures = 0
      pollingErrorNotified = false
      pollingError.value = ''
      setCurrentTaskContext(job)

      detectionProgress.value = {
        show: true,
        percentage: Number(job.progress || mapStatusToProgress(job.status)),
        current: Number(job.progress || mapStatusToProgress(job.status)),
        total: 100,
        eta: '',
        currentTask: job.message || job.step || '任务执行中',
      }

      detectionLogs.value = events.map((ev) => ({
        type: ev.level === 'error' ? 'warning' : ev.level,
        message: ev.message,
        details: ev.created_at,
        timestamp: parseBackendUtcDate(ev.created_at) || new Date(ev.created_at),
      }))

      const selectedId = selectedHistoryJobId.value || currentJobId.value
      if (!selectedId || selectedId === jobId) {
        selectedHistoryJobId.value = jobId
      }

      if (['activated', 'failed', 'canceled'].includes(job.status)) {
        detecting.value = false
        stopPolling()
        if (job.status === 'activated') {
          const activatedSnapshotKey = typeof job?.snapshot_key === 'string' ? job.snapshot_key : null
          if (typeof setSnapshot === 'function') {
            // 鍥哄畾鍒版湰娆′换鍔″鍏ョ殑蹇収锛岄伩鍏嶄緷璧栧悗绔粯璁ゆ寚閽堝鑷村埛鏂板悗涓㈠け銆?
            setSnapshot(activatedSnapshotKey)
          }
          globalThis.dispatchEvent(new CustomEvent('snapshots:changed', { detail: { snapshotKey: activatedSnapshotKey } }))
          notify.success(
            activatedSnapshotKey
              ? `探测任务完成，已切换到快照 ${activatedSnapshotKey}`
              : '探测任务完成，已刷新为最新快照'
          )
        } else if (job.status === 'failed') {
          setTaskFeedback(job.error_message || '探测任务失败，请查看任务日志', 'error')
          notify.error(job.error_message || '探测任务失败')
        } else {
          setTaskFeedback('探测任务已取消', 'info')
          notify.warning('探测任务已取消')
        }
        reloadHistory()
      }
    } catch (e) {
      if (pollingEpoch !== taskViewEpoch.value) {
        return
      }
      if (e?.status === 404) {
        stopPolling()
        if (currentJobId.value === jobId || selectedHistoryJobId.value === jobId) {
          resetTaskViewState()
        }
        allHistoryJobs.value = allHistoryJobs.value.filter((j) => j.id !== jobId)
        await runHistoryFilter()
        pollingError.value = '任务不存在，已停止自动轮询并刷新历史任务列表'
        notify.warning('任务不存在，已停止轮询并刷新历史')
        return
      }

      pollingConsecutiveFailures += 1
      pollingError.value = e?.message || '获取任务状态失败，正在自动重试'
      if (!pollingErrorNotified) {
        notify.error(e?.message || '获取任务状态失败，将自动重试')
        pollingErrorNotified = true
      }
      if (pollingConsecutiveFailures >= 10) {
        stopPolling()
        detecting.value = false
        pollingError.value = '连续多次获取任务状态失败，已停止自动重试，请手动重试'
      }
    }
  }

  fetchAndUpdate()
  pollingTimer = setInterval(fetchAndUpdate, 3000)
}

const addDetectionLog = (type, message, details = '') => {
  detectionLogs.value.unshift({
    type,
    message,
    details,
    timestamp: new Date(),
  })
  if (detectionLogs.value.length > 80) {
    detectionLogs.value = detectionLogs.value.slice(0, 80)
  }
}

const formatLogTime = (ts) => {
  if (!(ts instanceof Date) || Number.isNaN(ts.getTime())) {
    return '--:--:--'
  }
  return ts.toLocaleTimeString()
}

watch(
  () => [historyKeyword.value, historyStatus.value],
  () => {
    if (historyFilterTimer) {
      clearTimeout(historyFilterTimer)
    }
    historyFilterTimer = setTimeout(() => {
      runHistoryFilter()
    }, 200)
  },
)

watch(
  () => selectedRegions.value,
  (regions) => {
    if (detectionScope.value !== 'selected') return
    const limited = applySelectedRegionsLimit(regions)
    if (limited.length !== regions.length) {
      selectedRegions.value = limited
      notify.warning(`最多可选择 ${maxSelectableRegions.value} 个区域`)
    }
  },
  { deep: true },
)

watch(
  () => detectionScope.value,
  (scope) => {
    if (scope === 'global') {
      selectedRegions.value = []
    }
  },
)

watch(
  () => props.visible,
  async (v) => {
    if (v) {
      clearTaskFeedback()
      regionLoadError.value = ''
      historyLoadError.value = ''
      jobDetailError.value = ''
      pollingError.value = ''
      await loadDetectionRegions()
      restoreLatestJob()
    } else {
      clearTaskFeedback()
      regionLoadError.value = ''
      historyLoadError.value = ''
      jobDetailError.value = ''
      pollingError.value = ''
    }
  },
  { immediate: true },
)
</script>

<style scoped>
/* Base Overlay & Panel - Glassmorphism Support */
.panel-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.2s ease-out;
}

.panel-content {
  width: 680px;
  max-width: 90vw;
  height: 720px;
  max-height: 90vh;
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(24px) saturate(150%);
  -webkit-backdrop-filter: blur(24px) saturate(150%);
  border-radius: 20px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1), 0 1px 3px rgba(0,0,0,0.05);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(255, 255, 255, 0.5);
  transform-origin: center;
  animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  color: #1e293b;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

@media (prefers-color-scheme: dark) {
  .panel-overlay {
    background: rgba(0, 0, 0, 0.4);
  }
  .panel-content {
    background: rgba(30, 41, 59, 0.75);
    border-color: rgba(255, 255, 255, 0.1);
    color: #f8fafc;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3), 0 1px 3px rgba(0,0,0,0.2);
  }
}

/* Header */
.panel-header {
  padding: 20px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}
@media (prefers-color-scheme: dark) {
  .panel-header {
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }
}

.panel-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.close-btn {
  background: rgba(0, 0, 0, 0.04);
  border: none;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 20px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: inherit;
  transition: all 0.2s;
}
.close-btn:hover {
  background: rgba(0, 0, 0, 0.08);
  transform: scale(1.05);
}
@media (prefers-color-scheme: dark) {
  .close-btn {
    background: rgba(255, 255, 255, 0.1);
  }
  .close-btn:hover {
    background: rgba(255, 255, 255, 0.15);
  }
}

/* Body & Sections */
.panel-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}

.panel-section {
  background: rgba(0, 0, 0, 0.02);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 20px;
  border: 1px solid rgba(0, 0, 0, 0.04);
}
@media (prefers-color-scheme: dark) {
  .panel-section {
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.05);
  }
}

.panel-section h4 {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 600;
  color: #3b82f6;
}
@media (prefers-color-scheme: dark) {
  .panel-section h4 { color: #60a5fa; }
}

.panel-section p {
  margin: 0 0 16px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}
@media (prefers-color-scheme: dark) {
  .panel-section p { color: #94a3b8; }
}

/* Forms & Buttons */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
}
.form-group label {
  font-size: 13px;
  font-weight: 500;
  color: #475569;
}
@media (prefers-color-scheme: dark) {
  .form-group label { color: #cbd5e1; }
}
.form-group input,
.form-group select {
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid rgba(0,0,0,0.1);
  background: #fff;
  font-size: 14px;
  color: inherit;
}
.form-group input:disabled,
.form-group select:disabled {
  background: rgba(0,0,0,0.02);
  color: #94a3b8;
}
@media (prefers-color-scheme: dark) {
  .form-group input,
  .form-group select {
    background: rgba(0,0,0,0.3);
    border-color: rgba(255,255,255,0.1);
    color: #e2e8f0;
  }
  .form-group input:disabled,
  .form-group select:disabled {
    background: rgba(0,0,0,0.1);
  }
}

.region-select {
  min-height: 180px;
}

.region-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #64748b;
}
@media (prefers-color-scheme: dark) {
  .region-meta {
    color: #94a3b8;
  }
}

.form-actions {
  display: flex;
  gap: 12px;
}

button {
  font-family: inherit;
  font-size: 14px;
}

.detection-btn,
.stop-btn,
.clear-btn {
  border: none;
  border-radius: 8px;
  padding: 10px 16px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.detection-btn {
  background: #000;
  color: #fff;
}
.detection-btn:hover {
  background: #333;
}
@media (prefers-color-scheme: dark) {
  .detection-btn {
    background: #fff;
    color: #000;
  }
  .detection-btn:hover {
    background: #e2e8f0;
  }
}

.stop-btn {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}
.stop-btn:hover {
  background: rgba(239, 68, 68, 0.2);
}

.clear-btn {
  background: rgba(0,0,0,0.04);
  color: #475569;
}
.clear-btn:hover {
  background: rgba(0,0,0,0.08);
}
@media (prefers-color-scheme: dark) {
  .clear-btn {
    background: rgba(255,255,255,0.05);
    color: #cbd5e1;
  }
  .clear-btn:hover {
    background: rgba(255,255,255,0.1);
  }
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

/* Progress Section */
.detection-progress {
  padding: 16px;
  border-radius: 12px;
  background: rgba(59, 130, 246, 0.05);
  border: 1px solid rgba(59, 130, 246, 0.1);
  margin-bottom: 20px;
}

.detection-progress h5,
.detection-logs h5 {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
}

.progress-bar-container {
  height: 8px;
  border-radius: 4px;
  background: rgba(0,0,0,0.05);
  overflow: hidden;
}
@media (prefers-color-scheme: dark) {
  .progress-bar-container { background: rgba(255,255,255,0.1); }
}

.progress-bar {
  height: 100%;
  background: #3b82f6;
  transition: width 0.3s ease;
  min-width: 2%;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
}

.current-task {
  margin-top: 8px;
  font-size: 12px;
  color: #475569;
  font-family: ui-monospace, SFMono-Regular, monospace;
}
@media (prefers-color-scheme: dark) {
  .progress-info { color: #94a3b8; }
  .current-task { color: #cbd5e1; }
}

/* History Toolbar & List */
.history-toolbar {
  display: grid;
  grid-template-columns: 1fr 140px auto;
  gap: 8px;
  margin-bottom: 12px;
}
.history-toolbar input,
.history-toolbar select {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(0,0,0,0.1);
  background: #fff;
  font-size: 13px;
  color: inherit;
}
@media (prefers-color-scheme: dark) {
  .history-toolbar input,
  .history-toolbar select {
    background: rgba(0,0,0,0.2);
    border-color: rgba(255,255,255,0.1);
    color: #e2e8f0;
  }
}

.history-list {
  background: rgba(0,0,0,0.02);
  border: 1px solid rgba(0,0,0,0.04);
  border-radius: 8px;
  max-height: 160px;
  overflow-y: auto;
  margin-bottom: 16px;
}
@media (prefers-color-scheme: dark) {
  .history-list {
    background: rgba(0,0,0,0.2);
    border-color: rgba(255,255,255,0.05);
  }
}

.history-item {
  display: grid;
  grid-template-columns: 80px 100px 1fr;
  gap: 12px;
  padding: 10px 12px;
  background: transparent;
  border: none;
  border-bottom: 1px solid rgba(0,0,0,0.04);
  text-align: left;
  cursor: pointer;
  color: inherit;
  transition: background 0.2s;
  font-size: 13px;
}
.history-item:last-child {
  border-bottom: none;
}
.history-item:hover {
  background: rgba(0,0,0,0.03);
}
.history-item.active {
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
}
@media (prefers-color-scheme: dark) {
  .history-item { border-bottom-color: rgba(255,255,255,0.05); }
  .history-item:hover { background: rgba(255,255,255,0.05); }
  .history-item.active {
    background: rgba(96, 165, 250, 0.15);
    color: #60a5fa;
  }
}

.history-job-id {
  font-family: ui-monospace, SFMono-Regular, monospace;
  color: #64748b;
}

/* Logs */
.logs-container {
  max-height: 240px;
  overflow-y: auto;
  border-radius: 8px;
  background: #1e293b;
  padding: 12px;
}
@media (prefers-color-scheme: dark) {
  .logs-container {
    background: #0f172a;
  }
}

.no-logs {
  font-size: 13px;
  color: #94a3b8;
  padding: 12px;
  text-align: center;
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.log-item {
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 12px;
  line-height: 1.4;
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
}
.log-item.info .log-message { color: #38bdf8; }
.log-item.warning .log-message { color: #fbbf24; }
.log-item.success .log-message { color: #a3e635; }
.log-item.error .log-message { color: #f87171; }

.log-time {
  font-size: 10px;
  color: #64748b;
  margin-bottom: 2px;
}
.log-details {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
  padding-left: 8px;
  border-left: 1px solid rgba(255,255,255,0.1);
}

/* Animations & Scrollbar */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes slideUp {
  from { opacity: 0; transform: translateY(10px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(0,0,0,0.1);
  border-radius: 3px;
}
@media (prefers-color-scheme: dark) {
  ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); }
}

@media (max-width: 768px) {
  .panel-content {
    width: 100vw;
    height: 100vh;
    max-width: none;
    max-height: none;
    border-radius: 0;
    border: none;
  }
  .history-toolbar {
    grid-template-columns: 1fr;
  }
  .region-toolbar {
    grid-template-columns: 1fr;
  }
}
</style>

<style scoped>
.panel-header-shell {
  padding: var(--ds-space-4);
  border-bottom: 1px solid var(--ds-border-soft);
  background: linear-gradient(180deg, rgba(248, 251, 255, 0.96), rgba(244, 247, 251, 0.92));
}

.panel-page-header {
  padding: var(--ds-space-5);
  border-radius: var(--ds-radius-xl);
}

.panel-body {
  padding: var(--ds-space-6);
  background: linear-gradient(180deg, rgba(244, 247, 251, 0.9), rgba(248, 251, 255, 0.82));
}

.task-workbench-panel {
  gap: var(--ds-space-6);
  padding: var(--ds-panel-padding);
  border-color: var(--ds-card-border);
  border-radius: var(--ds-radius-xl);
  background: rgba(255, 255, 255, 0.82);
  box-shadow: var(--ds-shadow-sm);
}

.panel-section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ds-space-4);
}

.panel-section-eyebrow {
  margin: 0 0 var(--ds-space-2);
  color: var(--ds-primary-500);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.panel-section-title {
  margin: 0;
  color: var(--ds-text-strong);
  font-size: 20px;
  font-weight: 700;
}

.panel-section-description {
  margin: var(--ds-space-2) 0 0;
  max-width: 720px;
  color: var(--ds-text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.form-group {
  gap: var(--ds-space-2);
  margin-bottom: var(--ds-space-5);
}

.form-group label {
  color: var(--ds-text-primary);
  font-size: 13px;
  font-weight: 700;
}

.form-group input,
.form-group select,
.region-toolbar-shell :deep(input),
.history-toolbar-shell :deep(input),
.history-toolbar-shell :deep(select) {
  min-height: 44px;
  border-radius: 14px;
  border-color: var(--ds-border-strong);
  background: rgba(255, 255, 255, 0.92);
}

.form-group-help-block,
.history-state-block,
.logs-empty-state {
  margin-top: var(--ds-space-3);
}

.region-toolbar-shell,
.history-toolbar-shell {
  margin-bottom: var(--ds-space-3);
}

.region-clear-btn,
.clear-btn,
.feedback-btn,
.detection-btn,
.stop-btn {
  min-height: 42px;
}

.feedback-btn-quiet {
  background: rgba(255, 255, 255, 0.45);
}

.task-summary-card,
.draft-region-summary,
.detection-progress {
  border-radius: var(--ds-radius-lg);
  border-color: var(--ds-border-soft);
  box-shadow: none;
}

.history-list,
.region-checklist {
  border-radius: var(--ds-radius-lg);
  border-color: var(--ds-border-soft);
  background: rgba(248, 251, 255, 0.86);
}

.logs-container {
  border-radius: var(--ds-radius-lg);
}

.close-btn.ds-icon-btn {
  width: 44px;
  height: 44px;
  font-size: 22px;
}

@media (max-width: 768px) {
  .panel-page-header,
  .panel-body {
    padding: var(--ds-space-4);
  }
}
</style>

<style scoped>
.panel-overlay {
  background: rgba(15, 23, 42, 0.22);
  backdrop-filter: blur(6px);
}

.panel-content {
  background: #f7f9fc;
  border: 1px solid #e5e7eb;
  box-shadow: 0 20px 42px rgba(15, 23, 42, 0.12);
  color: #111827;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.panel-header {
  background: linear-gradient(180deg, #f3f6fb 0%, #edf2f8 100%);
}

.panel-header h3,
.panel-section h4 {
  color: #1a1a1a;
}

.panel-section {
  background: #fbfcfe;
  border: 1px solid #e5e7eb;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
}

.panel-section p,
.form-group label,
.progress-info,
.current-task {
  color: #374151;
}

.feedback-btn {
  border-radius: 10px;
  border: 1px solid #bfdbfe;
  background: #ffffff;
  color: #1d4ed8;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}

.feedback-btn:hover:not(:disabled) {
  background: #dbeafe;
}

.feedback-btn-quiet {
  background: transparent;
}

.form-group-help {
  margin-bottom: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  font-size: 12px;
  line-height: 1.55;
}

.form-group input,
.form-group select,
.region-toolbar input,
.history-toolbar input,
.history-toolbar select {
  background: #fdfdff;
  color: #111827;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  transition: all 0.3s ease;
}

.form-group input:disabled,
.form-group select:disabled {
  background: #f3f4f6;
  color: #374151;
  border-color: #d1d5db;
}

.history-toolbar input::placeholder {
  color: #9ca3af;
}

.form-group input:focus,
.form-group select:focus,
.region-toolbar input:focus,
.history-toolbar input:focus,
.history-toolbar select:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.region-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #6b7280;
  gap: 12px;
  flex-wrap: wrap;
}

.draft-region-summary,
.task-summary-card {
  margin-top: 12px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid #dbeafe;
  background: linear-gradient(180deg, #f8fbff 0%, #eff6ff 100%);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.8);
}

.draft-region-summary-header,
.task-summary-header,
.task-summary-title-row,
.task-summary-grid,
.task-region-tags {
  display: flex;
}

.draft-region-summary-header,
.task-summary-header {
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.draft-region-summary-header {
  margin-bottom: 10px;
  font-size: 12px;
  color: #475569;
}

.task-summary-header {
  align-items: flex-start;
}

.task-summary-heading {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-summary-eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #64748b;
}

.task-summary-title-row {
  gap: 8px;
  flex-wrap: wrap;
}

.task-status-pill,
.task-scope-pill {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.task-status-pill-info {
  background: #dbeafe;
  color: #1d4ed8;
}

.task-status-pill-success {
  background: #dcfce7;
  color: #15803d;
}

.task-status-pill-warning {
  background: #fef3c7;
  color: #b45309;
}

.task-status-pill-error {
  background: #fee2e2;
  color: #b91c1c;
}

.task-status-pill-muted,
.task-scope-pill {
  background: #e5e7eb;
  color: #374151;
}

.task-summary-grid {
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.task-summary-item {
  min-width: 120px;
  flex: 1 1 140px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(191, 219, 254, 0.9);
  min-width: 0;
}

.task-summary-item span {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
}

.task-summary-item strong {
  font-size: 13px;
  color: #111827;
  overflow-wrap: anywhere;
}

.task-summary-range {
  margin-top: 14px;
}

.task-summary-range-label {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 700;
  color: #1f2937;
}

.task-summary-note {
  font-size: 13px;
  line-height: 1.6;
  color: #334155;
}

.task-summary-note-warning {
  color: #b45309;
}

.task-region-tags {
  gap: 8px;
  flex-wrap: wrap;
}

.task-region-tag {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #bfdbfe;
  color: #1e3a8a;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.task-region-tag strong {
  color: #1d4ed8;
}

.region-toolbar {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  margin-bottom: 8px;
}

.region-clear-btn {
  border-radius: 10px;
  border: 1px solid #d1d5db;
  background: #f3f4f6;
  color: #374151;
  padding: 0 12px;
  font-size: 13px;
  font-weight: 500;
}

.region-clear-btn:hover:not(:disabled) {
  background: #e5e7eb;
}

.region-checklist {
  max-height: 250px;
  overflow-y: auto;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  background: #fdfdff;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.region-checklist.disabled {
  opacity: 0.75;
}

.region-option {
  width: 100%;
  border: 1px solid transparent;
  border-radius: 8px;
  background: #ffffff;
  color: #111827;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  text-align: left;
}

.region-option:hover:not(:disabled) {
  background: #eff6ff;
  border-color: #bfdbfe;
  transform: none;
}

.region-option.selected {
  background: #eaf2ff;
  border-color: #93c5fd;
}

.region-checkbox {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  border: 1.5px solid #93a3b8;
  background: #ffffff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.region-checkbox.checked {
  background: #2563eb;
  border-color: #2563eb;
}

.region-checkmark {
  color: #ffffff;
  font-size: 12px;
  line-height: 1;
  opacity: 0;
  transform: scale(0.8);
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.region-checkbox.checked .region-checkmark {
  opacity: 1;
  transform: scale(1);
}

.region-labels {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.region-primary {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.region-secondary {
  font-size: 12px;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.region-empty {
  padding: 16px 10px;
  text-align: center;
  font-size: 12px;
  color: #6b7280;
}

.detection-btn,
.stop-btn,
.clear-btn {
  border-radius: 10px;
  transition: all 0.3s ease;
}

.detection-btn {
  background: #2563eb;
  color: #ffffff;
}

.detection-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.stop-btn {
  background: #ef4444;
  color: #ffffff;
}

.stop-btn:hover:not(:disabled) {
  background: #dc2626;
}

.clear-btn {
  background: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
}

.clear-btn:hover:not(:disabled) {
  background: #e5e7eb;
}

.detection-btn:hover,
.stop-btn:hover,
.clear-btn:hover {
  transform: translateY(-2px);
}

.history-list {
  background: #f3f6fb;
  border: 1px solid #e5e7eb;
}

.history-item {
  color: #374151;
}

.history-job-scope {
  grid-column: 1 / -1;
  font-size: 11px;
  color: #64748b;
  overflow-wrap: anywhere;
}

.history-item:hover {
  background: #eff6ff;
}

.history-item.active {
  background: #dbeafe;
  color: #1d4ed8;
}

.logs-container {
  background: #0b1735;
  border-radius: 10px;
  box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.24);
}

.no-logs {
  color: #6b7280;
}

.logs-empty-state {
  margin: 0;
}

@media (max-width: 768px) {
  .task-summary-header,
  .draft-region-summary-header {
    flex-direction: column;
    align-items: stretch;
  }

  .task-summary-grid {
    flex-direction: column;
  }
}
</style>
