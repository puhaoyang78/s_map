/**
 * 快照状态管理 Store
 *
 * 职责：管理当前激活的数据快照（历史日期 key 或 null 表示最新快照）
 * 替代原来在 MapComponent.vue 中用 provide/inject 传递的全局快照状态
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

const SNAPSHOT_STORAGE_KEY = 'map_active_snapshot'

function loadPersistedSnapshot() {
  try {
    const raw = globalThis.localStorage?.getItem(SNAPSHOT_STORAGE_KEY)
    if (!raw || raw === 'null' || raw === 'latest') {
      return null
    }
    return raw
  } catch {
    return null
  }
}

function persistSnapshot(key) {
  try {
    if (!key) {
      globalThis.localStorage?.setItem(SNAPSHOT_STORAGE_KEY, 'latest')
      return
    }
    globalThis.localStorage?.setItem(SNAPSHOT_STORAGE_KEY, key)
  } catch {
    // Ignore storage errors in private mode or restricted environments.
  }
}

export const useSnapshotStore = defineStore('snapshot', () => {
  /** null = 最新快照，'YYYYMMDD' = 历史快照 */
  const activeSnapshot = ref(loadPersistedSnapshot())

  /** 切换动画状态：null | 'loading' | 'success' */
  const transitionState = ref(null)

  function setSnapshot(key) {
    activeSnapshot.value = key || null
    persistSnapshot(activeSnapshot.value)
  }

  function setTransitionState(state) {
    transitionState.value = state
  }

  return { activeSnapshot, transitionState, setSnapshot, setTransitionState }
})
