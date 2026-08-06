<template>
  <PanelCard as="aside" class="satellite-panel ds-sidebar-shell">
    <template #header>
      <div class="satellite-panel-head">
        <div class="satellite-panel-copy">
          <div class="satellite-panel-title-row">
            <h2 class="satellite-panel-title">Starlink 卫星</h2>
            <span class="ds-status-pill ds-badge-info">TLE 实时推算</span>
          </div>
          <p class="satellite-panel-subtitle">按名称、NORAD 和轨道高度筛选当前可见卫星。</p>
        </div>
        <div class="satellite-panel-actions">
          <button
            type="button"
            class="ds-btn-primary satellite-action-btn"
            :disabled="loading"
            title="刷新卫星列表"
            aria-label="刷新卫星列表"
            @click="refresh"
          >
            {{ loading ? '刷新中...' : '刷新' }}
          </button>
          <button
            type="button"
            class="ds-icon-btn satellite-close-btn"
            title="关闭卫星面板"
            aria-label="关闭卫星面板"
            @click="closePanel"
          >
            ×
          </button>
        </div>
      </div>
    </template>

    <div class="satellite-filter-bar ds-filter-bar">
      <label class="ds-field satellite-field">
        <span class="ds-field-label">名称 / NORAD</span>
        <input
          id="starlink-keyword-filter"
          v-model="localFilters.keyword"
          name="starlink_keyword"
          type="text"
          autocomplete="off"
          placeholder="支持名称或 NORAD 搜索"
        />
      </label>
      <label class="ds-field satellite-field">
        <span class="ds-field-label">最小高度 (km)</span>
        <input
          id="starlink-min-height-filter"
          v-model="localFilters.minHeight"
          name="starlink_min_height"
          type="number"
          autocomplete="off"
          placeholder="例如 450"
        />
      </label>
      <label class="ds-field satellite-field">
        <span class="ds-field-label">最大高度 (km)</span>
        <input
          id="starlink-max-height-filter"
          v-model="localFilters.maxHeight"
          name="starlink_max_height"
          type="number"
          autocomplete="off"
          placeholder="例如 650"
        />
      </label>
    </div>

    <div class="satellite-summary ds-surface-card">
      <div class="satellite-summary-item">
        <strong>{{ satellites.length }}</strong>
        <span>可见卫星</span>
      </div>
      <div v-if="renderedSatellites.length < satellites.length" class="satellite-summary-item">
        <strong>{{ renderedSatellites.length }}</strong>
        <span>当前已展示</span>
      </div>
      <div v-if="detailLoading" class="satellite-summary-item">
        <strong>处理中</strong>
        <span>详情加载中</span>
      </div>
    </div>

    <StateBlock
      v-if="networkBlockNotice"
      type="error"
      title="卫星数据受限"
      :description="networkBlockNotice"
    />

    <StateBlock
      v-else-if="degradedNotice"
      type="info"
      title="使用降级数据"
      :description="degradedNotice"
    />

    <StateBlock
      v-if="!satellites.length"
      type="empty"
      title="没有匹配的卫星"
      description="调整名称或高度范围后再试。"
    />

    <div v-else class="satellite-list">
      <button
        v-for="sat in renderedSatellites"
        :key="sat.id"
        type="button"
        class="satellite-item ds-surface-card"
        :class="{ active: sat.id === selectedId }"
        :aria-pressed="sat.id === selectedId"
        @click="selectSatellite(sat.id, true)"
      >
        <div class="satellite-item-head">
          <span class="satellite-name">{{ sat.name }}</span>
          <span class="ds-status-pill" :class="hasPosition(sat) ? 'ds-badge-info' : 'ds-badge-warning'">
            {{ hasPosition(sat) ? '可定位' : '轨道数据' }}
          </span>
        </div>
        <div class="satellite-meta">
          <span>NORAD {{ sat.norad_cat_id || '-' }}</span>
          <span>{{ formatCoord(sat.latitude) }}, {{ formatCoord(sat.longitude) }}</span>
        </div>
        <div class="satellite-meta satellite-meta-secondary">
          <span>{{ hasPosition(sat) ? '可直接定位到地图' : '位置缺失，仅展示轨道信息' }}</span>
        </div>
      </button>
    </div>

    <div v-if="satellites.length" class="list-pagination ds-page-toolbar">
      <div class="pagination-info">显示 {{ renderedSatellites.length }} / {{ satellites.length }} 条</div>
      <button v-if="hasMoreSatellites" type="button" class="ds-btn-secondary satellite-more-btn" @click="loadMoreSatellites">
        加载更多
      </button>
    </div>
  </PanelCard>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import PanelCard from './ui/PanelCard.vue'
import StateBlock from './ui/StateBlock.vue'

const PAGE_SIZE = 100

const props = defineProps({
  satellites: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  detailLoading: {
    type: Boolean,
    default: false,
  },
  selectedId: {
    type: String,
    default: '',
  },
  filters: {
    type: Object,
    default: () => ({ keyword: '', minHeight: '', maxHeight: '' }),
  },
  networkBlockNotice: {
    type: String,
    default: '',
  },
  degradedNotice: {
    type: String,
    default: '',
  },
})

const emit = defineEmits([
  'refresh',
  'close',
  'filters-change',
  'select-satellite',
])

const localFilters = reactive({
  keyword: '',
  minHeight: '',
  maxHeight: '',
})

const visibleCount = ref(PAGE_SIZE)

const renderedSatellites = computed(() => props.satellites.slice(0, visibleCount.value))
const hasMoreSatellites = computed(() => renderedSatellites.value.length < props.satellites.length)

const resetVisibleCount = () => {
  visibleCount.value = Math.min(PAGE_SIZE, props.satellites.length || PAGE_SIZE)
}

watch(
  () => props.filters,
  (next) => {
    localFilters.keyword = next?.keyword || ''
    localFilters.minHeight = next?.minHeight || ''
    localFilters.maxHeight = next?.maxHeight || ''
  },
  { immediate: true, deep: true },
)

watch(
  () => [localFilters.keyword, localFilters.minHeight, localFilters.maxHeight],
  () => {
    resetVisibleCount()
    emit('filters-change', {
      keyword: localFilters.keyword,
      minHeight: localFilters.minHeight,
      maxHeight: localFilters.maxHeight,
    })
  },
)

watch(
  () => props.satellites,
  (items) => {
    // 数据每 5s 重建，仅在可见数量超出新数据长度时收敛，避免重置用户"加载更多"的进度
    if (visibleCount.value > items.length) {
      visibleCount.value = Math.max(PAGE_SIZE, items.length)
    }
  },
)

const refresh = () => emit('refresh')
const closePanel = () => emit('close')
const loadMoreSatellites = () => {
  visibleCount.value = Math.min(props.satellites.length, visibleCount.value + PAGE_SIZE)
}

const selectSatellite = (satelliteId, fromPanel = false) => {
  emit('select-satellite', { satelliteId, fromPanel })
}

const formatCoord = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return Number(value).toFixed(2)
}

const hasPosition = (satellite) => {
  if (!satellite) return false
  const lat = Number(satellite.latitude)
  const lng = Number(satellite.longitude)
  return Number.isFinite(lat) && Number.isFinite(lng)
}
</script>

<style scoped>
.satellite-panel {
  position: absolute;
  top: 20px;
  left: 20px;
  width: 340px;
  height: calc(100vh - 40px);
  max-height: calc(100vh - 40px);
  z-index: 210;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding: 16px;
  gap: 14px;
  background: rgba(255, 255, 255, 0.9);
}

.satellite-panel :deep(.panel-card__header) {
  gap: 0;
}

.satellite-panel :deep(.panel-card__body) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.satellite-panel :deep(.panel-card__header + .panel-card__body) {
  margin-top: 0;
}

.satellite-panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.satellite-panel-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.satellite-panel-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.satellite-panel-title {
  margin: 0;
  color: #0f172a;
  font-size: 20px;
  font-weight: 700;
}

.satellite-panel-subtitle {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.satellite-panel-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.satellite-action-btn {
  min-height: 38px;
  font-size: 13px;
}

.satellite-close-btn {
  width: 38px;
  height: 38px;
  font-size: 16px;
}

.satellite-filter-bar {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 12px;
  padding: 12px;
}

.satellite-field:first-child {
  grid-column: 1 / -1;
}

.satellite-field input {
  width: 100%;
  min-height: 40px;
  padding: 0 12px;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(255, 255, 255, 0.9);
  color: #0f172a;
  font-size: 13px;
  transition: all var(--ds-duration-base) var(--ds-ease-standard);
}

.satellite-field input:focus {
  outline: none;
  border-color: rgba(37, 99, 235, 0.35);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.1);
}

.satellite-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(92px, 1fr));
  gap: 12px;
  padding: 12px 14px;
}

.satellite-summary-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.satellite-summary-item strong {
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
}

.satellite-summary-item span {
  color: #64748b;
  font-size: 11px;
}

.satellite-list {
  flex: 1;
  min-height: 0;
  overflow-y: scroll;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.7) rgba(255, 255, 255, 0.28);
  padding-right: 4px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.satellite-list::-webkit-scrollbar {
  width: 8px;
}

.satellite-list::-webkit-scrollbar-track {
  background: rgba(241, 245, 249, 0.55);
  border-radius: 999px;
}

.satellite-list::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.72);
  border-radius: 999px;
}

.satellite-list::-webkit-scrollbar-thumb:hover {
  background: rgba(100, 116, 139, 0.9);
}

.satellite-item {
  width: 100%;
  padding: 12px 14px;
  text-align: left;
  gap: 8px;
  transition: all var(--ds-duration-base) var(--ds-ease-standard);
}

.satellite-item:hover {
  transform: translateY(-1px);
  border-color: rgba(37, 99, 235, 0.22);
  box-shadow: 0 16px 28px rgba(15, 23, 42, 0.08);
}

.satellite-item.active {
  border-color: rgba(37, 99, 235, 0.3);
  background: linear-gradient(135deg, rgba(219, 234, 254, 0.72), rgba(255, 255, 255, 0.92));
}

.satellite-item-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.satellite-name {
  color: #0f172a;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.4;
}

.satellite-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.satellite-meta-secondary {
  color: #475569;
}

.list-pagination {
  padding: 10px 14px;
}

.pagination-info {
  color: #64748b;
  font-size: 12px;
}

.satellite-more-btn {
  min-height: 40px;
  font-size: 13px;
}

@media (max-width: 768px) {
  .satellite-panel {
    width: calc(100vw - 24px);
    left: 12px;
    right: 12px;
    top: 12px;
    height: calc(100vh - 24px);
    max-height: calc(100vh - 24px);
    padding: 14px;
  }

  .satellite-panel-head {
    flex-direction: column;
  }

  .satellite-panel-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .satellite-summary {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 430px) {
  .satellite-filter-bar {
    grid-template-columns: 1fr;
  }
}
</style>
