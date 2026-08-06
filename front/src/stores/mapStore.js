/**
 * 地图状态管理 Store
 *
 * 职责：管理侧边栏、地图样式、视图切换等全局地图状态
 * 替代原来分散在 MapComponent.vue 各处的 provide/inject
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useMapStore = defineStore('map', () => {
  // ------------------------------------------------------------------
  // 视图切换（地图 / 信息展示）
  // ------------------------------------------------------------------
  /** 'map' | 'info' */
  const currentView = ref('map')

  function switchView(view) {
    currentView.value = view
  }

  // ------------------------------------------------------------------
  // 地图样式（2D / 3D）
  // ------------------------------------------------------------------
  const is3DMode = ref(localStorage.getItem('mapStyle3D') === 'true')

  function setIs3DMode(value) {
    is3DMode.value = value
    localStorage.setItem('mapStyle3D', String(value))
  }

  // ------------------------------------------------------------------
  // 侧边栏（InfoSidebar）
  // ------------------------------------------------------------------
  const sidebarVisible = ref(false)
  const sidebarTitle   = ref('')
  const sidebarContent = ref('')
  const sidebarNetworkSegments = ref([])

  function openSidebar(title, content, networkSegments = []) {
    sidebarTitle.value   = title
    sidebarContent.value = content
    sidebarNetworkSegments.value = networkSegments
    sidebarVisible.value = true
  }

  function closeSidebar() {
    sidebarVisible.value = false
    sidebarNetworkSegments.value = []
  }

  return {
    currentView, switchView,
    is3DMode, setIs3DMode,
    sidebarVisible, sidebarTitle, sidebarContent, sidebarNetworkSegments,
    openSidebar, closeSidebar,
  }
})
