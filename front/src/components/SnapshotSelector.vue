<template>
  <div
    ref="rootRef"
    class="snapshot-btn-wrap"
    :class="{ 'snapshot-btn-wrap-triggerless': hideTrigger }"
  >
    <button
      v-if="!hideTrigger"
      type="button"
      class="snapshot-trigger-btn ds-icon-btn ds-floating-panel"
      :class="{ 'has-snapshot': activeSnapshot !== null }"
      :title="triggerTitle"
      :aria-label="triggerTitle"
      :aria-expanded="isOpen"
      aria-haspopup="true"
      @click="toggleDropdown"
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="3" y="4" width="18" height="18" rx="2" stroke="currentColor" stroke-width="2" fill="none" />
        <path d="M16 2V6M8 2V6M3 10H21" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
      </svg>
      <span v-if="activeSnapshot !== null" class="snapshot-dot"></span>
    </button>

    <transition name="slide-left">
      <div v-if="isOpen" class="snapshot-dropdown ds-floating-panel ds-glass-card">
        <div class="snapshot-dropdown-header">
          <div class="snapshot-dropdown-copy">
            <div class="snapshot-dropdown-title">数据快照</div>
            <div class="snapshot-dropdown-subtitle">{{ dropdownSubtitle }}</div>
          </div>
          <span class="ds-badge-info">已保存 {{ snapshots.length }}</span>
        </div>

        <StateBlock
          v-if="isLoading"
          type="loading"
          title="加载快照中"
          description="正在获取可用快照列表。"
        />

        <StateBlock
          v-else-if="snapshots.length === 0"
          type="empty"
          title="暂无可用快照"
          description="当前还没有保存的历史快照。"
        />

        <template v-else>
          <div class="snapshot-list">
            <div v-for="snap in snapshots" :key="snap.key" class="snapshot-entry">
              <button
                type="button"
                class="snapshot-item"
                :class="{ selected: isSnapshotChecked(snap) }"
                :aria-label="`选择快照 ${snap.date}`"
                :aria-pressed="isSnapshotChecked(snap)"
                @click="selectSnapshot(snap.key)"
              >
                <div class="snapshot-item-copy">
                  <span class="snap-date">{{ snap.date }}</span>
                  <span class="snap-meta">
                    {{ snap.isCurrent ? '当前默认快照' : '历史快照' }}
                  </span>
                </div>

                <div class="snapshot-item-actions">
                  <span
                    v-if="isSnapshotChecked(snap)"
                    class="ds-status-pill ds-badge-info"
                  >
                    使用中
                  </span>
                  <button
                    v-if="!snap.isCurrent"
                    type="button"
                    class="snap-delete-btn ds-btn-ghost"
                    :disabled="deletingKey === snap.key"
                    :title="`删除快照 ${snap.date}`"
                    :aria-label="`删除快照 ${snap.date}`"
                    @click.stop="requestDeleteSnapshot(snap)"
                  >
                    {{ deletingKey === snap.key ? '处理中...' : '删除' }}
                  </button>
                </div>
              </button>

              <div v-if="pendingDeleteKey === snap.key" class="snapshot-confirm ds-state-block ds-state-error">
                <div class="ds-state-block__body">
                  <h3 class="ds-state-block__title">确认删除 {{ snap.date }}？</h3>
                  <p class="ds-state-block__description">删除后不可恢复，请确认当前不再需要该快照。</p>
                </div>
                <div class="snapshot-confirm-actions">
                  <button
                    type="button"
                    class="ds-btn-danger snap-confirm-btn"
                    :disabled="deletingKey === snap.key"
                    @click="confirmDeleteSnapshot(snap)"
                  >
                    {{ deletingKey === snap.key ? '删除中...' : '确认删除' }}
                  </button>
                  <button
                    type="button"
                    class="ds-btn-secondary snap-confirm-btn"
                    :disabled="deletingKey === snap.key"
                    @click="cancelDeleteSnapshot"
                  >
                    取消
                  </button>
                </div>
              </div>
            </div>
          </div>

          <button
            v-if="activeSnapshot !== null"
            type="button"
            class="snapshot-reset ds-btn-ghost"
            @click="selectSnapshot(null)"
          >
            恢复默认快照
          </button>
        </template>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { fetchSnapshots, deleteSnapshot } from '../api/snapshots.js'
import { notify } from '../utils/notify.js'
import StateBlock from './ui/StateBlock.vue'

defineProps({
  hideTrigger: {
    type: Boolean,
    default: false,
  },
})

const activeSnapshot = inject('snapshot')
const setSnapshot = inject('setSnapshot')

const rootRef = ref(null)
const snapshots = ref([])
const isOpen = ref(false)
const isLoading = ref(true)
const deletingKey = ref('')
const pendingDeleteKey = ref('')
let ignoreOutsideClickUntil = 0

const formatSnapshotLabel = (value) => {
  if (!value) return '最新数据'
  if (/^\d{8}$/.test(value)) {
    return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`
  }
  return value
}

const triggerTitle = computed(() => (
  activeSnapshot?.value
    ? `当前快照：${formatSnapshotLabel(activeSnapshot.value)}`
    : '选择数据快照'
))

const dropdownSubtitle = computed(() => (
  activeSnapshot?.value
    ? `当前使用：${formatSnapshotLabel(activeSnapshot.value)}`
    : '当前使用最新数据'
))

const isSnapshotChecked = (snap) => {
  if (activeSnapshot?.value) {
    return activeSnapshot.value === snap.key
  }
  return !!snap.isCurrent
}

const clearDeleteState = () => {
  pendingDeleteKey.value = ''
  deletingKey.value = ''
}

const loadSnapshots = async (showLoading = true) => {
  if (showLoading) {
    isLoading.value = true
  }
  try {
    const data = await fetchSnapshots()
    snapshots.value = data.data?.snapshots || []
    if (activeSnapshot?.value) {
      const exists = snapshots.value.some((snap) => snap.key === activeSnapshot.value)
      if (!exists) {
        setSnapshot(null)
        notify.warning('已保存的快照不存在，已自动切换到默认快照')
      }
    }
  } catch (e) {
    console.error('获取快照列表失败:', e)
    notify.error(e?.message || '加载快照列表失败，请稍后重试')
  } finally {
    if (showLoading) {
      isLoading.value = false
    }
  }
}

const handleSnapshotsChanged = () => {
  clearDeleteState()
  loadSnapshots(false)
}

const markOutsideClickIgnored = () => {
  ignoreOutsideClickUntil = Date.now() + 120
}

const toggleDropdown = () => {
  if (isOpen.value) {
    closeDropdown()
    return
  }
  markOutsideClickIgnored()
  isOpen.value = true
}

const openDropdown = () => {
  if (isOpen.value) return
  markOutsideClickIgnored()
  isOpen.value = true
}

const closeDropdown = () => {
  if (!isOpen.value) return
  isOpen.value = false
  clearDeleteState()
}

const selectSnapshot = (key) => {
  clearDeleteState()
  setSnapshot(key)
  isOpen.value = false
}

const requestDeleteSnapshot = (snap) => {
  if (!snap?.key || snap.isCurrent || deletingKey.value) {
    return
  }
  pendingDeleteKey.value = pendingDeleteKey.value === snap.key ? '' : snap.key
}

const cancelDeleteSnapshot = () => {
  pendingDeleteKey.value = ''
}

const confirmDeleteSnapshot = async (snap) => {
  if (!snap?.key || snap.isCurrent) {
    return
  }

  deletingKey.value = snap.key
  try {
    await deleteSnapshot(snap.key)
    if (activeSnapshot?.value === snap.key) {
      setSnapshot(null)
    }
    notify.success(`快照 ${snap.date} 已删除`)
    clearDeleteState()
    globalThis.dispatchEvent?.(new CustomEvent('snapshots:changed', {
      detail: { snapshotKey: snap.key, deleted: true },
    }))
    await loadSnapshots(false)
  } catch (e) {
    notify.error(e?.message || '删除快照失败，请稍后重试')
  } finally {
    deletingKey.value = ''
  }
}

const handleClickOutside = (e) => {
  if (Date.now() < ignoreOutsideClickUntil) {
    return
  }
  if (rootRef.value && !rootRef.value.contains(e.target)) {
    closeDropdown()
  }
}

onMounted(async () => {
  document.addEventListener('click', handleClickOutside)
  globalThis.addEventListener('snapshots:changed', handleSnapshotsChanged)
  await loadSnapshots(true)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  globalThis.removeEventListener('snapshots:changed', handleSnapshotsChanged)
})

watch(isOpen, (open) => {
  if (open) {
    loadSnapshots(false)
  } else {
    clearDeleteState()
  }
})

defineExpose({
  openDropdown,
  closeDropdown,
  toggleDropdown,
  isOpen,
})
</script>

<style scoped>
.snapshot-btn-wrap {
  position: absolute;
  top: 140px;
  right: 20px;
  z-index: 200;
}

.snapshot-btn-wrap-triggerless {
  position: static;
  top: auto;
  right: auto;
  z-index: auto;
}

.snapshot-btn-wrap-triggerless .snapshot-dropdown {
  top: 0;
  right: 0;
}

.snapshot-trigger-btn {
  position: relative;
  width: 52px;
  height: 52px;
  color: #334155;
}

.snapshot-trigger-btn.has-snapshot {
  border-color: rgba(37, 99, 235, 0.28);
  color: #2563eb;
}

.snapshot-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #22c55e;
  border: 2px solid rgba(255, 255, 255, 0.95);
}

.snapshot-dropdown {
  position: absolute;
  top: 0;
  right: 64px;
  width: 304px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.snapshot-dropdown-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.snapshot-dropdown-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.snapshot-dropdown-title {
  color: #0f172a;
  font-size: 15px;
  font-weight: 700;
}

.snapshot-dropdown-subtitle {
  color: #64748b;
  font-size: 12px;
}

.snapshot-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.snapshot-entry {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.snapshot-item {
  width: 100%;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.86);
  padding: 12px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  text-align: left;
  transition: all var(--ds-duration-base) var(--ds-ease-standard);
}

.snapshot-item:hover {
  transform: translateY(-1px);
  border-color: rgba(37, 99, 235, 0.2);
  box-shadow: 0 14px 28px rgba(15, 23, 42, 0.08);
}

.snapshot-item.selected {
  border-color: rgba(37, 99, 235, 0.28);
  background: linear-gradient(135deg, rgba(219, 234, 254, 0.78), rgba(255, 255, 255, 0.92));
}

.snapshot-item-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.snap-date {
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
  font-family: 'Cascadia Mono', 'Consolas', monospace;
}

.snap-meta {
  color: #64748b;
  font-size: 12px;
}

.snapshot-item-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.snap-delete-btn {
  min-height: 32px;
  padding: 0 12px;
  font-size: 12px;
}

.snapshot-confirm {
  align-items: stretch;
}

.snapshot-confirm-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.snap-confirm-btn {
  min-height: 36px;
  font-size: 12px;
}

.snapshot-reset {
  width: 100%;
  justify-content: center;
}

.slide-left-enter-active,
.slide-left-leave-active {
  transition: all 0.24s ease;
}

.slide-left-enter-from,
.slide-left-leave-to {
  opacity: 0;
  transform: translateX(10px) scale(0.96);
  transform-origin: right center;
}

@media (max-width: 768px) {
  .snapshot-btn-wrap {
    top: 132px;
    right: 16px;
  }

  .snapshot-dropdown {
    right: 0;
    top: 62px;
    width: min(304px, calc(100vw - 32px));
  }
}
</style>
