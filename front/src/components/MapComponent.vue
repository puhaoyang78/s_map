<template>
  <div
    class="app-container"
    :class="{
      'terminal-sidebar-expanded': terminalSidebarExpanded,
      'starlink-panel-open': is3DMode && starlinkPanelVisible,
    }"
  >
    <!-- 地图视图 -->
    <div v-show="currentView === 'map'" class="map-container">
      <div id="map" ref="mapContainer"></div>
      <div ref="starlinkOverlayContainer" class="starlink-three-overlay"></div>

      <div v-if="shouldShowMapLoading" class="map-loading-banner">
        <StateBlock
          class="map-state-block map-state-block-loading ds-floating-panel"
          type="loading"
          title="地图加载中"
          description="正在初始化底图和图层，请稍候。"
        />
      </div>

      <div class="map-status-stack">
        <StateBlock
          v-if="shouldShowMapError"
          class="map-state-block map-state-block-error ds-floating-panel"
          type="error"
          :title="mapSurfaceError?.title || '地图初始化失败'"
          :description="mapSurfaceError?.message"
        >
          <template #action>
            <button type="button" class="ds-btn-primary map-state-btn" @click="retryMapInitialization">
              重试初始化
            </button>
          </template>
        </StateBlock>

        <StateBlock
          v-else-if="shouldShowMapLayerNotice"
          class="map-state-block map-state-block-notice ds-floating-panel"
          :type="mapLayerNotice.state === 'warning' ? 'error' : (mapLayerNotice.state === 'empty' ? 'empty' : (mapLayerNotice.state === 'loading' ? 'loading' : 'info'))"
          :title="mapLayerNotice.title"
          :description="mapLayerNotice.message"
        >
          <template #action>
            <button
              v-if="mapLayerNotice.retryLabel"
              type="button"
              class="ds-btn-primary map-state-btn"
              @click="handleMapNoticeRetry"
            >
              {{ mapLayerNotice.retryLabel }}
            </button>
            <button
              v-if="mapLayerNotice.dismissible"
              type="button"
              class="ds-btn-secondary map-state-btn"
              @click="dismissMapLayerNotice"
            >
              知道了
            </button>
          </template>
        </StateBlock>
      </div>
      
      <InfoSidebar
        :visible="sidebarVisible"
        :position="sidebarPosition"
        :title="sidebarTitle"
        :content="sidebarContent"
        :network-segments="sidebarNetworkSegments"
        :context-tags="selectedObjectContextTags"
        @close="closeSidebar"
      />
      
      <TerminalSidebar
        @locate-terminal="handleLocateTerminal"
        @sidebar-expanded-change="handleTerminalSidebarExpandedChange"
      />

      <div class="starlink-panel-shell">
        <Transition name="starlink-panel" appear>
          <StarlinkSatellitePanel
            v-if="is3DMode && starlinkPanelVisible"
            :satellites="filteredSatellites"
            :loading="starlinkLoading"
            :detail-loading="starlinkDetailLoading"
            :network-block-notice="starlinkNetworkBlockNotice"
            :degraded-notice="starlinkDegradedNotice"
            :selected-id="selectedStarlinkId"
            :filters="starlinkFilters"
            @refresh="handleStarlinkRefresh"
            @close="starlinkPanelVisible = false"
            @filters-change="handleStarlinkFiltersChange"
            @select-satellite="handleSelectStarlink"
          />
        </Transition>
      </div>

    </div>

    <!-- 信息展示视图 - 使用单独的组件 -->
    <div v-show="currentView === 'info'" class="info-view-container">
      <InfoView />
    </div>

    <div class="top-right-action-cluster">
      <TopRightActionMenu
        :actions="topRightActions"
        :context-key="currentView"
        main-label="展开页面功能"
        main-title="展开页面功能"
        close-label="收起页面功能"
        close-title="收起页面功能"
        @toggle="handleTopRightMenuToggle"
        @action-click="handleTopRightAction"
      >
        <template #icon-task>
          <svg class="task-toggle-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 3V7M12 17V21M3 12H7M17 12H21M6.34 6.34L9.17 9.17M14.83 14.83L17.66 17.66M17.66 6.34L14.83 9.17M9.17 14.83L6.34 17.66" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            <circle cx="12" cy="12" r="3.5" stroke="currentColor" stroke-width="1.8"/>
          </svg>
        </template>

        <template #icon-style>
          <svg v-if="!is3DMode" class="style-toggle-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="2" fill="none"/>
            <path d="M3 9H21M9 5V19M15 5V19" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <circle cx="6" cy="7" r="0.8" fill="currentColor"/>
            <circle cx="12" cy="7" r="0.8" fill="currentColor"/>
            <circle cx="18" cy="7" r="0.8" fill="currentColor"/>
          </svg>
          <svg v-else class="style-toggle-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" fill="none"/>
            <ellipse cx="12" cy="12" rx="4" ry="9" stroke="currentColor" stroke-width="1.5" fill="none"/>
            <path d="M3 12H21M12 3C14 5.5 15 8.5 15 12C15 15.5 14 18.5 12 21M12 3C10 5.5 9 8.5 9 12C9 15.5 10 18.5 12 21" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </template>

        <template #icon-satellite>
          <svg class="satellite-toggle-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M4 20L10 14M14 10L20 4M9 9L15 15M7 3L21 17" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>
            <circle cx="7" cy="3" r="2" fill="currentColor"/>
            <circle cx="21" cy="17" r="2" fill="currentColor"/>
          </svg>
        </template>

        <template #icon-snapshot>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="3" y="4" width="18" height="18" rx="2" stroke="currentColor" stroke-width="2" fill="none" />
            <path d="M16 2V6M8 2V6M3 10H21" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
        </template>
      </TopRightActionMenu>

      <div class="top-right-snapshot-anchor">
        <SnapshotSelector ref="snapshotSelectorRef" hide-trigger class="top-right-snapshot-selector" />
      </div>
    </div>
    
    <!-- 界面切换按钮 - 底部 -->
    <div class="view-toggle ds-floating-panel">
      <button
        type="button"
        class="toggle-button" 
        :class="{ 'active': currentView === 'map' }" 
        :aria-pressed="currentView === 'map'"
        title="切换到地图视图"
        aria-label="切换到地图视图"
        @click="switchView('map')"
      >
        <environment-outlined />
        <span>地图</span>
      </button>
      <button
        type="button"
        class="toggle-button" 
        :class="{ 'active': currentView === 'info' }" 
        :aria-pressed="currentView === 'info'"
        title="切换到信息展示视图"
        aria-label="切换到信息展示视图"
        @click="switchView('info')"
      >
        <bar-chart-outlined />
        <span>信息展示</span>
      </button>
    </div>

    <!-- 快照切换过渡动画 -->
    <SnapshotTransition />

    <!-- 系统设置面板 -->
    <SettingsPanel
      :visible="panelVisible"
      :map-instance="mapRef"
      @close="closePanel"
    />

  </div>
</template>


<script setup>
import { ref, computed, onMounted, onUnmounted, provide, watch, defineAsyncComponent } from 'vue';
import InfoSidebar from './InfoSidebar.vue';
import TerminalSidebar from './TerminalSidebar.vue';
import { notify } from '../utils/notify.js';
import { useSnapshotStore } from '../stores/snapshotStore.js';
import { useMapStore } from '../stores/mapStore.js';
import { storeToRefs } from 'pinia';
import { EnvironmentOutlined, BarChartOutlined } from '@ant-design/icons-vue';
import StateBlock from './ui/StateBlock.vue';
import TopRightActionMenu from './ui/TopRightActionMenu.vue';
import SnapshotSelector from './SnapshotSelector.vue';
import { MAP_STYLES } from '../constants/mapConstants.js';
import { useMapLayers } from '../composables/useMapLayers.js';
import { useMapNavigation } from '../composables/useMapNavigation.js';
import { createMapInstance, destroyMapInstance, resizeMapInstance } from '../composables/useMapInstance.js';
import { useStarlinkSatellites } from '../composables/useStarlinkSatellites.js';
import { useStarlinkThreeOverlay } from '../composables/useStarlinkThreeOverlay.js';
import { formatStarlinkSatelliteDetails } from '../utils/mapPopupBuilders.js';

const lazyComponent = (loader) => defineAsyncComponent({
  loader,
  suspensible: false,
})

const InfoView = lazyComponent(() => import('./InfoView.vue'));
const SnapshotTransition = lazyComponent(() => import('./SnapshotTransition.vue'));
const SettingsPanel = lazyComponent(() => import('./SettingsPanel.vue'));
const StarlinkSatellitePanel = lazyComponent(() => import('./StarlinkSatellitePanel.vue'));

// ── Pinia stores ───────────────────────────────────────────
const snapshotStore = useSnapshotStore();
const mapStore = useMapStore();
const { activeSnapshot } = storeToRefs(snapshotStore);

// 当前视图（与 mapStore 同步）
const currentView = computed(() => mapStore.currentView);

// 快照（保持 provide/inject 以兼容未迁移的子组件，同时写入 store）
provide('snapshot', activeSnapshot);
provide('setSnapshot', (key) => {
  snapshotStore.setSnapshot(key);
});

// 快照切换过渡动画状态（保持 provide/inject 兼容性）
const snapshotTransitionState = ref(null);
provide('snapshotTransitionState', snapshotTransitionState);

// 地图样式状态
const is3DMode = ref(localStorage.getItem('mapStyle3D') === 'true');
const starlinkPanelVisible = ref(false);

// Starlink 卫星状态
const {
  loading: starlinkLoading,
  detailLoading: starlinkDetailLoading,
  error: starlinkError,
  filters: starlinkFilters,
  networkBlockNotice: starlinkNetworkBlockNotice,
  degradedNotice: starlinkDegradedNotice,
  filteredSatellites,
  loadSatellites,
  loadSatelliteDetail,
} = useStarlinkSatellites();
const selectedStarlinkId = ref('');
const visibleStarlinkSatellites = ref([]);
const terminalSidebarExpanded = ref(false);
const snapshotSelectorRef = ref(null);

// 弹出面板状态
const panelVisible = ref(false);
const mapBootstrapState = ref('idle');
const mapSurfaceError = ref(null);
const mapLayerNotice = ref({
  state: 'idle',
  title: '',
  message: '',
  retryLabel: '',
  dismissible: false,
  action: '',
});
const lastMapErrorSignature = ref('');
const selectedObjectContext = ref(null);

// 切换面板显示/隐藏
const togglePanel = () => { panelVisible.value = !panelVisible.value; };
const closePanel = () => { panelVisible.value = false; };
const satelliteButtonTitle = computed(() => (
  is3DMode.value
    ? (starlinkPanelVisible.value ? '隐藏卫星信息' : '显示卫星信息')
    : '切换到3D并显示卫星信息'
));

const formatSnapshotLabel = (snapshotKey) => {
  if (!snapshotKey) {
    return '最新数据';
  }
  if (/^\d{8}$/.test(snapshotKey)) {
    return `${snapshotKey.slice(0, 4)}-${snapshotKey.slice(4, 6)}-${snapshotKey.slice(6, 8)}`;
  }
  return snapshotKey;
};

const formatContextDateTime = (value) => {
  if (!value) {
    return '';
  }

  const text = String(value).trim();
  if (!text) {
    return '';
  }

  const hasTimezone = /(?:[zZ]|[+-]\d{2}:\d{2})$/.test(text);
  const parsed = new Date(hasTimezone ? text : `${text}Z`);
  if (Number.isNaN(parsed.getTime())) {
    return text;
  }

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(parsed);
};

const setSelectedObjectContext = (payload) => {
  if (!payload) {
    selectedObjectContext.value = null;
    return;
  }

  selectedObjectContext.value = {
    id: payload.id || '',
    type: payload.type || 'object',
    typeLabel: payload.typeLabel || '对象',
    name: payload.name || '未命名对象',
    subtitle: payload.subtitle || '',
    sourceLabel: payload.sourceLabel || '当前视图',
  };
};

const clearSelectedObjectContext = () => {
  selectedObjectContext.value = null;
};

const clearMapSurfaceError = () => {
  mapSurfaceError.value = null;
};

const setMapLayerNotice = (payload = {}) => {
  mapLayerNotice.value = {
    state: payload.state || 'idle',
    title: payload.title || '',
    message: payload.message || '',
    retryLabel: payload.retryLabel || '',
    dismissible: payload.dismissible || false,
    action: payload.action || '',
  };
};

const clearMapLayerNotice = () => {
  setMapLayerNotice();
};

const handleLayerStatusUpdate = (payload = {}) => {
  if (payload.kind !== 'heatmap') {
    return;
  }

  if (payload.state === 'loading') {
    clearMapLayerNotice();
    return;
  }

  const snapshotLabel = formatSnapshotLabel(activeSnapshot.value);

  if (payload.state === 'empty') {
    setMapLayerNotice({
      state: 'empty',
      title: '当前地图暂无热力图数据',
      message: payload.message || `当前显示的 ${snapshotLabel} 快照没有可展示的终端分布数据。`,
      retryLabel: '重新加载',
      dismissible: true,
      action: 'heatmap',
    });
    return;
  }

  if (payload.state === 'ready') {
    clearMapLayerNotice();
  }
};

const handleLayerError = (payload = {}) => {
  if (payload.kind === 'pop') {
    setMapLayerNotice({
      state: 'error',
      title: payload.title || 'PoP/地面站图层加载失败',
      message: payload.message || 'PoP 与地面站图层暂时不可用，地图底图仍可继续浏览。',
      retryLabel: '重新加载地图',
      dismissible: true,
      action: 'map',
    });
    return;
  }
  if (payload.kind !== 'heatmap') {
    return;
  }
  setMapLayerNotice({
    state: 'error',
    title: payload.title || '热力图加载失败',
    message: payload.message || '热力图数据暂时不可用，地图底图仍可继续浏览。',
    retryLabel: '重试热力图',
    dismissible: true,
    action: 'heatmap',
  });
};

const reportMapIssue = ({ code = 'unknown', message = '地图暂时不可用，请稍后重试。', fatal = false } = {}) => {
  const signature = `${code}:${message}:${fatal ? 'fatal' : 'warn'}`;
  if (lastMapErrorSignature.value === signature) {
    return;
  }
  lastMapErrorSignature.value = signature;

  if (fatal || mapBootstrapState.value !== 'ready') {
    mapBootstrapState.value = 'error';
    mapSurfaceError.value = {
      title: code === 'mapbox-token-missing' ? '地图配置缺失' : '地图初始化失败',
      message,
    };
    return;
  }

  setMapLayerNotice({
    state: 'warning',
    title: '地图资源加载异常',
    message,
    retryLabel: '重试地图',
    dismissible: true,
    action: 'map',
  });
};

const currentSnapshotLabel = computed(() => formatSnapshotLabel(activeSnapshot.value));
const currentMapModeLabel = computed(() => (is3DMode.value ? '3D 地球模式' : '2D 热力图模式'));
const selectedObjectContextTags = computed(() => {
  if (!selectedObjectContext.value) {
    return [];
  }

  const tags = [
    { label: '对象类型', value: selectedObjectContext.value.typeLabel },
    { label: '来源', value: selectedObjectContext.value.sourceLabel },
    { label: '显示模式', value: currentMapModeLabel.value },
  ];

  if (selectedObjectContext.value.type === 'terminal') {
    tags.splice(2, 0, { label: '当前快照', value: currentSnapshotLabel.value });
  }

  if (selectedObjectContext.value.type === 'satellite') {
    const updatedAt = formatContextDateTime(selectedObjectContext.value.updatedAt);
    if (updatedAt) {
      tags.splice(2, 0, { label: '更新时间', value: updatedAt });
    }
  }

  return tags;
});
const shouldShowMapLoading = computed(() => mapBootstrapState.value === 'loading');
const shouldShowMapError = computed(() => mapBootstrapState.value === 'error' && !!mapSurfaceError.value);
const shouldShowMapLayerNotice = computed(() => (
  mapBootstrapState.value === 'ready'
  && ['empty', 'error', 'warning'].includes(mapLayerNotice.value.state)
));

const applyMapStyleMode = (mode3D) => {
  is3DMode.value = mode3D;
  localStorage.setItem('mapStyle3D', String(mode3D));
  setStarlinkOverlayEnabled(mode3D);
  setStarlinkOverlaySatellites(mode3D ? filteredSatellites.value : []);

  if (!mode3D) {
    starlinkPanelVisible.value = false;
    visibleStarlinkSatellites.value = [];
  }

  if (mapRef.value) {
    mapRef.value.setStyle(mode3D ? MAP_STYLES.STANDARD_3D : MAP_STYLES.DARK_2D);
    // 样式切换后重新挂载图层
    mapRef.value.once('style.load', async () => {
      try {
        mapRef.value.setProjection(mode3D ? 'globe' : 'mercator');
      } catch {
        // Ignore projection unsupported runtime.
      }

      if (mode3D) {
        try {
          mapRef.value.setFog({
            color: 'rgb(12, 22, 48)',
            'high-color': 'rgb(32, 46, 88)',
            'horizon-blend': 0.18,
            'space-color': 'rgb(3, 7, 18)',
            'star-intensity': 0.25,
          });
        } catch {
          // Ignore fog unsupported runtime.
        }
      }

      try {
        await setupLayers(mapRef.value);
      } catch (error) {
        reportMapIssue({
          code: 'map-style-switch-failed',
          message: error?.message || '地图样式切换后图层恢复失败，请重试。',
          fatal: false,
        });
      }
    });
  }
};

const toggleStarlinkPanel = async () => {
  if (!is3DMode.value) {
    applyMapStyleMode(true);
    starlinkPanelVisible.value = true;
    if (filteredSatellites.value.length === 0) {
      await loadSatellites();
    }
    return;
  }

  starlinkPanelVisible.value = !starlinkPanelVisible.value;
  if (starlinkPanelVisible.value && filteredSatellites.value.length === 0) {
    await loadSatellites();
  }
};

// 切换地图 2D / 3D 样式
const toggleMapStyle = () => {
  applyMapStyleMode(!is3DMode.value);
};

const isSnapshotDropdownOpen = () => {
  const openState = snapshotSelectorRef.value?.isOpen;
  if (typeof openState === 'object' && openState !== null && 'value' in openState) {
    return !!openState.value;
  }
  return !!openState;
};

const toggleSnapshotDropdown = () => {
  const selector = snapshotSelectorRef.value;
  if (!selector) {
    return;
  }

  if (isSnapshotDropdownOpen()) {
    selector.closeDropdown?.();
    return;
  }

  window.setTimeout(() => {
    snapshotSelectorRef.value?.openDropdown?.();
  }, 0);
};

const closeSnapshotDropdown = () => {
  snapshotSelectorRef.value?.closeDropdown?.();
};

const topRightActions = computed(() => {
  const baseActions = [
    {
      key: 'task',
      label: '探测任务',
      title: panelVisible.value ? '收起探测任务' : '打开探测任务',
      active: panelVisible.value,
    },
    {
      key: 'snapshot',
      label: '数据快照',
      title: activeSnapshot.value ? `当前快照：${formatSnapshotLabel(activeSnapshot.value)}` : '选择数据快照',
      active: Boolean(activeSnapshot.value),
    },
  ];

  if (currentView.value !== 'map') {
    return baseActions;
  }

  return [
    baseActions[0],
    {
      key: 'style',
      label: is3DMode.value ? '切换到 2D 模式' : '切换到 3D 模式',
      title: is3DMode.value ? '切换到 2D 模式' : '切换到 3D 模式',
      active: is3DMode.value,
    },
    {
      key: 'satellite',
      label: satelliteButtonTitle.value,
      title: satelliteButtonTitle.value,
      active: is3DMode.value && starlinkPanelVisible.value,
    },
    baseActions[1],
  ];
});

const handleTopRightAction = (actionKey) => {
  if (actionKey === 'task') {
    togglePanel();
    return;
  }
  if (actionKey === 'style') {
    toggleMapStyle();
    return;
  }
  if (actionKey === 'satellite') {
    void toggleStarlinkPanel();
    return;
  }
  if (actionKey === 'snapshot') {
    toggleSnapshotDropdown();
  }
};

const handleTopRightMenuToggle = (expanded) => {
  if (expanded) {
    closeSnapshotDropdown();
  }
};

// 地图实例引用（供 SettingsPanel 等子组件使用）
const mapRef = ref(null);

// 切换视图
const switchView = (view) => {
  mapStore.switchView(view);
  if (view === 'map') {
    setTimeout(() => {
      resizeMapInstance(mapRef.value);
    }, 100);
  }
};

// 侧边栏状态
const sidebarVisible = ref(false);
const sidebarPosition = ref('right');
const sidebarTitle = ref('');
const sidebarContent = ref('');
const sidebarNetworkSegments = ref([]);

// 打开侧边栏
const openSidebar = (title, content, clickX, networkSegments = [], selection = null) => {
  sidebarPosition.value = 'right';
  setSelectedObjectContext(selection);
  
  // 如果侧边栏已经打开，先关闭再打开，以触发动画效果
  if (sidebarVisible.value) {
    sidebarVisible.value = false;
    
    // 使用 setTimeout 确保关闭动画有时间执行
    setTimeout(() => {
      sidebarTitle.value = title;
      sidebarContent.value = content;
      sidebarNetworkSegments.value = networkSegments;
      sidebarVisible.value = true;
    }, 10);
  } else {
    sidebarTitle.value = title;
    sidebarContent.value = content;
    sidebarNetworkSegments.value = networkSegments;
    sidebarVisible.value = true;
  }
};

// 关闭侧边栏
const closeSidebar = () => {
  sidebarVisible.value = false;
  sidebarNetworkSegments.value = [];
  clearSelectedObjectContext();
};

const { setupLayers, cleanupLayerInteractions } = useMapLayers({
  activeSnapshot,
  sidebarVisible,
  closeSidebar,
  openSidebar,
  onLayerStatus: handleLayerStatusUpdate,
  onLayerError: handleLayerError,
  onSelectionChange: setSelectedObjectContext,
});

const handleStarlinkRefresh = async () => {
  await loadSatellites(true);
};

const handleTerminalSidebarExpandedChange = (expanded) => {
  terminalSidebarExpanded.value = Boolean(expanded);
};

const handleStarlinkFiltersChange = (nextFilters) => {
  starlinkFilters.value = {
    ...starlinkFilters.value,
    ...nextFilters,
  };
};

const focusSatellite = (satellite) => {
  if (!satellite || !mapRef.value) return;
  const lng = Number(satellite.longitude);
  const lat = Number(satellite.latitude);
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) return;

  mapRef.value.flyTo({
    center: [lng, lat],
    zoom: Math.max(mapRef.value.getZoom(), 4),
    speed: 0.9,
    essential: true,
  });
};

const handleSelectStarlink = async ({ satelliteId, fromPanel }) => {
  if (!satelliteId) return;
  selectedStarlinkId.value = satelliteId;
  const detail = await loadSatelliteDetail(satelliteId);
  if (!detail) return;

  openSidebar(
    `🛰️ Starlink 卫星 | ${detail.name || satelliteId}`,
    formatStarlinkSatelliteDetails(detail),
    undefined,
    [],
    {
      id: detail.id || satelliteId,
      type: 'satellite',
      typeLabel: '卫星',
      name: detail.name || satelliteId,
      subtitle: detail.norad_cat_id ? `NORAD ${detail.norad_cat_id}` : '',
      sourceLabel: fromPanel ? '卫星面板' : '地图点选',
      updatedAt: detail.metadata_fetched_at || '',
    },
  );

  if (fromPanel) {
    focusSatellite(detail);
  }
};

const {
  flyToTerminal,
  highlightDevice,
  registerLocateListener,
  unregisterLocateListener,
} = useMapNavigation({
  getMap: () => map,
  switchToMapView: () => mapStore.switchView('map'),
});

// 提供侧边栏控制函数给子组件
provide('openSidebar', openSidebar);

const highlightDeviceWithContext = (device = {}) => {
  if (!device) {
    clearSelectedObjectContext();
    return;
  }
  highlightDevice(device);
  const subtitleParts = [
    device.ip ? `IP ${device.ip}` : '',
    device.country || '',
    device.city || '',
  ].filter(Boolean);
  setSelectedObjectContext({
    id: device.ip || `${device.longitude || ''}-${device.latitude || ''}`,
    type: 'terminal',
    typeLabel: '终端设备',
    name: device.ip || '终端设备',
    subtitle: subtitleParts.join(' · '),
    sourceLabel: device.sourceLabel || '终端侧栏',
  });
};

const handleLocateTerminal = (payload) => {
  const location = payload?.location || payload;
  if (!location) return;

  flyToTerminal(location);
  if (payload?.selection) {
    setSelectedObjectContext(payload.selection);
  } else {
    clearSelectedObjectContext();
  }
};

let activeHeatmapAbortController = null;
let latestHeatmapRequestId = 0;

const refreshHeatmapForSnapshot = async (snapshotKey) => {
  // 防竞态：只让最后一次请求落地（参照 TerminalSidebar 的 latestRequestId + AbortController 范式）
  activeHeatmapAbortController?.abort();
  activeHeatmapAbortController = new globalThis.AbortController();
  latestHeatmapRequestId += 1;
  const requestId = latestHeatmapRequestId;
  const { signal } = activeHeatmapAbortController;
  const isLatestHeatmapRequest = () => requestId === latestHeatmapRequestId;

  // 显示加载动画
  snapshotTransitionState.value = 'loading';
  try {
    if (map) {
      const { addHeatmapLayer } = await import('../utils/heatmapLayer.js');
      const result = await addHeatmapLayer(map, true, snapshotKey, signal);
      if (!isLatestHeatmapRequest()) return;
      handleLayerStatusUpdate({
        kind: 'heatmap',
        state: result?.hasData ? 'ready' : 'empty',
        message: result?.hasData
          ? (snapshotKey ? `已切换到 ${formatSnapshotLabel(snapshotKey)} 快照` : '最新热力图已刷新')
          : (snapshotKey ? `${formatSnapshotLabel(snapshotKey)} 快照暂无热力图数据` : '当前暂无可展示的热力图数据'),
      });
    } else {
      // 地图尚未挂载时，稍作延迟以保证动画可见
      await new Promise(r => setTimeout(r, 600));
    }
    if (!isLatestHeatmapRequest()) return;
    // 切换到成功状态再自动关闭
    snapshotTransitionState.value = 'success';
    setTimeout(() => { if (isLatestHeatmapRequest()) snapshotTransitionState.value = null; }, 1800);
  } catch (e) {
    if (e?.name === 'AbortError' || !isLatestHeatmapRequest()) return;
    console.error('切换快照时刷新热力图失败:', e);
    notify.error(e?.message || '刷新地图数据失败，请稍后重试');
    handleLayerError({
      kind: 'heatmap',
      title: '快照加载失败',
      message: e?.message || '当前快照的地图数据加载失败，请稍后重试。',
    });
    snapshotTransitionState.value = null;
  }
};

const retryMapInitialization = () => {
  lastMapErrorSignature.value = '';
  clearMapSurfaceError();
  clearMapLayerNotice();
  destroyMapInstance(map);
  map = null;
  mapRef.value = null;
  void initMap();
};

const retryHeatmapLayer = async () => {
  await refreshHeatmapForSnapshot(activeSnapshot.value);
};

const retryStarlinkLayer = async () => {
  await loadSatellites(true);
};

const dismissMapLayerNotice = () => {
  clearMapLayerNotice();
};

const handleMapNoticeRetry = async () => {
  if (mapLayerNotice.value.action === 'map') {
    retryMapInitialization();
    return;
  }
  if (mapLayerNotice.value.action === 'starlink') {
    await retryStarlinkLayer();
    return;
  }
  await retryHeatmapLayer();
};

// 快照切换时重新加载热力图
watch(activeSnapshot, async (newSnapshot) => {
  await refreshHeatmapForSnapshot(newSnapshot);
});

// 地图容器引用
const mapContainer = ref(null);
const starlinkOverlayContainer = ref(null);
// 地图实例
let map = null;

const {
  mount: mountStarlinkOverlay,
  unmount: unmountStarlinkOverlay,
  setEnabled: setStarlinkOverlayEnabled,
  setSatellites: setStarlinkOverlaySatellites,
  setSelectedSatelliteId: setStarlinkOverlaySelectedId,
} = useStarlinkThreeOverlay({
  getMap: () => mapRef.value,
  getContainer: () => starlinkOverlayContainer.value,
  onSatelliteClick: (satelliteId) => {
    handleSelectStarlink({ satelliteId, fromPanel: false });
  },
});

// 监听视图变化，当切换到地图视图时确保地图正确渲染
watch(() => mapStore.currentView, (newView) => {
  closeSnapshotDropdown();
  if (newView === 'map' && mapRef.value) {
    setTimeout(() => { resizeMapInstance(mapRef.value); }, 0);
  }
});

// 初始化地图
const initMap = async () => {
  mapBootstrapState.value = 'loading';
  clearMapSurfaceError();
  clearMapLayerNotice();
  map = await createMapInstance({
    container: mapContainer.value,
    is3DMode: is3DMode.value,
    previousMap: map,
    onLoad: async (loadedMap) => {
      await setupLayers(loadedMap);
      await mountStarlinkOverlay();
      setStarlinkOverlayEnabled(is3DMode.value);
      setStarlinkOverlaySatellites(is3DMode.value ? filteredSatellites.value : []);
      setStarlinkOverlaySelectedId(selectedStarlinkId.value);
    },
    onReady: () => {
      mapBootstrapState.value = 'ready';
    },
    onError: reportMapIssue,
  });
  mapRef.value = map;
};

// 将 highlightDevice 函数提供给需要它的组件
provide('highlightDevice', highlightDeviceWithContext);


onMounted(async () => {
  if (is3DMode.value) {
    await loadSatellites();
  }

  // 延迟一帧确保DOM已渲染
  setTimeout(() => {
    // 初始化地图
    void initMap();
    
    // 添加全局事件监听器
    registerLocateListener();
    
    // 如果初始视图是地图，确保地图可见
    if (mapStore.currentView === 'map') {
      setTimeout(() => {
        resizeMapInstance(mapRef.value);
      }, 100);
    }
  }, 0);
});

onUnmounted(() => {
  // 取消仍在途的热力图请求，避免卸载后写入已销毁的地图
  activeHeatmapAbortController?.abort();
  unmountStarlinkOverlay();
  cleanupLayerInteractions(map);
  // 组件卸载时移除地图
  destroyMapInstance(map);
  map = null;
  
  // 移除事件监听器
  unregisterLocateListener();
});

watch(
  [filteredSatellites, () => is3DMode.value],
  ([items, mode3D]) => {
    setStarlinkOverlayEnabled(mode3D);
    setStarlinkOverlaySatellites(mode3D ? items : []);

    visibleStarlinkSatellites.value = mode3D ? items : [];
    if (items.length === 0) {
      selectedStarlinkId.value = '';
      return;
    }
    if (!selectedStarlinkId.value || !items.some((item) => item.id === selectedStarlinkId.value)) {
      selectedStarlinkId.value = items[0].id;
    }
  },
  { immediate: true },
);

watch(
  () => is3DMode.value,
  async (v) => {
    if (v && filteredSatellites.value.length === 0) {
      await loadSatellites();
    }
  },
);

watch(
  () => starlinkError.value,
  (message) => {
    if (!message) {
      if (mapLayerNotice.value.action === 'starlink') {
        clearMapLayerNotice();
      }
      return;
    }
    if (!is3DMode.value) return;
    if (['error', 'loading'].includes(mapLayerNotice.value.state)) return;
    setMapLayerNotice({
      state: 'warning',
      title: '卫星覆盖层加载异常',
      message,
      retryLabel: '重试卫星数据',
      dismissible: true,
      action: 'starlink',
    });
  },
);

watch(
  () => selectedStarlinkId.value,
  (satelliteId) => {
    setStarlinkOverlaySelectedId(satelliteId || '');
  },
  { immediate: true },
);
</script>

<style>
/* 全局样式，影响地图弹出窗口 */
.pop-popup .mapboxgl-popup-content,
.station-popup .mapboxgl-popup-content,
.heatmap-popup .mapboxgl-popup-content,
.starlink-popup .mapboxgl-popup-content {
  padding: 0;
  min-width: 260px;
  border-radius: 18px;
  border: 1px solid rgba(191, 219, 254, 0.72);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 251, 255, 0.92));
  box-shadow: 0 18px 44px rgba(15, 23, 42, 0.14);
  backdrop-filter: blur(18px);
}

.pop-popup .mapboxgl-popup-tip,
.station-popup .mapboxgl-popup-tip,
.heatmap-popup .mapboxgl-popup-tip,
.starlink-popup .mapboxgl-popup-tip {
  border-top-color: rgba(255, 255, 255, 0.96);
}

.pop-popup .mapboxgl-popup-close-button,
.station-popup .mapboxgl-popup-close-button,
.heatmap-popup .mapboxgl-popup-close-button,
.starlink-popup .mapboxgl-popup-close-button {
  top: 10px;
  right: 10px;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 1px solid rgba(226, 232, 240, 0.92);
  background: rgba(255, 255, 255, 0.9);
  color: #64748b;
  font-size: 18px;
  line-height: 1;
  transition: all var(--ds-duration-fast) var(--ds-ease-standard);
}

.pop-popup .mapboxgl-popup-close-button:hover,
.station-popup .mapboxgl-popup-close-button:hover,
.heatmap-popup .mapboxgl-popup-close-button:hover,
.starlink-popup .mapboxgl-popup-close-button:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.heatmap-info {
  padding: 16px 18px;
}

.heatmap-info .info-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(226, 232, 240, 0.9);
}

.heatmap-info .info-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.heatmap-info .info-row.highlight {
  margin: 0 -6px;
  padding: 12px 14px;
  border-radius: 14px;
  border-bottom: none;
  background: linear-gradient(135deg, rgba(219, 234, 254, 0.88), rgba(239, 246, 255, 0.72));
}

.heatmap-info .info-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}

.heatmap-info .info-value {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  text-align: right;
}

.heatmap-info .info-value.count {
  color: #1d4ed8;
  font-size: 16px;
}
</style>

<style scoped>
.view-toggle {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid #e5e7eb;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12);
}

.toggle-button {
  color: #4a4a4a;
  border-radius: 8px;
}

.toggle-button:hover {
  background: #f1f5f9;
  color: #1a1a1a;
}

.toggle-button.active {
  background: #2563eb;
  color: #ffffff;
}

.panel-overlay {
  background: rgba(15, 23, 42, 0.24);
}

.panel-content {
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #e5e7eb;
  box-shadow: 0 24px 46px rgba(15, 23, 42, 0.14);
}

.panel-header,
.panel-tabs {
  background: #f8f9fa;
  border-color: #e5e7eb;
}

.panel-header h3,
.panel-section h4,
.update-status h5,
.record-type,
.log-section h6 {
  color: #1a1a1a;
}

.panel-section,
.update-form,
.update-status,
.detection-form,
.record-item,
.detection-logs,
.logs-container {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
}

.panel-section p,
.form-hint,
.record-message,
.page-info,
.progress-info,
.records-header span {
  color: #4a4a4a;
}

.panel-btn,
.update-btn,
.status-btn,
.cache-btn,
.heatmap-btn,
.detection-btn,
.stop-btn,
.save-config-btn,
.delete-all-btn,
.pagination button {
  border-radius: 10px;
  transition: all 0.3s ease;
}

.panel-btn:hover,
.update-btn:hover:not(:disabled),
.status-btn:hover:not(:disabled),
.cache-btn:hover:not(:disabled),
.heatmap-btn:hover,
.detection-btn:hover:not(:disabled),
.stop-btn:hover,
.save-config-btn:hover:not(:disabled),
.delete-all-btn:hover:not(:disabled),
.pagination button:hover:not(:disabled) {
  transform: translateY(-2px);
}

.form-group input[type="password"],
.form-group input[type="text"],
.form-group select,
.detection-form select,
.detection-form input[type="text"] {
  border-radius: 10px;
  border: 1px solid #d1d5db;
}

.form-group input[type="password"]:focus,
.form-group input[type="text"]:focus,
.form-group select:focus,
.detection-form select:focus,
.detection-form input[type="text"]:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.tab-button.active,
.progress-bar,
.status-info.running .progress-bar {
  background: #2563eb;
}
</style>

<style scoped>
.app-container {
  position: absolute;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
}

.map-container {
  position: absolute;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 1;
}

.info-view-container {
  position: absolute;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 1;
  background-color: #f5f5f5;
}

#map {
  width: 100%;
  height: 100%;
}

.map-status-stack {
  position: absolute;
  top: 20px;
  left: 20px;
  z-index: 230;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: min(380px, calc(100vw - 144px));
  min-width: 0;
}

.map-loading-banner {
  position: absolute;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 240;
  width: min(420px, calc(100vw - 160px));
}

.map-state-block {
  min-width: 0;
  max-width: 100%;
  border-radius: var(--ds-radius-lg);
  border-color: rgba(255, 255, 255, 0.54);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(248, 251, 255, 0.88));
  backdrop-filter: blur(18px);
  box-shadow: var(--ds-shadow-md);
}

.map-state-block .ds-state-block__body {
  gap: var(--ds-space-2);
}

.map-state-block .ds-state-block__title {
  font-size: 14px;
}

.map-state-block .ds-state-block__description {
  line-height: 1.55;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.map-state-btn {
  min-height: 36px;
  padding: 0 var(--ds-space-3);
  font-size: 12px;
  border-radius: var(--ds-radius-pill);
  box-shadow: none;
}

.app-container {
  --map-action-rail-top: 24px;
  --map-action-rail-right: 20px;
  --map-action-button-gap: 14px;
  --map-action-button-size: 52px;
  --left-floating-panel-offset: 64px;
  --left-sidebar-expanded-offset: 340px;
  --starlink-popup-offset: 380px;
}

.top-right-action-cluster {
  position: absolute;
  top: var(--map-action-rail-top);
  right: var(--map-action-rail-right);
  z-index: 2600;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.top-right-snapshot-anchor {
  position: absolute;
  top: 0;
  right: calc(var(--map-action-button-size) + 12px);
  z-index: 2590;
}

.starlink-three-overlay {
  position: absolute;
  inset: 0;
  z-index: 160;
  overflow: hidden;
  pointer-events: none;
}

.starlink-three-overlay .starlink-three-overlay-canvas {
  display: block;
}

.starlink-panel-shell {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  left: var(--left-floating-panel-offset);
  z-index: 2500;
  pointer-events: none;
}

.app-container.terminal-sidebar-expanded .starlink-panel-shell {
  left: var(--left-sidebar-expanded-offset);
}

.starlink-panel-shell :deep(.satellite-panel) {
  pointer-events: auto;
  left: 20px !important;
}

.app-container.starlink-panel-open :deep(.mapboxgl-popup.starlink-popup) {
  margin-left: var(--starlink-popup-offset);
}

/* 视图切换按钮样式 - 底部 */
.view-toggle {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 4px;
  padding: 6px;
  z-index: 100;
  border-radius: var(--ds-radius-xl);
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid rgba(255, 255, 255, 0.52);
  backdrop-filter: blur(20px);
  box-shadow: var(--ds-shadow-md);
}

.toggle-button {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 46px;
  padding: 0 18px;
  border: none;
  border-radius: 14px;
  background: transparent;
  cursor: pointer;
  color: var(--ds-text-secondary);
  transition: all var(--ds-duration-base) var(--ds-ease-standard);
  margin: 0;
}

.toggle-button span {
  margin-left: 6px;
}

.toggle-button:hover {
  color: var(--ds-text-strong);
  background: rgba(255, 255, 255, 0.68);
}

.toggle-button.active {
  background: linear-gradient(135deg, var(--ds-primary-500), var(--ds-primary-400));
  color: #ffffff;
  box-shadow: 0 14px 26px rgba(37, 99, 235, 0.22);
}

.toggle-button .anticon {
  transition: transform 0.3s ease, filter 0.3s ease;
}

.toggle-button:hover .anticon {
  transform: translateY(-1px) scale(1.08);
}

.toggle-button.active .anticon {
  transform: translateY(-1px) scale(1.12);
  filter: drop-shadow(0 0 6px rgba(147, 197, 253, 0.75));
}

/* PoP 详细信息样式 */
.pop-details {
  font-size: 14px;
  line-height: 1.5;
}

.detail-item {
  margin-bottom: 8px;
}

.detail-label {
  font-weight: bold;
  color: #3498db;
}

.detail-value {
  margin-left: 4px;
}

.network-list {
  margin: 4px 0 0 0;
  padding-left: 16px;
}

.task-toggle-icon,
.style-toggle-icon {
  transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1), filter 0.35s ease;
}

.app-container :deep(.top-right-snapshot-selector.snapshot-btn-wrap-triggerless) {
  position: static;
}

.app-container :deep(.top-right-snapshot-selector.snapshot-btn-wrap-triggerless .snapshot-dropdown) {
  top: 0;
  right: 0;
}

.app-container :deep(.top-right-snapshot-selector .snapshot-dropdown) {
  box-shadow: var(--ds-shadow-lg);
}

.app-container .terminal-sidebar {
  z-index: 3200;
  isolation: isolate;
}

.app-container .terminal-sidebar.expanded {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 251, 255, 0.94)),
    rgba(255, 255, 255, 0.96);
  box-shadow: 16px 0 40px rgba(15, 23, 42, 0.12);
}

.app-container .terminal-sidebar.expanded .sidebar-content,
.app-container .terminal-sidebar.expanded .sidebar-header {
  position: relative;
  z-index: 1;
}

.app-container .terminal-sidebar.expanded .terminal-details {
  position: absolute;
  z-index: 2;
}

.app-container .terminal-sidebar .toggle-button {
  z-index: 2;
}

.satellite-toggle-icon {
  transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1), filter 0.35s ease;
}

.starlink-panel-enter-active,
.starlink-panel-leave-active {
  transition: opacity 0.3s ease, transform 0.35s cubic-bezier(0.22, 1, 0.36, 1), filter 0.3s ease;
}

.starlink-panel-enter-from,
.starlink-panel-leave-to {
  opacity: 0;
  transform: translate3d(-20px, 0, 0) scale(0.96);
  filter: blur(2px);
}

.starlink-panel-enter-to,
.starlink-panel-leave-from {
  opacity: 1;
  transform: translate3d(0, 0, 0) scale(1);
  filter: blur(0);
}

@media (max-width: 768px) {
  .app-container {
    --map-action-rail-top: 16px;
    --map-action-rail-right: 16px;
    --map-action-button-gap: 10px;
    --left-floating-panel-offset: 12px;
    --left-sidebar-expanded-offset: 12px;
    --starlink-popup-offset: 0px;
  }

  .top-right-snapshot-anchor {
    right: calc(var(--map-action-button-size) + 8px);
  }

  .map-status-stack {
    top: 16px;
    left: 16px;
    width: min(calc(100vw - 92px), 100%);
  }

  .map-loading-banner {
    top: 16px;
    width: min(calc(100vw - 32px), 100%);
  }

  .map-state-block .ds-state-block__action {
    width: 100%;
    justify-content: flex-start;
  }

  .map-state-btn {
    flex: 1 1 auto;
  }

}

/* 弹出面板样式 - 现代化设计 */
.panel-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.panel-content {
  width: 680px;
  max-width: 90vw;
  height: 720px;
  max-height: 90vh;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(24px) saturate(180%);
  border-radius: 24px;
  box-shadow: 
    0 10px 40px rgba(0, 0, 0, 0.15),
    0 0 0 1px rgba(0, 0, 0, 0.04) inset;
  overflow: hidden;
  animation: slideIn 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  border: 1px solid #e2e8f0;
  font-family: -apple-system, 'SF Pro Display', 'PingFang SC', 'Noto Sans SC', sans-serif;
}

.panel-header {
  padding: 28px 32px;
  background: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  border-bottom: 1px solid #e2e8f0;
  border-bottom: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: relative;
  overflow: hidden;
}

.panel-header::before {
  display: none;
  pointer-events: none;
}

.panel-header h3 {
  margin: 0;
  color: #0f172a;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-shadow: none;
  position: relative;
  z-index: 1;
}

.close-btn {
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  font-size: 28px;
  cursor: pointer;
  color: #0f172a;
  padding: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  z-index: 1;
  font-weight: 300;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: rotate(90deg) scale(1.1);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.panel-body {
  padding: 32px;
  flex: 1;
  overflow-y: auto;
  background: transparent;
}

/* 自定义滚动条 */
.panel-body::-webkit-scrollbar {
  width: 8px;
}

.panel-body::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.05);
  border-radius: 10px;
}

.panel-body::-webkit-scrollbar-thumb {
  background: #ffffff;
  border-radius: 10px;
  transition: all 0.3s ease;
}

.panel-body::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%);
}

.panel-section {
  margin-bottom: 32px;
  background: #f8fafc;
  backdrop-filter: blur(10px);
  padding: 24px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.panel-section:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  border-color: rgba(255, 255, 255, 0.12);
}

.panel-section h4 {
  margin: 0 0 8px 0;
  color: #3b82f6;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.3px;
}

.panel-section p {
  margin: 0 0 20px 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.6;
}

.setting-item {
  margin-bottom: 12px;
}

.setting-item label {
  display: flex;
  align-items: center;
  cursor: pointer;
  color: #334155;
}

.setting-item input[type="checkbox"] {
  margin-right: 8px;
}

.panel-btn {
  background: #ffffff;
  color: #334155;
  border: none;
  padding: 12px 24px;
  border-radius: 12px;
  cursor: pointer;
  margin-right: 12px;
  margin-bottom: 12px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  font-weight: 600;
  font-size: 14px;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.panel-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

.panel-btn:active {
  transform: translateY(0);
}

/* 动画效果 */
@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideIn {
  from {
    transform: scale(0.9);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}

/* 数据库更新表单样式 - 现代化设计 */
.update-form {
  background: #f8fafc;
  backdrop-filter: blur(10px);
  padding: 24px;
  border-radius: 16px;
  margin-bottom: 20px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 10px;
  font-weight: 600;
  color: #3b82f6;
  font-size: 14px;
  letter-spacing: 0.3px;
}

.form-group input[type="password"],
.form-group input[type="text"],
.form-group select {
  width: 100%;
  padding: 14px 18px;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  font-size: 15px;
  box-sizing: border-box;
  background: #ffffff;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  color: #0f172a;
}

.form-group input[type="password"]:focus,
.form-group input[type="text"]:focus,
.form-group select:focus {
  outline: none;
  border-color: #3b82f6;
  background: #ffffff;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2), 0 4px 12px rgba(102, 126, 234, 0.15);
  transform: translateY(-1px);
}

.form-group input[type="password"]:disabled,
.form-group input[type="text"]:disabled,
.form-group select:disabled {
  background: #f1f5f9;
  cursor: not-allowed;
  border-color: #e2e8f0;
  color: #94a3b8;
}

.form-hint {
  margin-top: 8px;
  font-size: 13px;
  color: #94a3b8;
  display: flex;
  align-items: center;
  gap: 4px;
  line-height: 1.5;
}

.form-group select option {
  background: #ffffff;
  color: #0f172a;
}

.form-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 24px;
}



.update-btn, .status-btn, .cache-btn, .heatmap-btn, .detection-btn, .stop-btn, .save-config-btn {
  padding: 14px 28px;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 600;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.update-btn::before, .status-btn::before, .cache-btn::before, .heatmap-btn::before,
.detection-btn::before, .stop-btn::before, .save-config-btn::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0;
  height: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  transform: translate(-50%, -50%);
  transition: width 0.6s, height 0.6s;
}

.update-btn:hover::before, .status-btn:hover::before, .cache-btn:hover::before, 
.heatmap-btn:hover::before, .detection-btn:hover::before, .stop-btn:hover::before, .save-config-btn:hover::before {
  width: 300px;
  height: 300px;
}

.update-btn {
  background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
  color: white;
}

.update-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(40, 167, 69, 0.4);
}

.update-btn:active:not(:disabled) {
  transform: translateY(0);
}

.update-btn:disabled {
  background: linear-gradient(135deg, #6c757d 0%, #5a6268 100%);
  cursor: not-allowed;
  opacity: 0.6;
  box-shadow: none;
}

.status-btn {
  background: linear-gradient(135deg, #17a2b8 0%, #138496 100%);
  color: white;
}

.status-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(23, 162, 184, 0.4);
}

.status-btn:disabled {
  background: linear-gradient(135deg, #6c757d 0%, #5a6268 100%);
  cursor: not-allowed;
  opacity: 0.6;
  box-shadow: none;
}

.cache-btn {
  background: linear-gradient(135deg, #ffc107 0%, #ffb300 100%);
  color: #212529;
}

.cache-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(255, 193, 7, 0.4);
}

.heatmap-btn {
  background: #ffffff;
  color: #334155;
}

.heatmap-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

.detection-btn {
  background: #ffffff;
  color: #334155;
}

.detection-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

.detection-btn:disabled {
  background: linear-gradient(135deg, #6c757d 0%, #5a6268 100%);
  cursor: not-allowed;
  opacity: 0.6;
  box-shadow: none;
}

.stop-btn {
  background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
  color: white;
}

.stop-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(220, 53, 69, 0.4);
}

.save-config-btn {
  background: #ffffff;
  color: #334155;
}

.save-config-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

.save-config-btn:disabled {
  background: linear-gradient(135deg, #6c757d 0%, #5a6268 100%);
  cursor: not-allowed;
  opacity: 0.6;
  box-shadow: none;
}

.heatmap-btn:hover {
  background-color: #138496;
}

/* 更新状态显示 - 现代化卡片设计 */
.update-status {
  background: #f8fafc;
  backdrop-filter: blur(10px);
  padding: 24px;
  border-radius: 16px;
  margin-top: 20px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.update-status h5 {
  margin: 0 0 16px 0;
  color: #3b82f6;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.3px;
}

.status-info {
  padding: 20px;
  border-radius: 12px;
  margin-bottom: 16px;
  border: 2px solid;
  position: relative;
  overflow: hidden;
}

.status-info::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, transparent, currentColor, transparent);
  animation: scan 2s ease-in-out infinite;
}

@keyframes scan {
  0%, 100% {
    opacity: 0;
  }
  50% {
    opacity: 1;
  }
}

.status-info.success {
  background: linear-gradient(135deg, rgba(212, 237, 218, 0.6) 0%, rgba(195, 230, 203, 0.4) 100%);
  border-color: #28a745;
  color: #155724;
}

.status-info.success::before {
  background: linear-gradient(90deg, transparent, #28a745, transparent);
}

.status-info.error {
  background: linear-gradient(135deg, rgba(248, 215, 218, 0.6) 0%, rgba(245, 198, 203, 0.4) 100%);
  border-color: #dc3545;
  color: #721c24;
}

.status-info.error::before {
  background: linear-gradient(90deg, transparent, #dc3545, transparent);
}

.status-info.running {
  background: linear-gradient(135deg, rgba(209, 236, 241, 0.6) 0%, rgba(190, 229, 235, 0.4) 100%);
  border-color: #17a2b8;
  color: #0c5460;
}

.status-info.running::before {
  background: linear-gradient(90deg, transparent, #17a2b8, transparent);
}

.status-info p {
  margin: 8px 0;
  font-size: 14px;
  line-height: 1.6;
  font-weight: 500;
}

.status-info p strong {
  color: inherit;
  font-weight: 700;
  margin-right: 8px;
}

/* 进度条样式 - 现代化设计 */
.progress-section {
  margin: 20px 0;
}

.progress-bar-container {
  width: 100%;
  height: 32px;
  background: rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  overflow: hidden;
  position: relative;
  margin-bottom: 12px;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.1);
}

.progress-bar {
  height: 100%;
  background: #ffffff;
  border-radius: 16px;
  transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  min-width: 0;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

.progress-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: white;
  font-size: 14px;
  font-weight: 700;
  text-shadow: 0 1px 3px rgba(0,0,0,0.3);
  letter-spacing: 0.5px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
}

.progress-info span {
  font-weight: 600;
}

/* 进度条动画效果 */
.status-info.running .progress-bar {
  background: linear-gradient(90deg, #3b82f6 0%, #60a5fa 25%, #3b82f6 50%, #60a5fa 75%, #3b82f6 100%);
  background-size: 300% 100%;
  animation: progress-shimmer 3s ease-in-out infinite;
}

@keyframes progress-shimmer {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

@keyframes progress-shimmer {
  0% {
    background-position: -200px 0;
  }
  100% {
    background-position: calc(200px + 100%) 0;
  }
}

/* 成功状态的进度条 */
.status-info.success .progress-bar {
  background: linear-gradient(90deg, #28a745 0%, #20c997 100%);
  animation: none;
}

/* 失败状态的进度条 */
.status-info.error .progress-bar {
  background: linear-gradient(90deg, #dc3545 0%, #e74c3c 100%);
  animation: none;
}

/* 日志显示 */
.update-logs {
  margin-top: 12px;
}

.update-logs details {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px;
}

.update-logs summary {
  cursor: pointer;
  font-weight: 500;
  color: #0f172a;
  padding: 4px 0;
}

.update-logs summary:hover {
  color: #2563eb;
}

.log-section {
  margin-top: 12px;
}

.log-section h6 {
  margin: 0 0 8px 0;
  color: #475569;
  font-size: 14px;
}

.log-content {
  background: #f1f5f9;
  color: #0f172a;
  color: #0f172a;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
  color: #334155;
}

.log-content.error {
  background: #fef2f2;
  border-color: #fecaca;
  color: #dc2626;
}

/* 数据拉取记录样式 */
.records-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 8px 0;
  border-bottom: 1px solid #e2e8f0;
}

.records-header span {
  font-size: 14px;
  color: #64748b;
  font-weight: 500;
}

.delete-all-btn {
  background-color: #dc3545;
  color: white;
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s ease;
}

.delete-all-btn:hover:not(:disabled) {
  background-color: #c82333;
}

.delete-all-btn:disabled {
  background-color: #6c757d;
  cursor: not-allowed;
}

.records-list {
  max-height: 400px;
  overflow-y: auto;
}

.record-item {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 8px;
  transition: all 0.2s ease;
}

.record-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  background: #f8fafc;
}

.record-item.record-success {
  border-left: 4px solid #28a745;
  background: #f0fdf4;
}

.record-item.record-error {
  border-left: 4px solid #dc3545;
  background: #fef2f2;
}

.record-item.record-running {
  border-left: 4px solid #17a2b8;
  background: #ecfeff;
}

.record-item.record-exception {
  border-left: 4px solid #ffc107;
  background: #fefce8;
}

.record-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.record-type {
  font-weight: 600;
  color: #0f172a;
  font-size: 14px;
}

.record-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 500;
}

.record-success .record-status {
  background-color: #d4edda;
  color: #155724;
}

.record-error .record-status {
  background-color: #f8d7da;
  color: #721c24;
}

.record-running .record-status {
  background-color: #d1ecf1;
  color: #0c5460;
}

.record-exception .record-status {
  background-color: #fff3cd;
  color: #856404;
}

.delete-record-btn {
  background: none;
  border: none;
  color: #dc3545;
  font-size: 18px;
  font-weight: bold;
  cursor: pointer;
  padding: 0;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.delete-record-btn:hover {
  background-color: #dc3545;
  color: white;
}

.record-message {
  color: #64748b;
  font-size: 13px;
  line-height: 1.4;
  margin-bottom: 6px;
}

.record-time {
  color: #94a3b8;
  font-size: 12px;
}

.record-details {
  margin-top: 8px;
}

.record-details details {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 6px;
}

.record-details summary {
  cursor: pointer;
  font-size: 12px;
  color: #3b82f6;
  font-weight: 500;
}

.record-details summary:hover {
  color: #a78bfa;
}

.details-content {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #eee;
}

.detail-item {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
  word-break: break-word;
}

.detail-item strong {
  color: #333;
}

.no-records {
  text-align: center;
  color: #999;
  font-style: italic;
  padding: 20px;
}

.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #e9ecef;
}

.pagination button {
  background-color: #4a90e2;
  color: white;
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s ease;
}

.pagination button:hover:not(:disabled) {
  background-color: #357abd;
}

.pagination button:disabled {
  background-color: #6c757d;
  cursor: not-allowed;
}

.page-info {
  font-size: 12px;
  color: #666;
}

/* 加载圆圈动画 */
.loading-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid #f3f3f3;
  border-top: 2px solid #4a90e2;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-right: 8px;
  vertical-align: middle;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* 自动清除缓存样式 */
.auto-cache-clear {
  background-color: #e8f4f8;
  padding: 16px;
  border-radius: 8px;
  margin-top: 16px;
  border-left: 4px solid #17a2b8;
}

.auto-cache-clear h5 {
  margin: 0 0 12px 0;
  color: #0c5460;
}

.cache-clear-info {
  display: flex;
  align-items: center;
}

.cache-clear-spinner {
  display: flex;
  align-items: center;
  color: #0c5460;
  font-size: 14px;
}

.cache-clear-spinner .loading-spinner {
  border-top-color: #17a2b8;
  margin-right: 12px;
}

/* 缓存按钮禁用状态 */
.cache-btn:disabled {
  background-color: #6c757d;
  cursor: not-allowed;
  opacity: 0.6;
}

.cache-btn:disabled:hover {
  background-color: #6c757d;
}

/* 标签页样式 - 现代化pill设计 */
.panel-tabs {
  display: flex;
  gap: 12px;
  padding: 20px 32px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  margin-bottom: 0;
}

.tab-button {
  flex: 1;
  padding: 14px 24px;
  text-align: center;
  cursor: pointer;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #64748b;
  font-size: 15px;
  font-weight: 600;
  transition: all 0.2s ease;
  border-radius: 8px;
}

.tab-button:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.tab-button.active {
  background: #ffffff;
  color: #2563eb;
  border-color: #bfdbfe;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

.tab-content {
  animation: fadeIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 探测任务表单样式 */
.detection-form {
  background: #f8fafc;
  backdrop-filter: blur(10px);
  padding: 24px;
  border-radius: 16px;
  margin-bottom: 20px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.detection-form .form-group {
  margin-bottom: 12px;
}

.detection-form label {
  display: block;
  margin-bottom: 4px;
  font-weight: 500;
  color: #475569;
}

.detection-form select,
.detection-form input[type="text"] {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
  background: #ffffff;
  color: #0f172a;
}

.detection-form select:focus,
.detection-form input[type="text"]:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2);
}

.detection-form select:disabled,
.detection-form input[type="text"]:disabled {
  background-color: #f5f5f5;
  cursor: not-allowed;
}

.detection-btn {
  background-color: #28a745;
  color: white;
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s ease;
}

.detection-btn:hover:not(:disabled) {
  background-color: #218838;
}

.detection-btn:disabled {
  background-color: #6c757d;
  cursor: not-allowed;
}

.stop-btn {
  background-color: #dc3545;
  color: white;
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s ease;
}

.stop-btn:hover {
  background-color: #c82333;
}

/* 探测进度样式 */
.detection-progress {
  background-color: #e3f2fd;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  border-left: 4px solid #2196f3;
}

.detection-progress h5 {
  margin: 0 0 12px 0;
  color: #1976d2;
}

.current-task {
  margin-top: 8px;
  font-size: 14px;
  color: #1976d2;
  font-weight: 500;
}

/* 探测日志样式 */
.detection-logs {
  background-color: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
}

.detection-logs h5 {
  margin: 0 0 12px 0;
  color: #333;
}

.logs-container {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid #e9ecef;
  border-radius: 4px;
  background-color: white;
}

.no-logs {
  padding: 20px;
  text-align: center;
  color: #6c757d;
  font-style: italic;
}

.log-list {
  padding: 8px;
}

.log-item {
  padding: 8px 12px;
  border-bottom: 1px solid #f1f3f4;
  font-size: 13px;
  line-height: 1.4;
}

.log-item:last-child {
  border-bottom: none;
}

.log-item.info {
  border-left: 3px solid #17a2b8;
  background-color: #f7f9fa;
}

.log-item.success {
  border-left: 3px solid #28a745;
  background-color: #f8fff9;
}

.log-item.warning {
  border-left: 3px solid #ffc107;
  background-color: #fffef7;
}

.log-item.error {
  border-left: 3px solid #dc3545;
  background-color: #fef8f8;
}

.log-time {
  font-size: 11px;
  color: #6c757d;
  margin-bottom: 2px;
}

.log-message {
  font-weight: 500;
  color: #495057;
  margin-bottom: 2px;
}

.log-details {
  font-size: 12px;
  color: #6c757d;
  font-style: italic;
}
</style> 
