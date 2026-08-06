<template>
  <div class="terminal-sidebar ds-sidebar-shell" :class="{ collapsed: !expanded, expanded }">
    <div class="toggle-button" @click="toggleSidebar">
      <CaretLeftOutlined v-if="expanded" />
      <CaretRightOutlined v-else />
    </div>

    <div v-show="expanded" class="sidebar-content">
      <PageHeader
        class="terminal-page-header"
        eyebrow="Terminal Explorer"
        title="终端设备列表"
        description="按国家、地区和城市筛选终端设备，并与地图联动定位。"
      >
        <template #meta>
          <span class="ds-status-pill ds-badge-info">{{ displayTotalFilteredCount }} 台设备</span>
        </template>
      </PageHeader>

      <div class="terminal-filter-panel ds-panel-card">
        <div class="ds-section-title">
          <div>
            <h3 class="ds-section-title__text">筛选条件</h3>
            <p class="ds-section-title__hint">按国家 / 地区与城市联动筛选终端设备</p>
          </div>
        </div>

        <div class="filter-container">
          <div class="filter-item ds-field">
            <label class="u-sr-only" for="terminal-ip-search">搜索终端设备</label>
            <a-input-search
              id="terminal-ip-search"
              v-model:value="searchKeyword"
              name="terminal_ip_search"
              autocomplete="off"
              allow-clear
              aria-label="按 IP、国家、地区或城市搜索终端设备"
              placeholder="搜索 IP / 国家 / 地区 / 城市"
              @search="handleTerminalSearch"
            />
          </div>

          <div class="filter-item ds-field">
            <div class="filter-label ds-field-label">国家 / 地区</div>
            <a-select
              v-model:value="selectedCountry"
              show-search
              placeholder="选择或输入国家 / 地区"
              :filter-option="filterOption"
              style="width: 100%"
              allow-clear
              @change="handleCountryChange"
            >
              <a-select-option v-for="country in countryOptions" :key="country.value" :value="country.value">
                {{ country.label }} ({{ country.count }})
              </a-select-option>
            </a-select>
          </div>

          <div class="filter-item ds-field">
            <div class="filter-label ds-field-label">城市</div>
            <a-select
              v-model:value="selectedCity"
              show-search
              placeholder="选择或输入城市"
              :filter-option="filterOption"
              style="width: 100%"
              allow-clear
              :disabled="!selectedCountry"
              @change="handleCityChange"
            >
              <a-select-option v-for="city in cityOptions" :key="city.value" :value="city.value">
                {{ city.label }} ({{ city.count }})
              </a-select-option>
            </a-select>
          </div>
        </div>
      </div>

      <PanelCard v-if="displayedTerminals.length > 0" class="terminal-stats-card">
        <template #header>
          <div class="ds-section-title">
            <div>
              <h3 class="ds-section-title__text">当前范围</h3>
              <p class="ds-section-title__hint">当前筛选条件下的终端概览</p>
            </div>
          </div>
        </template>

        <div class="terminal-stats">
          <div class="stat-item stat-item--metric ds-stat-card">
            <div class="stat-value">{{ displayTotalFilteredCount }}</div>
            <div class="stat-label">设备数</div>
          </div>
          <div v-if="selectedCountry" class="stat-item stat-item--text ds-stat-card">
            <div class="stat-value">{{ selectedCountry }}</div>
            <div class="stat-label">国家 / 地区</div>
          </div>
          <div v-if="selectedCity" class="stat-item stat-item--text ds-stat-card">
            <div class="stat-value">{{ selectedCity }}</div>
            <div class="stat-label">城市</div>
          </div>
        </div>
      </PanelCard>

      <StateBlock
        v-if="isLoading"
        type="loading"
        title="终端列表加载中"
        description="正在同步当前筛选条件下的终端设备。"
      >
        <template #action>
          <a-spin />
        </template>
      </StateBlock>

      <StateBlock
        v-else-if="totalFilteredCount === 0 && hasActiveFilters"
        type="empty"
        title="没有匹配结果"
        description="当前筛选条件下没有找到终端设备。"
      />

      <StateBlock
        v-else-if="totalFilteredCount === 0"
        type="info"
        title="请选择筛选条件"
        description="先选择国家 / 地区和城市，再查看终端设备列表。"
      />

      <template v-else>
        <div class="terminal-list">
          <div
            v-for="terminal in displayedTerminals"
            :key="terminal.ip || terminal.key"
            class="terminal-item ds-surface-card"
            :class="{ selected: selectedTerminal && selectedTerminal.ip === terminal.ip }"
            @click="selectTerminal(terminal)"
          >
            <div class="terminal-ip">{{ terminal.ip }}</div>
            <div class="terminal-meta">
              <div class="terminal-location">
                <EnvironmentOutlined />
                {{ terminal.country }} - {{ terminal.city }}
              </div>
              <div v-if="dbTimestamp" class="terminal-time">
                <ClockCircleOutlined />
                {{ dbTimestamp }}
              </div>
            </div>
          </div>
        </div>

        <div v-if="totalFilteredCount > displayedTerminals.length" class="pagination ds-page-toolbar">
          <div class="pagination-info">
            显示 {{ displayedTerminals.length }} / {{ displayTotalFilteredCount }} 条
          </div>
          <a-button
            v-if="displayedTerminals.length < totalFilteredCount"
            class="ds-btn-secondary"
            @click="loadMoreTerminals"
          >
            加载更多
          </a-button>
        </div>
      </template>
    </div>

    <div v-if="selectedTerminal && expanded" class="terminal-details ds-sidebar-shell ds-panel-card">
      <div class="details-header">
        <h3>设备详情</h3>
        <a-button type="link" @click="closeDetails">
          <CloseOutlined />
        </a-button>
      </div>

      <div class="details-content">
        <div class="detail-item">
          <div class="detail-label">IP 地址</div>
          <div class="detail-value">{{ selectedTerminal.ip }}</div>
        </div>
        <div class="detail-item">
          <div class="detail-label">国家 / 地区</div>
          <div class="detail-value">{{ selectedTerminal.country }}</div>
        </div>
        <div class="detail-item">
          <div class="detail-label">省份 / 州</div>
          <div class="detail-value">{{ selectedTerminal.region }}</div>
        </div>
        <div class="detail-item">
          <div class="detail-label">城市</div>
          <div class="detail-value">{{ selectedTerminal.city }}</div>
        </div>
        <div class="detail-item">
          <div class="detail-label">经度</div>
          <div class="detail-value">{{ selectedTerminal.lng }}</div>
        </div>
        <div class="detail-item">
          <div class="detail-label">纬度</div>
          <div class="detail-value">{{ selectedTerminal.lat }}</div>
        </div>

        <a-button type="primary" class="locate-button ds-btn-primary" @click="locateOnMap(selectedTerminal)">
          <AimOutlined /> 在地图上定位
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, onUnmounted, ref, watch } from 'vue';
import { Button as AButton, Input as AInput, Select as ASelect, Spin as ASpin } from 'ant-design-vue';
import {
  AimOutlined,
  CaretLeftOutlined,
  CaretRightOutlined,
  ClockCircleOutlined,
  CloseOutlined,
  EnvironmentOutlined,
} from '@ant-design/icons-vue';
import { fetchDevices } from '../api/devices.js';
import { withTerminalDeviceDisplayOffset } from '../constants/deviceDisplay.js';
import { notify } from '../utils/notify.js';
import PageHeader from './ui/PageHeader.vue';
import PanelCard from './ui/PanelCard.vue';
import StateBlock from './ui/StateBlock.vue';

const ASelectOption = ASelect.Option;
const AInputSearch = AInput.Search;
const emit = defineEmits(['locate-terminal', 'sidebar-expanded-change']);
const highlightDevice = inject('highlightDevice');
const activeSnapshot = inject('snapshot', ref(null));

const expanded = ref(false);
const searchKeyword = ref('');
const selectedCountry = ref(null);
const selectedCity = ref(null);
const selectedTerminal = ref(null);
const isLoading = ref(false);
const dbTimestamp = ref('');

const pageSize = 100;
const currentPage = ref(1);
const displayedTerminals = ref([]);
const totalFilteredCount = ref(0);
const countryStats = ref({});
const cityStats = ref({});

let latestDevicesRequestId = 0;
let activeDevicesAbortController = null;

const normalizedSearchKeyword = computed(() => searchKeyword.value.trim());
const hasActiveFilters = computed(() => Boolean(
  normalizedSearchKeyword.value || selectedCountry.value || selectedCity.value
));
const isGlobalTerminalScope = computed(() => !hasActiveFilters.value);
const displayTotalFilteredCount = computed(() => (
  isGlobalTerminalScope.value
    ? withTerminalDeviceDisplayOffset(totalFilteredCount.value)
    : totalFilteredCount.value
));

const countryOptions = computed(() => Object.keys(countryStats.value)
  .filter((country) => country && country !== '-')
  .map((country) => ({
    value: country,
    label: country,
    count: countryStats.value[country],
  }))
  .sort((a, b) => a.label.localeCompare(b.label)));

const cityOptions = computed(() => {
  if (!selectedCountry.value) return [];
  return Object.keys(cityStats.value)
    .filter((city) => city && city !== '-')
    .map((city) => ({
      value: city,
      label: city,
      count: cityStats.value[city],
    }))
    .sort((a, b) => a.label.localeCompare(b.label));
});

const startDevicesRequest = () => {
  activeDevicesAbortController?.abort();
  activeDevicesAbortController = new globalThis.AbortController();
  latestDevicesRequestId += 1;
  return {
    requestId: latestDevicesRequestId,
    signal: activeDevicesAbortController.signal,
  };
};

const isLatestDevicesRequest = (requestId) => requestId === latestDevicesRequestId;

const clearActiveDevicesAbortController = (signal) => {
  if (activeDevicesAbortController?.signal === signal) {
    activeDevicesAbortController = null;
  }
};

const updateListStats = (data) => {
  totalFilteredCount.value = data.total || 0;
  dbTimestamp.value = data.dbTimestamp || dbTimestamp.value || '';
};

const locateOnMap = (location) => {
  if (location?.ip) {
    emit('locate-terminal', {
      location: {
        lng: location.lng,
        lat: location.lat,
        zoom: 10,
      },
      selection: {
        id: location.ip,
        type: 'terminal',
        typeLabel: '终端设备',
        name: location.ip,
        subtitle: [location.country, location.city].filter(Boolean).join(' / '),
        sourceLabel: '终端侧栏',
      },
    });
    return;
  }
  emit('locate-terminal', location);
};

const focusTerminals = (items, zoom) => {
  if (!items.length) return;
  const sample = items.slice(0, 50);
  const avgLat = sample.reduce((sum, item) => sum + Number(item.lat || 0), 0) / sample.length;
  const avgLng = sample.reduce((sum, item) => sum + Number(item.lng || 0), 0) / sample.length;
  locateOnMap({ lat: avgLat, lng: avgLng, zoom });
};

const runDeviceQuery = async (params, {
  append = false,
  onSuccess = null,
  errorMessage = '加载终端列表失败，请稍后重试',
} = {}) => {
  const { requestId, signal } = startDevicesRequest();
  isLoading.value = true;

  try {
    const data = await fetchDevices(params, { signal });
    if (!isLatestDevicesRequest(requestId)) {
      return false;
    }

    updateListStats(data);
    displayedTerminals.value = append
      ? displayedTerminals.value.concat(data.items || [])
      : (data.items || []);

    onSuccess?.(data);
    return true;
  } catch (error) {
    if (error?.code === 'REQUEST_ABORTED') {
      return false;
    }
    if (!isLatestDevicesRequest(requestId)) {
      return false;
    }
    console.error('加载终端设备数据失败:', error);
    notify.error(error?.message || errorMessage);
    return false;
  } finally {
    if (isLatestDevicesRequest(requestId)) {
      isLoading.value = false;
    }
    clearActiveDevicesAbortController(signal);
  }
};

const toggleSidebar = () => {
  expanded.value = !expanded.value;
  emit('sidebar-expanded-change', expanded.value);
  if (!expanded.value) {
    selectedTerminal.value = null;
  }
};

const closeDetails = () => {
  selectedTerminal.value = null;
};

const handleCountryChange = async (value) => {
  selectedCountry.value = value;
  selectedCity.value = null;
  currentPage.value = 1;
  displayedTerminals.value = [];

  const params = {
    page: 1,
    pageSize,
    country: value || '',
    keyword: normalizedSearchKeyword.value,
  };
  if (activeSnapshot.value) params.snapshot = activeSnapshot.value;

  await runDeviceQuery(params, {
    onSuccess: (data) => {
      countryStats.value = data.countryStats || {};
      cityStats.value = data.cityStats || {};
      focusTerminals(data.items || [], 4);
    },
    errorMessage: '按国家筛选终端失败，请稍后重试',
  });
};

const handleCityChange = async (value) => {
  selectedCity.value = value;
  currentPage.value = 1;
  displayedTerminals.value = [];

  const params = {
    page: 1,
    pageSize,
    country: selectedCountry.value || '',
    city: value || '',
    keyword: normalizedSearchKeyword.value,
  };
  if (activeSnapshot.value) params.snapshot = activeSnapshot.value;

  await runDeviceQuery(params, {
    onSuccess: (data) => {
      const first = data.items?.[0];
      if (first) {
        locateOnMap({ lat: first.lat, lng: first.lng, zoom: 10 });
      }
    },
    errorMessage: '按城市筛选终端失败，请稍后重试',
  });
};

const loadFilteredTerminals = async (append = false, pageOverride = currentPage.value) => {
  const params = {
    page: pageOverride,
    pageSize,
    country: selectedCountry.value || '',
    city: selectedCity.value || '',
    keyword: normalizedSearchKeyword.value,
  };
  if (activeSnapshot.value) params.snapshot = activeSnapshot.value;

  return runDeviceQuery(params, {
    append,
    errorMessage: append ? '加载更多终端失败，请稍后重试' : '加载终端列表失败，请稍后重试',
  });
};

const loadMoreTerminals = async () => {
  const nextPage = currentPage.value + 1;
  const appended = await loadFilteredTerminals(true, nextPage);
  if (appended) {
    currentPage.value = nextPage;
  }
};

const loadTerminalData = async () => {
  currentPage.value = 1;
  const params = {
    page: 1,
    pageSize,
    country: selectedCountry.value || '',
    city: selectedCity.value || '',
    keyword: normalizedSearchKeyword.value,
  };
  if (activeSnapshot.value) params.snapshot = activeSnapshot.value;

  await runDeviceQuery(params, {
    onSuccess: (data) => {
      countryStats.value = data.countryStats || {};
      cityStats.value = data.cityStats || {};
    },
    errorMessage: '加载终端列表失败，请稍后重试',
  });
};

const handleTerminalSearch = () => {
  selectedTerminal.value = null;
  currentPage.value = 1;
  displayedTerminals.value = [];
  void loadTerminalData();
};

const selectTerminal = (terminal) => {
  if (selectedTerminal.value && selectedTerminal.value.ip === terminal.ip) {
    selectedTerminal.value = null;
    highlightDevice?.(null);
    return;
  }

  selectedTerminal.value = terminal;
  highlightDevice?.({
    longitude: Number.parseFloat(terminal.lng),
    latitude: Number.parseFloat(terminal.lat),
    ip: terminal.ip,
    country: terminal.country,
    city: terminal.city,
    sourceLabel: '终端侧栏',
  });
};

const handleCacheCleared = () => {
  void loadTerminalData();
};

const filterOption = (input, option) => {
  const value = option?.value || '';
  return value.toLowerCase().includes(String(input || '').toLowerCase());
};

watch(activeSnapshot, () => {
  selectedCountry.value = null;
  selectedCity.value = null;
  selectedTerminal.value = null;
  displayedTerminals.value = [];
  void loadTerminalData();
});

onMounted(() => {
  void loadTerminalData();
  window.addEventListener('cache-cleared', handleCacheCleared);
  emit('sidebar-expanded-change', expanded.value);
});

onUnmounted(() => {
  activeDevicesAbortController?.abort();
  window.removeEventListener('cache-cleared', handleCacheCleared);
  emit('sidebar-expanded-change', false);
});
</script>

<style scoped>
.terminal-sidebar {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 10;
  height: 100vh;
  width: 320px;
  transition: width 0.3s ease;
  font-family: 'Plus Jakarta Sans', 'Segoe UI', 'PingFang SC', 'Noto Sans SC', sans-serif;
}

.terminal-sidebar.collapsed {
  width: 40px;
  overflow: visible;
}

.terminal-sidebar.expanded {
  width: 320px;
}

.toggle-button {
  position: absolute;
  top: 50%;
  right: -18px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
}

.sidebar-content {
  height: 100%;
  padding: 12px 10px 10px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.terminal-page-header {
  padding: 12px;
}

.terminal-page-header :deep(.ds-page-header__title) {
  font-size: 22px;
}

.terminal-page-header :deep(.ds-page-header__description) {
  font-size: 12px;
}

.terminal-filter-panel,
.terminal-stats-card {
  gap: 0;
}

.terminal-filter-panel :deep(.panel-card__body),
.terminal-stats-card :deep(.panel-card__body) {
  padding: 10px;
}

.filter-container {
  display: grid;
  gap: 8px;
}

.filter-item {
  min-width: 0;
}

.terminal-filter-panel :deep(.ant-select-selector) {
  min-height: 38px;
  border-radius: 12px !important;
  border-color: var(--ds-border-soft) !important;
  box-shadow: none !important;
}

.terminal-filter-panel :deep(.ant-input-group-wrapper),
.terminal-filter-panel :deep(.ant-input-affix-wrapper),
.terminal-filter-panel :deep(.ant-input),
.terminal-filter-panel :deep(.ant-input-search-button) {
  border-radius: 12px !important;
}

.terminal-filter-panel :deep(.ant-input-affix-wrapper),
.terminal-filter-panel :deep(.ant-input-search-button) {
  border-color: var(--ds-border-soft) !important;
  box-shadow: none !important;
}

.terminal-filter-panel :deep(.ant-select-focused .ant-select-selector) {
  border-color: var(--ds-primary-500) !important;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12) !important;
}

.terminal-stats {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.stat-item {
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 4px;
  padding: 12px 14px;
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--ds-text-strong);
  line-height: 1.35;
  text-align: left;
  word-break: break-word;
  width: 100%;
}

.stat-item--metric .stat-value {
  font-size: 22px;
}

.stat-label {
  margin-top: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--ds-text-secondary);
  line-height: 1.5;
}

.terminal-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.terminal-item {
  padding: 8px 10px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.terminal-item:hover,
.terminal-item.selected {
  border-color: rgba(37, 99, 235, 0.35);
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.08);
}

.terminal-ip {
  font-weight: 700;
  color: var(--ds-text-strong);
  word-break: break-all;
}

.terminal-meta {
  margin-top: 4px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  color: var(--ds-text-secondary);
  font-size: 12px;
}

.terminal-location,
.terminal-time {
  display: flex;
  align-items: center;
  gap: 6px;
}

.pagination {
  margin-top: 10px;
}

.pagination-info {
  font-size: 12px;
  color: var(--ds-text-secondary);
}

.terminal-details {
  position: absolute;
  left: 320px;
  top: 50%;
  transform: translateY(-50%);
  width: 280px;
  padding: 18px;
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.12);
}

.details-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}

.details-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
}

.details-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detail-item {
  display: grid;
  grid-template-columns: 84px 1fr;
  gap: 10px;
}

.detail-label {
  font-size: 12px;
  color: var(--ds-text-secondary);
}

.detail-value {
  min-width: 0;
  font-size: 13px;
  color: var(--ds-text-primary);
  word-break: break-all;
}

.locate-button {
  margin-top: 10px;
}

@media (max-width: 960px) {
  .terminal-sidebar.expanded {
    width: 288px;
  }

  .terminal-details {
    left: 288px;
    width: 240px;
  }
}
</style>
