<template>
  <div ref="infoContainerRef" class="info-container info-workbench">
    <PageHeader
      class="info-page-header"
      eyebrow="Analysis Workspace"
      title="数据分析面板"
      description="统一查看终端设备、IPv4 网段与网络分布数据。"
    >
      <template #meta>
        <span class="ds-status-pill ds-badge-info">当前快照：{{ activeSnapshotLabel }}</span>
        <span class="ds-status-pill">{{ activeTab === 'terminal' ? '终端分析' : 'IPv4 分析' }}</span>
      </template>
    </PageHeader>

    <!-- 閺嶅洨顒锋い闈涘瀼閹?-->
    <PanelCard class="info-tabs-shell" as="section">
      <a-tabs v-model:active-key="activeTab" class="modern-tabs" size="large">
        <!-- 缂佸牏顏拋鎯ь槵閸掑棙鐎介弽鍥╊劮妞?-->
        <a-tab-pane key="terminal">
          <template #tab>
            <span class="tab-label">
              <rocket-outlined class="tab-icon" />
              <span>终端设备分析</span>
            </span>
          </template>
          <!-- 缂佺喕顓搁崡锛勫 -->
          <div class="stats-summary ds-stat-grid">
            <div class="stat-card stat-primary ds-stat-card">
              <div class="stat-icon-wrapper">
                <rocket-outlined class="stat-icon" />
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ formatNumber(displayTotalDevices) }}</div>
                <div class="stat-label">总设备数</div>
              </div>
            </div>
            <div class="stat-card stat-success ds-stat-card">
              <div class="stat-icon-wrapper">
                <global-outlined class="stat-icon" />
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ countryCount }}</div>
                <div class="stat-label">覆盖国家/地区</div>
              </div>
            </div>
            <div class="stat-card stat-warning ds-stat-card">
              <div class="stat-icon-wrapper">
                <environment-outlined class="stat-icon" />
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ cityCount }}</div>
                <div class="stat-label">覆盖城市</div>
              </div>
            </div>
          </div>

          <StateBlock
            v-if="hasTerminalLoadErrors"
            class="panel-feedback"
            type="error"
            title="终端数据加载失败"
            description="部分终端分析模块未完成加载，请重试失败模块。"
          >
            <div class="panel-feedback-list">
              <div v-for="item in terminalErrorSummary" :key="item.key" class="panel-feedback-item">
                <div class="panel-feedback-item-copy">
                  <strong>{{ item.title }}</strong>
                  <span>{{ item.message }}</span>
                </div>
                <a-button size="small" @click="item.action()">重试</a-button>
              </div>
            </div>
            <template #action>
              <a-button type="primary" size="small" @click="retryTerminalPanels">重试全部</a-button>
            </template>
          </StateBlock>

          <!-- 閸愬懎顔愰崠鍝勭厵 -->
          <div class="content-layout">
            <!-- 瀹革缚鏅?- 閸ユ崘銆冮崠鍝勭厵 -->
            <div class="left-panel">
              <div class="chart-card ds-panel-card info-panel-card">
                <div class="chart-header">
                  <h3>设备分布统计</h3>
                  <span class="chart-subtitle">Top 10 国家/地区</span>
                </div>
                <div ref="deviceChartRef" class="chart-container"></div>
              </div>
              
              <div class="chart-card ds-panel-card info-panel-card">
                <div class="chart-header">
                  <h3>地面站分布</h3>
                  <span class="chart-subtitle">按国家统计</span>
                </div>
                <div ref="stationChartRef" class="chart-container"></div>
              </div>
              
              <div class="chart-card ds-panel-card info-panel-card">
                <div class="chart-header">
                  <h3>PoP 节点分布</h3>
                  <span class="chart-subtitle">全球覆盖情况</span>
                </div>
                <div ref="popChartRef" class="chart-container"></div>
              </div>
            </div>
            
            <!-- 閸欏厖鏅?- 閺佺増宓佺悰銊︾壐 -->
            <div class="right-panel">
              <div class="data-card ds-panel-card ds-table-shell info-panel-card">
                <div class="card-header">
                  <h3>终端设备列表</h3>
                </div>
                <PageToolbar class="table-actions info-table-toolbar">
                  <label class="u-sr-only" for="info-device-search">搜索终端设备</label>
                  <a-input-search
                    id="info-device-search"
                    v-model:value="searchKeyword"
                    name="device_search"
                    size="large"
                    autocomplete="off"
                    aria-label="搜索终端设备"
                    placeholder="搜索 IP / 国家 / 地区 / 城市（支持组合搜索）"
                    @search="onSearch"
                  />
                </PageToolbar>
                <a-table
                  :data-source="displayedData"
                  :columns="columns"
                  :loading="loading"
                  :pagination="pagination"
                  @change="handleTableChange"
                >
                  <template #bodyCell="{ column, record }">
                    <template v-if="column.key === 'action'">
                      <a class="action-link" @click="locateOnMap(record)">定位</a>
                    </template>
                  </template>
                </a-table>
              </div>
            </div>
          </div>
        </a-tab-pane>

        <!-- IPv4 缂冩垶顔岄崚鍡樼€介弽鍥╊劮妞?-->
        <a-tab-pane key="ipv4">
          <template #tab>
            <span class="tab-label">
              <global-outlined class="tab-icon" />
              <span>IPv4 网段分析</span>
            </span>
          </template>
          <!-- IPv4 缂佺喕顓搁崡锛勫 -->
          <div class="stats-summary ds-stat-grid">
            <div class="stat-card stat-info ds-stat-card">
              <div class="stat-icon-wrapper">
                <global-outlined class="stat-icon" />
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ formatNumber(totalIpSegments) }}</div>
                <div class="stat-label">IP 网段总数</div>
              </div>
            </div>
            <div class="stat-card stat-success ds-stat-card">
              <div class="stat-icon-wrapper">
                <environment-outlined class="stat-icon" />
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ formatNumber(totalIpCount) }}</div>
                <div class="stat-label">IP 地址总数</div>
              </div>
            </div>
          </div>

          <StateBlock
            v-if="ipError"
            class="panel-feedback"
            type="error"
            title="IPv4 数据加载失败"
            :description="ipError"
          >
            <template #action>
              <a-button type="primary" size="small" @click="loadIpData">重试</a-button>
            </template>
          </StateBlock>

          <StateBlock
            v-if="fofaError"
            class="panel-feedback"
            type="error"
            title="FOFA 数据加载失败"
            :description="fofaError"
          >
            <template #action>
              <a-button type="primary" size="small" @click="loadFofaData">重试</a-button>
            </template>
          </StateBlock>

          <!-- IPv4 閸愬懎顔愰崠鍝勭厵 -->
          <div class="content-layout">
            <!-- 瀹革缚鏅?- IPv4 閸ユ崘銆?-->
            <div class="left-panel">
              <div class="chart-card ds-panel-card info-panel-card">
                <div class="chart-header">
                  <h3>IP 网段 CIDR 分布</h3>
                  <span class="chart-subtitle">按 CIDR 段统计</span>
                </div>
                <div ref="ipSegmentChartRef" class="chart-container"></div>
              </div>
              
              <div class="chart-card ds-panel-card info-panel-card">
                <div class="chart-header">
                  <h3>IP 地址数量分布</h3>
                  <span class="chart-subtitle">按 CIDR 段统计 IP 总数</span>
                </div>
                <div ref="ipCountChartRef" class="chart-container"></div>
              </div>
              
              <div class="chart-card ds-panel-card info-panel-card">
                <div class="chart-header">
                  <h3>网段大小分布</h3>
                  <span class="chart-subtitle">CIDR 段位统计</span>
                </div>
                <div ref="cidrDistChartRef" class="chart-container"></div>
              </div>
            </div>
            
            <!-- 閸欏厖鏅?- IPv4 閺佺増宓佺悰銊︾壐 -->
            <div class="right-panel">
              <div class="data-card ds-panel-card ds-table-shell info-panel-card">
                <div class="card-header">
                  <h3>IPv4 网段列表</h3>
                </div>
                <PageToolbar class="table-actions info-table-toolbar">
                  <label class="u-sr-only" for="info-ip-search">搜索 IPv4 网段</label>
                  <a-input-search
                    id="info-ip-search"
                    v-model:value="ipSearchKeyword"
                    name="ip_segment_search"
                    size="large"
                    autocomplete="off"
                    aria-label="搜索 IPv4 网段"
                    placeholder="搜索 IP 网段（支持网段、描述、扫描结果）"
                    @search="onIpSearch"
                  />
                </PageToolbar>
                <a-table
                  :data-source="displayedIpData"
                  :columns="ipColumns"
                  :loading="ipLoading"
                  :pagination="ipPagination"
                  :scroll="{ x: 1200 }"
                  @change="handleIpTableChange"
                >
                  <template #bodyCell="{ column, record }">
                    <template v-if="column.key === 'description'">
                      <a-tooltip :title="record.description">
                        <span class="ellipsis-text">{{ record.description }}</span>
                      </a-tooltip>
                    </template>
                    <template v-else-if="column.key === 'scanResult'">
                      <a-tag 
                        :color="getScanResultColor(record.scanResult)"
                        style="cursor: pointer;"
                        @click="showScanReport(record)"
                      >
                        {{ record.scanResult }}
                      </a-tag>
                    </template>
                  </template>
                </a-table>
              </div>

              <div class="info-fofa-shell ds-panel-card">
                <InfoFofaPanel
                  :loading="fofaLoading"
                  :search-keyword="fofaSearchKeyword"
                  :displayed-data="displayedFofaData"
                  :pagination="fofaPagination"
                  @update:search-keyword="(value) => (fofaSearchKeyword = value)"
                  @search="onFofaSearch"
                  @view-detail="viewFofaDetail"
                  @page-change="handleFofaPageChange"
                  @page-size-change="handleFofaPageSizeChange"
                />
              </div>
            </div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </PanelCard>

  <InfoFofaDetailModal
    :open="fofaDetailVisible"
    :item="selectedFofaItem"
    @close="closeFofaDetail"
  />

  <InfoScanReportModal
    :open="scanReportVisible"
    :loading="scanReportLoading"
    :selected-ip-segment="selectedIpSegment"
    :scan-report-data="scanReportData"
    :filtered-scan-report-data="filteredScanReportData"
    :scan-report-columns="scanReportColumns"
    :get-risk-color="getRiskColor"
    @close="closeScanReport"
    @filter-by-threat-level="filterScanReportByThreatLevel"
    @reset-filter="resetScanReportFilter"
  />
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, reactive, nextTick, watch, inject } from 'vue';
import {
  Button as AButton,
  Input as AInput,
  Table as ATable,
  Tabs as ATabs,
  Tag as ATag,
  Tooltip as ATooltip,
} from 'ant-design-vue';
import { 
  RocketOutlined, 
  GlobalOutlined, 
  EnvironmentOutlined
} from '@ant-design/icons-vue';
import { message } from 'ant-design-vue';
import * as echarts from 'echarts/core';
import { BarChart, LineChart, PieChart } from 'echarts/charts';
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  ToolboxComponent
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { getChineseCountryName } from '../utils/stationNameMapping';
import { fetchDevices } from '../api/devices.js';
import { withTerminalDeviceDisplayOffset } from '../constants/deviceDisplay.js';
import { buildRenderedGatewayFeatures } from '../utils/starlinkGatewayData.js';
import {
  buildRenderedPopFeatures,
  computeRenderedPopCountryStats,
} from '../utils/starlinkRenderedData.js';
import {
  getPopCountryChineseName,
} from '../utils/infoDataParsers.js';
import { useInfoFofaData } from '../composables/useInfoFofaData.js';
import { useInfoFofaDetailModal } from '../composables/useInfoFofaDetailModal.js';
import { useInfoScanReport } from '../composables/useInfoScanReport.js';
import { useInfoIpv4Data } from '../composables/useInfoIpv4Data.js';
import { useInfoChartLifecycle } from '../composables/useInfoChartLifecycle.js';
import { useInfoTerminalCharts } from '../composables/useInfoTerminalCharts.js';
import { useInfoIpv4Charts } from '../composables/useInfoIpv4Charts.js';
import InfoFofaPanel from './InfoFofaPanel.vue';
import InfoFofaDetailModal from './InfoFofaDetailModal.vue';
import InfoScanReportModal from './InfoScanReportModal.vue';
import PageHeader from './ui/PageHeader.vue';
import PageToolbar from './ui/PageToolbar.vue';
import PanelCard from './ui/PanelCard.vue';
import StateBlock from './ui/StateBlock.vue';

const AInputSearch = AInput.Search;
const ATabPane = ATabs.TabPane;

// 濞夈劌鍞?ECharts 缂佸嫪娆?
echarts.use([
  BarChart,
  LineChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  ToolboxComponent,
  CanvasRenderer,
]);

const infoContainerRef = ref(null);
const deviceChartRef = ref(null);
const stationChartRef = ref(null);
const popChartRef = ref(null);

const loading = ref(false);
const searchKeyword = ref('');
const displayedData = ref([]);
const dbTimestamp = ref('');
const deviceLoadError = ref('');
const stationLoadError = ref('');
const popLoadError = ref('');

const totalDevices = ref(0);
const countryCount = ref(0);
const cityCount = ref(0);
const countryStats = ref({});
const stationData = ref([]);
const stationCountByCountry = ref({});
const displayTotalDevices = computed(() => withTerminalDeviceDisplayOffset(totalDevices.value));

const {
  resizeVisibleChartContainers,
  observeContainerVisibility,
  cleanupContainerObserver,
} = useInfoChartLifecycle();

const reinitAllCharts = () => {
  resizeVisibleChartContainers({ deviceChartRef, stationChartRef, popChartRef });

  if (activeTab.value === 'terminal') {
    if (Object.keys(countryStats.value).length > 0) initDeviceChart();
    if (Object.keys(stationCountByCountry.value).length > 0) initStationChart();
    if (Object.keys(popCountByCountry.value).length > 0) initPopChart();
    return;
  }

  if (activeTab.value === 'ipv4' && rawIpData.value.length > 0) {
    initIpSegmentChart();
    initIpCountChart();
    initCidrDistChart();
  }
};

// POP 閺佺増宓?
const popCountByCountry = ref({});

const {
  initDeviceChart,
  updateDeviceChart,
  initStationChart,
  initPopChart,
  resizeTerminalCharts,
  disposeTerminalCharts,
} = useInfoTerminalCharts({
  echarts,
  deviceChartRef,
  stationChartRef,
  popChartRef,
  countryStats,
  totalDevices,
  stationCountByCountry,
  popCountByCountry,
  getChineseCountryName,
  getPopCountryChineseName,
});

// 閸掑棝銆夌拋鍓х枂
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50', '100']
});

// 鐠佹儳顦弫鐗堝祦鐞涖劍鐗搁崚?
const columns = [
  {
    title: 'IP 地址',
    dataIndex: 'ip',
    key: 'ip',
    width: 150
  },
  {
    title: '国家/地区',
    dataIndex: 'country',
    key: 'country',
    width: 120
  },
  {
    title: '省份/州',
    dataIndex: 'region',
    key: 'region',
    width: 120
  },
  {
    title: '城市',
    dataIndex: 'city',
    key: 'city',
    width: 120
  },
  {
    title: '时间',
    dataIndex: 'timestamp',
    key: 'timestamp',
    width: 110
  },
  {
    title: '操作',
    key: 'action',
    fixed: 'right',
    width: 80
  }
];

const {
  fofaLoading,
  fofaError,
  fofaSearchKeyword,
  displayedFofaData,
  fofaPagination,
  onFofaSearch,
  handleFofaPageChange,
  handleFofaPageSizeChange,
  loadFofaData,
} = useInfoFofaData();

// 閺嶅洨顒锋い鍨た閸?key
const activeTab = ref('terminal');

const {
  totalIpSegments,
  totalIpCount,
  ipLoading,
  ipError,
  ipSearchKeyword,
  displayedIpData,
  rawIpData,
  ipPagination,
  onIpSearch,
  handleIpTableChange,
  loadIpData,
} = useInfoIpv4Data({
  onLoaded: () => {
    if (activeTab.value === 'ipv4') {
      nextTick(() => {
        setTimeout(() => {
          initIpSegmentChart();
          initIpCountChart();
          initCidrDistChart();
        }, 300);
      });
    }
  },
});

const terminalErrorSummary = computed(() => [
  { key: 'device', title: '设备列表', message: deviceLoadError.value, action: loadDeviceData },
  { key: 'station', title: '地面站分布', message: stationLoadError.value, action: loadStationData },
  { key: 'pop', title: 'PoP 节点分布', message: popLoadError.value, action: loadPopData },
].filter((item) => item.message));

const hasTerminalLoadErrors = computed(() => terminalErrorSummary.value.length > 0);

const retryTerminalPanels = () => {
  loadDeviceData();
  loadStationData();
  loadPopData();
};

// IPv4 缂冩垶顔岀悰銊︾壐閸?
const ipColumns = [
  {
    title: 'IP 网段',
    dataIndex: 'ipSegment',
    key: 'ipSegment',
    width: 200,
    fixed: 'left'
  },
  {
    title: 'CIDR',
    dataIndex: 'cidr',
    key: 'cidr',
    width: 80
  },
  {
    title: '起始 IP',
    dataIndex: 'startIp',
    key: 'startIp',
    width: 150
  },
  {
    title: '结束 IP',
    dataIndex: 'endIp',
    key: 'endIp',
    width: 150
  },
  {
    title: '描述',
    dataIndex: 'description',
    key: 'description',
    width: 300,
    ellipsis: true
  },
  {
    title: '扫描结果',
    dataIndex: 'scanResult',
    key: 'scanResult',
    width: 200
  }
];

// IPv4 閸ユ崘銆冨鏇犳暏
const ipSegmentChartRef = ref(null);
const ipCountChartRef = ref(null);
const cidrDistChartRef = ref(null);

const {
  initIpSegmentChart,
  initIpCountChart,
  initCidrDistChart,
  resizeIpv4Charts,
  disposeIpv4Charts,
} = useInfoIpv4Charts({
  echarts,
  ipSegmentChartRef,
  ipCountChartRef,
  cidrDistChartRef,
  rawIpData,
});

// 閺嶇厧绱￠崠鏍ㄦ殶鐎?
const formatNumber = (num) => {
  const normalized = Number(num ?? 0);
  if (Number.isNaN(normalized)) return '0';
  return new Intl.NumberFormat('en-US').format(normalized);
};

// 濞夈劌鍙嗛崗銊ョ湰韫囶偆鍙庨悩鑸碘偓?
const activeSnapshot = inject('snapshot', ref(null));

const activeSnapshotLabel = computed(() => {
  const snapshotValue = activeSnapshot?.value;
  if (!snapshotValue) {
    return '最新数据';
  }
  if (/^\d{8}$/.test(snapshotValue)) {
    return `${snapshotValue.slice(0, 4)}-${snapshotValue.slice(4, 6)}-${snapshotValue.slice(6, 8)}`;
  }
  return snapshotValue;
});

// 韫囶偆鍙庨崚鍥ㄥ床閺冨爼鍣哥純顔煎瀻妞ら潧鑻熼柌宥嗘煀閸旂姾娴囬弫鐗堝祦
watch(activeSnapshot, () => {
  pagination.current = 1;
  loadDeviceData();
});

// 閹兼粎鍌ㄧ拋鎯ь槵
const onSearch = (value) => {
  searchKeyword.value = value;
  pagination.current = 1; // 闁插秶鐤嗛崚鎵儑娑撯偓妞?
  loadDeviceData(); // 娴犲骸鎮楃粩顖炲櫢閺傛澘濮炴潪鑺ユ殶閹?
};

// 鐞涖劍鐗搁崚鍡涖€夐崣妯哄
const handleTableChange = (pag) => {
  pagination.current = pag.current;
  pagination.pageSize = pag.pageSize;
  loadDeviceData(); // 闁插秵鏌婇崝鐘烘祰閺佺増宓?
};

// 娴犲骸鎮楃粩顖氬鏉炲€燁啎婢跺洦鏆熼幑?
let activeDevicesAbortController = null;
let latestDevicesRequestId = 0;

const loadDeviceData = async () => {
  // 防竞态：只让最后一次请求落地（参照 TerminalSidebar 的 latestRequestId + AbortController 范式）
  activeDevicesAbortController?.abort();
  activeDevicesAbortController = new globalThis.AbortController();
  latestDevicesRequestId += 1;
  const requestId = latestDevicesRequestId;
  const { signal } = activeDevicesAbortController;
  const isLatestDevicesRequest = () => requestId === latestDevicesRequestId;

  try {
    loading.value = true;
    deviceLoadError.value = '';
    
    // 鐠囬攱鐪伴崥搴ｎ伂API
    const data = await fetchDevices({
      page: pagination.current,
      pageSize: pagination.pageSize,
      keyword: searchKeyword.value || '',
      snapshot: activeSnapshot.value || null
    }, { signal });
    
    if (!isLatestDevicesRequest()) return;
    if (!data) throw new Error('返回数据异常');
    
    // 娣囨繂鐡ㄩ弫鐗堝祦鎼存挻妞傞梻瀛樺煈
    dbTimestamp.value = data.dbTimestamp || '';
    
    // 閺囧瓨鏌婇弫鐗堝祦閿涘奔璐熷В蹇氼攽濞ｈ濮為弮鍫曟？閹?
    displayedData.value = data.items.map((item, index) => ({
      ...item,
      key: item.id || index,  // 绾喕绻氬В蹇氼攽閺堝鏁稉鈧琸ey
      timestamp: dbTimestamp.value  // 濞ｈ濮為弮鍫曟？閸?
    }));
    
    // 閺囧瓨鏌婇崚鍡涖€夋穱鈩冧紖
    pagination.total = data.total;
    
    // 閺囧瓨鏌婄紒鐔活吀閺佺増宓?
    totalDevices.value = data.stats.totalDevices || 0;
    countryCount.value = data.stats.countryCount || 0;
    cityCount.value = data.stats.cityCount || 0;
    
    // 閺囧瓨鏌婇崶鎹愩€冮弫鐗堝祦閿涘牊鐦″▎锟犲厴閺囧瓨鏌婇敍?
    if (data.countryStats) {
      countryStats.value = data.countryStats;
      nextTick(() => {
        updateDeviceChart();
      });
    }
    
    loading.value = false;
  } catch (error) {
    if (signal.aborted || !isLatestDevicesRequest()) return;
    console.error('加载设备数据失败:', error);
    deviceLoadError.value = error?.message || '加载设备数据失败，请稍后重试';
    loading.value = false;
  }
};

// 閸︺劌婀撮崶鍙ョ瑐鐎规矮缍呯拋鎯ь槵
const locateOnMap = (record) => {
  // 閸掓稑缂撻懛顏勭暰娑斿绨ㄦ禒璁圭礉娴肩娀鈧帊缍呯純顔讳繆閹?
  const event = new CustomEvent('locate-device', {
    detail: {
      lat: record.lat,
      lng: record.lng,
      zoom: 10
    }
  });
  
  // 鐟欙箑褰傛禍瀣╂
  window.dispatchEvent(event);
};

// 婢跺嫮鎮婄紓鎾崇摠濞撳懘娅庢禍瀣╂
const handleCacheCleared = (event) => {
  // 瀵搫鍩楅柌宥囩枂閸掓壆顑囨稉鈧い鍏镐簰閼惧嘲褰囩€瑰本鏆ｉ惃鍕埠鐠佲剝鏆熼幑?
  pagination.current = 1;
  searchKeyword.value = '';
  
  // 闁插秵鏌婇崝鐘烘祰閹碘偓閺堝鏆熼幑?
  loadDeviceData();
  loadStationData();
  loadPopData();
  
  // 婵″倹鐏夋禍瀣╂閸栧懎鎯堥張鈧弬鎵埠鐠佲剝鏆熼幑顕嗙礉閻╁瓨甯撮弴瀛樻煀閸ユ崘銆?
  if (event.detail && event.detail.stats) {
    const stats = event.detail.stats;
    totalDevices.value = stats.totalDevices || 0;
    countryCount.value = stats.countryCount || 0;
    cityCount.value = stats.cityCount || 0;
    
    if (stats.countryStats) {
      countryStats.value = stats.countryStats;
      nextTick(() => {
        updateDeviceChart();
      });
    }
  }
  
  message.success('数据已刷新');
};

// 婢跺嫮鎮婄粣妤€褰涙径褍鐨崣妯哄
const handleResize = () => {
  resizeTerminalCharts();
  resizeIpv4Charts();
};

// 閸旂姾娴囬崷浼存桨缁旀瑦鏆熼幑顕嗙礄娴?GeoJSON 閺傚洣娆㈤敍?
const loadStationData = async () => {
  try {
    stationLoadError.value = '';
    const { gatewayFeatures } = await buildRenderedGatewayFeatures();

    stationData.value = gatewayFeatures;

    const countryStats = {};
    gatewayFeatures.forEach((feature) => {
      const country = (feature.properties?.country || '').trim() || '其他';
      countryStats[country] = (countryStats[country] || 0) + 1;
    });

    stationCountByCountry.value = countryStats;

  } catch (error) {
    console.error('加载地面站数据失败:', error);
    stationLoadError.value = error?.message || '加载地面站数据失败，请稍后重试';
  }
};


onMounted(() => {
  // 閸旂姾娴囬弫鐗堝祦(娑撳秴鍨垫慨瀣閸ユ崘銆?
  loadDeviceData();
  loadStationData();
  loadPopData();

  // FOFA / IPv4 等大文件数据延迟到信息页首次可见时再加载，只触发一次
  let heavyDataLoaded = false;
  const loadHeavyDataOnce = () => {
    if (heavyDataLoaded) return;
    heavyDataLoaded = true;
    loadFofaData();
    loadIpData();
  };
  
  // 濞ｈ濮炵粣妤€褰涙径褍鐨崣妯哄閻╂垵鎯?
  window.addEventListener('resize', handleResize);
  
  // 濞ｈ濮炵紓鎾崇摠濞撳懘娅庢禍瀣╂閻╂垵鎯夐崳?
  window.addEventListener('cache-cleared', handleCacheCleared);
  
  // 娴ｈ法鏁?IntersectionObserver 閻╂垵鎯夌€圭懓娅掗崣顖濐潌閹?
  observeContainerVisibility({
    containerRef: infoContainerRef,
    onVisible: () => {
      loadHeavyDataOnce();
      reinitAllCharts();
    },
  });
  
  // 閸掓繂顫愰崠鏍х秼閸撳秵鐖ｇ粵楣冦€夐惃鍕禈鐞?瀵ゆ儼绻滅涵顔荤箽閺佺増宓侀崝鐘烘祰鐎瑰本鍨?
  setTimeout(() => {
    if (activeTab.value === 'terminal') {
      nextTick(() => {
        setTimeout(() => {
          resizeVisibleChartContainers({ deviceChartRef, stationChartRef, popChartRef });
          if (Object.keys(countryStats.value).length > 0) {
            initDeviceChart();
          }
          if (Object.keys(stationCountByCountry.value).length > 0) {
            initStationChart();
          }
          if (Object.keys(popCountByCountry.value).length > 0) {
            initPopChart();
          }
        }, 300);
      });
    } else if (activeTab.value === 'ipv4') {
      nextTick(() => {
        setTimeout(() => {
          if (rawIpData.value.length > 0) {
            initIpSegmentChart();
            initIpCountChart();
            initCidrDistChart();
          }
        }, 300);
      });
    }
  }, 1000); // 缂佹瑦鏆熼幑顔煎鏉炲€熷喕婢剁喓娈戦弮鍫曟？
});

// 閻╂垵鎯夐弽鍥╊劮妞ら潧鍨忛幑顫礉瑜版挸鍨忛幑銏犲煂鐎电懓绨查弽鍥╊劮閺冭泛鍨垫慨瀣閸ユ崘銆?
watch(activeTab, (newTab) => {
  if (newTab === 'terminal') {
    // 娴ｈ法鏁?nextTick 绾喕绻?DOM 瀹稿弶瑕嗛弻?
    nextTick(() => {
      setTimeout(() => {
        // 妫ｆ牕鍘涙穱顔碱槻鐎圭懓娅掓径褍鐨?
        resizeVisibleChartContainers({ deviceChartRef, stationChartRef, popChartRef });
        
        // 閸掓繂顫愰崠鏍矒缁旑垵顔曟径鍥ф禈鐞?閸欘亜婀張澶嬫殶閹诡喗妞傞幍宥呭灥婵瀵?
        if (Object.keys(countryStats.value).length > 0) {
          initDeviceChart();
        }
        if (Object.keys(stationCountByCountry.value).length > 0) {
          initStationChart();
        }
        if (Object.keys(popCountByCountry.value).length > 0) {
          initPopChart();
        }
      }, 300); // 缂佹瑤绔撮悙鐟版鏉╃喓鈥樻穱婵囪閺屾挸鐣幋?
    });
  } else if (newTab === 'ipv4') {
    // 娴ｈ法鏁?nextTick 绾喕绻?DOM 瀹稿弶瑕嗛弻?
    nextTick(() => {
      setTimeout(() => {
        if (rawIpData.value.length > 0) {
          initIpSegmentChart();
          initIpCountChart();
          initCidrDistChart();
        }
      }, 300); // 缂佹瑤绔撮悙鐟版鏉╃喓鈥樻穱婵囪閺屾挸鐣幋?
    });
  }
});

// 缂佸嫪娆㈤崡姝屾祰閺冭埖绔婚悶?
onUnmounted(() => {
  // 缁夊娅庣粣妤€褰涙径褍鐨崣妯哄閻╂垵鎯?
  window.removeEventListener('resize', handleResize);
  
  // 缁夊娅庣紓鎾崇摠濞撳懘娅庢禍瀣╂閻╂垵鎯夐崳?
  window.removeEventListener('cache-cleared', handleCacheCleared);
  
  cleanupContainerObserver();

  // 取消仍在途的设备数据请求
  activeDevicesAbortController?.abort();
  
  // 闁库偓濮ｄ礁娴樼悰銊ョ杽娓?
  disposeTerminalCharts();
  disposeIpv4Charts();
});

// 娴?GeoJSON 閸旂姾娴?PoP 閺佺増宓?
const loadPopData = async () => {
  try {
    popLoadError.value = '';
    const { features: popFeatures } = await buildRenderedPopFeatures({
      skipSLC2: true,
    });

    const countryStats = computeRenderedPopCountryStats(popFeatures);
    popCountByCountry.value = countryStats;

  } catch (error) {
    console.error('加载 PoP 数据失败:', error);
    popLoadError.value = error?.message || '加载 PoP 数据失败，请稍后重试';
  }
};

const {
  fofaDetailVisible,
  selectedFofaItem,
  viewFofaDetail,
  closeFofaDetail,
} = useInfoFofaDetailModal();

const {
  scanReportVisible,
  scanReportLoading,
  selectedIpSegment,
  scanReportData,
  filteredScanReportData,
  scanReportColumns,
  getRiskColor,
  showScanReport,
  closeScanReport,
  filterScanReportByThreatLevel,
  resetScanReportFilter,
} = useInfoScanReport({
  messageApi: message,
});

// ========== IPv4 缂冩垶顔岄惄绋垮彠閺傝纭?==========

// 閼惧嘲褰囧蹇斿缂佹挻鐏夐弽鍥╊劮妫版粏澹?
const getScanResultColor = (result) => {
  const colorMap = {
    '查看报告': 'blue',
    '待扫描': 'default',
    '扫描中': 'processing',
    '已完成': 'success',
    '发现漏洞': 'error',
    '安全': 'success',
    '高危': 'red',
    '中危': 'orange',
    '低危': 'yellow'
  };
  return colorMap[result] || 'blue';
};

</script>

<style scoped>
/* ========== 鐎圭懓娅掗崺铏诡攨閺嶅嘲绱?========== */
.info-container {
  position: absolute;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: #f0f4f8;
  overflow-y: auto;
  font-family: 'Microsoft YaHei', 'PingFang SC', Arial, sans-serif;
}

/* ========== 婢舵挳鍎撮弽宄扮础 ========== */
.info-header {
  background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding: 30px 40px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.info-header h1 {
  margin: 0 0 8px 0;
  color: #ffffff;
  font-size: 36px;
  font-weight: 700;
  text-align: center;
  letter-spacing: 2px;
  text-shadow: 0 2px 4px rgba(0,0,0,0.2);
  animation: fadeInDown 0.6s ease-out;
}

@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.header-description {
  color: #bfdbfe;
  font-size: 15px;
  text-align: center;
  margin-top: 8px;
  letter-spacing: 0.5px;
  animation: fadeInUp 0.6s ease-out 0.2s both;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ========== 閺嶅洨顒锋い闈涱啇閸?========== */
.info-tabs {
  padding: 0 40px 20px;
  margin-top: -20px;
}

.modern-tabs :deep(.ant-tabs-nav) {
  background: transparent;
  margin-bottom: 24px;
}

.modern-tabs :deep(.ant-tabs-nav::before) {
  border-bottom: none;
}

.modern-tabs :deep(.ant-tabs-nav-list) {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  padding: 8px;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(31, 38, 135, 0.15);
  border: 1px solid rgba(148, 163, 184, 0.2);
  gap: 8px;
}

.modern-tabs :deep(.ant-tabs-tab) {
  margin: 0 !important;
  padding: 0 !important;
  border: none !important;
  background: transparent !important;
  border-radius: 12px !important;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.modern-tabs :deep(.ant-tabs-tab-btn) {
  padding: 12px 24px;
  width: 100%;
}

.tab-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 500;
  color: #94a3b8;
  transition: all 0.3s ease;
}

.tab-icon {
  font-size: 18px;
  transition: all 0.3s ease;
}

.modern-tabs :deep(.ant-tabs-tab:hover) {
  background: rgba(59, 130, 246, 0.08) !important;
}

.modern-tabs :deep(.ant-tabs-tab:hover .tab-label) {
  color: #3b82f6;
}

.modern-tabs :deep(.ant-tabs-tab:hover .tab-icon) {
  transform: scale(1.1);
}

.modern-tabs :deep(.ant-tabs-tab-active) {
  background: #3b82f6 !important;
}

.modern-tabs :deep(.ant-tabs-tab-active .tab-label) {
  color: #ffffff !important;
  font-weight: 600;
}

.modern-tabs :deep(.ant-tabs-tab-active .tab-icon) {
  color: #ffffff !important;
  transform: scale(1.15);
}

.modern-tabs :deep(.ant-tabs-ink-bar) {
  display: none;
}

.modern-tabs :deep(.ant-tabs-content) {
  background-color: transparent;
  padding-top: 0;
}

/* ========== 缂佺喕顓搁崡锛勫閺嶅嘲绱?========== */
.stats-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
  animation: fadeInUp 0.6s ease-out 0.3s both;
}

.panel-feedback-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 16px;
}

.panel-feedback-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(248, 113, 113, 0.25);
}

.panel-feedback-item-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.panel-feedback-item-copy strong {
  color: #7f1d1d;
}

.panel-feedback-item-copy span {
  color: #991b1b;
  overflow-wrap: anywhere;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 24px;
  background: rgba(30, 41, 59, 0.7);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(31, 38, 135, 0.1);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid rgba(148, 163, 184, 0.2);
  position: relative;
  overflow: hidden;
}

.stat-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, transparent 0%, rgba(59, 130, 246, 0.05) 100%);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.stat-card:hover::before {
  opacity: 1;
}

.stat-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 12px 40px rgba(31, 38, 135, 0.2);
  border-color: rgba(59, 130, 246, 0.3);
}

.stat-primary {
  border-left: 4px solid #3b82f6;
}

.stat-success {
  border-left: 4px solid #10b981;
}

.stat-warning {
  border-left: 4px solid #f59e0b;
}

.stat-info {
  border-left: 4px solid #3b82f6;
}

.stat-icon-wrapper {
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  margin-right: 20px;
  flex-shrink: 0;
}

.stat-primary .stat-icon-wrapper {
  background: #3b82f6;
}

.stat-success .stat-icon-wrapper {
  background: linear-gradient(135deg, #10b981 0%, #34d399 100%);
}

.stat-warning .stat-icon-wrapper {
  background: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%);
}

.stat-info .stat-icon-wrapper {
  background: linear-gradient(135deg, #3b82f6 0%, #60a5fa 100%);
}

.stat-icon {
  font-size: 28px;
  color: #0f172a;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #1f2937;
  line-height: 1.2;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 14px;
  color: #6b7280;
  font-weight: 500;
}

/* ========== 閸愬懎顔愮敮鍐ㄧ湰 ========== */
.content-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

/* ========== 瀹革缚鏅堕棃銏℃緲 - 閸ユ崘銆冮崠鍝勭厵 ========== */
.left-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
  animation: fadeInLeft 0.6s ease-out 0.4s both;
}

@keyframes fadeInLeft {
  from {
    opacity: 0;
    transform: translateX(-30px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.chart-card {
  background: rgba(30, 41, 59, 0.7);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(31, 38, 135, 0.1);
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.chart-card:hover {
  box-shadow: 0 12px 40px rgba(31, 38, 135, 0.2);
  transform: translateY(-4px);
}

.chart-header {
  padding: 20px 24px;
  background: #f8fafc;
  border-bottom: 2px solid rgba(59, 130, 246, 0.1);
  position: relative;
  overflow: hidden;
}

.chart-header::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  background: #3b82f6;
}

.chart-header h3 {
  margin: 0 0 4px 0;
  color: #1f2937;
  font-size: 18px;
  font-weight: 600;
  padding-left: 12px;
}

.chart-subtitle {
  color: #6b7280;
  font-size: 13px;
  padding-left: 12px;
}

.chart-container {
  height: 350px;
  padding: 20px;
}

/* ========== 閸欏厖鏅堕棃銏℃緲 - 閺佺増宓佺悰銊︾壐 ========== */
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
  animation: fadeInRight 0.6s ease-out 0.5s both;
}

@keyframes fadeInRight {
  from {
    opacity: 0;
    transform: translateX(30px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.data-card {
  background: rgba(30, 41, 59, 0.7);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(31, 38, 135, 0.1);
  padding: 24px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.data-card:hover {
  box-shadow: 0 12px 40px rgba(31, 38, 135, 0.2);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 2px solid rgba(59, 130, 246, 0.1);
  position: relative;
}

.card-header::before {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  width: 60px;
  height: 2px;
  background: #3b82f6;
}

.card-header h3 {
  margin: 0;
  color: #1f2937;
  font-size: 18px;
  font-weight: 600;
}

.table-actions {
  margin-bottom: 16px;
}

.action-link {
  color: #3b82f6;
  font-weight: 500;
  transition: color 0.2s ease;
}

.action-link:hover {
  color: #60a5fa;
}

/* ========== 閸濆秴绨插蹇撶鐏炩偓 ========== */
@media (max-width: 1600px) {
  .content-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .stats-summary {
    grid-template-columns: 1fr;
  }

  .panel-feedback-item {
    flex-direction: column;
    align-items: stretch;
  }
}

/* ========== 鐞涖劍鐗告导妯哄閺嶅嘲绱?========== */
.data-card :deep(.ant-table) {
  font-size: 13px;
  border-radius: 8px;
  overflow: hidden;
}

.data-card :deep(.ant-table-thead > tr > th) {
  background: #f1f5f9;
  color: #1f2937;
  font-weight: 600;
  border-bottom: 2px solid rgba(59, 130, 246, 0.2);
  padding: 14px 16px;
}

.data-card :deep(.ant-table-tbody > tr) {
  transition: all 0.2s ease;
}

.data-card :deep(.ant-table-tbody > tr:hover > td) {
  background: #f8fafc;
}

/* ========== 閹稿鎸虫导妯哄閺嶅嘲绱?========== */
.data-card :deep(.ant-btn-primary) {
  background: #3b82f6;
  border: none;
  font-weight: 500;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.2);
}

.data-card :deep(.ant-btn-primary:hover) {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(59, 130, 246, 0.4);
}

.data-card :deep(.ant-btn-primary:active) {
  transform: translateY(0);
}

/* ========== 鏉堟挸鍙嗗鍡曠喘閸栨牗鐗卞?========== */
.data-card :deep(.ant-input-search) {
  border-radius: 10px;
}

.data-card :deep(.ant-input-search .ant-input) {
  border-radius: 10px 0 0 10px;
  border-color: #d1d5db;
  transition: all 0.3s ease;
}

.data-card :deep(.ant-input-search .ant-input:focus) {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.data-card :deep(.ant-input-search-button) {
  border-radius: 0 10px 10px 0;
  background: #3b82f6;
  border: none;
}

/* ========== 閼奉亜鐣炬稊澶嬬泊閸斻劍娼弽宄扮础 ========== */
.info-container::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.info-container::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 4px;
}

.info-container::-webkit-scrollbar-thumb {
  background: #3b82f6;
  border-radius: 4px;
  transition: all 0.3s ease;
}

.info-container::-webkit-scrollbar-thumb:hover {
  background: rgba(30, 41, 59, 0.7);
}

</style>

<style scoped>
.info-workbench {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.info-container {
  background:
    radial-gradient(1200px 500px at 12% -10%, rgba(37, 99, 235, 0.07), transparent 60%),
    radial-gradient(900px 500px at 100% 0%, rgba(59, 130, 246, 0.06), transparent 64%),
    linear-gradient(180deg, #f5f8fc 0%, #edf2f8 100%);
  color: #111827;
}

.info-page-header {
  position: relative;
  z-index: 1;
}

.info-header {
  background: linear-gradient(135deg, #f8fafc 0%, #eef4fb 100%);
  border-bottom: 1px solid #e5e7eb;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
}

.info-header h1 {
  color: #1a1a1a;
  text-shadow: none;
  letter-spacing: 0.04em;
}

.header-description {
  color: #4b5563;
}

.info-tabs {
  padding: 0;
  margin-top: 0;
}

.info-tabs-shell {
  padding: 24px;
}

.content-layout {
  gap: 24px;
}

.left-panel,
.right-panel {
  gap: 24px;
}

.modern-tabs :deep(.ant-tabs-nav-list) {
  background: rgba(248, 251, 255, 0.95);
  border: 1px solid #e5e7eb;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
}

.modern-tabs :deep(.ant-tabs-tab-active) {
  background: #2563eb !important;
}

.stat-card,
.chart-card,
.data-card {
  background: rgba(251, 253, 255, 0.95);
  border: 1px solid #e5e7eb;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
}

.info-panel-card {
  padding: 0;
}

.info-panel-card.chart-card {
  overflow: hidden;
  border-radius: 24px;
}

.info-panel-card.chart-card .chart-header {
  padding: 22px 24px 18px;
  border-bottom: 1px solid rgba(191, 219, 254, 0.6);
  background: linear-gradient(180deg, rgba(248, 251, 255, 0.98), rgba(244, 248, 253, 0.92));
}

.info-panel-card.chart-card .chart-header::before {
  top: auto;
  bottom: -1px;
  left: 24px;
  width: 44px;
  height: 3px;
  border-radius: 999px;
  background: linear-gradient(90deg, #2563eb 0%, #60a5fa 100%);
}

.info-panel-card.chart-card .chart-header h3 {
  margin-bottom: 6px;
  padding-left: 0;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.01em;
}

.info-panel-card.chart-card .chart-subtitle {
  display: inline-flex;
  align-items: center;
  padding-left: 0;
  color: #64748b;
  font-size: 13px;
  font-weight: 500;
}

.info-panel-card.chart-card .chart-container {
  padding: 22px 24px 18px;
  height: 332px;
}

/* Legacy feedback class kept only as a spacing hook while StateBlock owns the
   feedback shell visuals. */
.panel-feedback.ds-state-block {
  margin-bottom: 20px;
}

.stat-primary {
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.95), rgba(251, 253, 255, 0.95));
}

.stat-success {
  background: linear-gradient(180deg, rgba(236, 253, 245, 0.95), rgba(251, 253, 255, 0.95));
}

.stat-warning {
  background: linear-gradient(180deg, rgba(255, 251, 235, 0.95), rgba(251, 253, 255, 0.95));
}

.stat-card:hover,
.chart-card:hover,
.data-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.1);
}

.stat-value,
.card-header h3,
.chart-header h3 {
  color: #111827;
}

.stat-label,
.chart-subtitle,
.action-link {
  color: #4b5563;
}

.chart-header {
  background: linear-gradient(180deg, #f8fafd 0%, #f2f6fb 100%);
}

.data-card :deep(.ant-table-thead > tr > th) {
  background: #f3f6fb;
  color: #111827;
}

.data-card :deep(.ant-table-tbody > tr:hover > td) {
  background: #f6f9fd;
}

.data-card :deep(.ant-table-tbody > tr > td) {
  color: #374151;
}

.data-card :deep(.ant-btn-primary),
.data-card :deep(.ant-input-search-button) {
  background: #2563eb;
}

.info-table-toolbar {
  margin-bottom: 16px;
}

.info-table-toolbar :deep(.ant-input-search) {
  width: 100%;
}

.info-fofa-shell {
  padding: 20px;
}

.info-fofa-shell :deep(.fofa-panel) {
  background: transparent;
  box-shadow: none;
  border: none;
}

.info-panel-card.data-card {
  padding: 0;
  overflow: hidden;
  border-radius: 24px;
}

.info-panel-card.data-card .card-header {
  margin: 0;
  padding: 20px 24px 10px;
  border-bottom: none;
  background: linear-gradient(180deg, rgba(248, 251, 255, 0.98), rgba(246, 249, 253, 0.94));
}

.info-panel-card.data-card .card-header::before {
  left: 24px;
  width: 36px;
  height: 3px;
  bottom: 0;
  border-radius: 999px;
  background: linear-gradient(90deg, #2563eb 0%, #60a5fa 100%);
}

.info-panel-card.data-card .card-header h3 {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.01em;
}

.info-table-toolbar.ds-page-toolbar {
  margin: 0;
  padding: 6px 24px 16px;
  border: none;
  border-radius: 0;
  background: linear-gradient(180deg, rgba(246, 249, 253, 0.94), rgba(255, 255, 255, 0.98));
  backdrop-filter: none;
  box-shadow: none;
}

.info-table-toolbar.ds-page-toolbar .ds-page-toolbar__content {
  width: 100%;
}

.info-table-toolbar :deep(.ant-input-group-wrapper),
.info-table-toolbar :deep(.ant-input-search) {
  width: min(100%, 380px);
}

.info-table-toolbar :deep(.ant-input-search .ant-input),
.info-table-toolbar :deep(.ant-input-search-button) {
  height: 48px;
}

.info-table-toolbar :deep(.ant-input-search .ant-input) {
  font-size: 14px;
}

.info-panel-card.data-card :deep(.ant-table-wrapper) {
  border-top: 1px solid rgba(226, 232, 240, 0.92);
}

.info-panel-card.data-card :deep(.ant-table-container) {
  border-radius: 0;
}

.info-panel-card.data-card :deep(.ant-table-thead > tr > th) {
  padding: 16px 24px;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: none;
  background: linear-gradient(180deg, #f7f9fc 0%, #f1f5f9 100%);
  border-bottom: 1px solid rgba(226, 232, 240, 0.95);
}

.info-panel-card.data-card :deep(.ant-table-tbody > tr > td) {
  padding: 18px 24px;
  font-size: 14px;
  line-height: 1.7;
  background: rgba(255, 255, 255, 0.9);
  vertical-align: top;
}

.info-panel-card.data-card :deep(.ant-table-tbody > tr:hover > td) {
  background: rgba(239, 246, 255, 0.8);
}

.info-panel-card.data-card :deep(.ant-table-pagination.ant-pagination) {
  margin: 0;
  padding: 16px 24px 20px;
  border-top: 1px solid rgba(226, 232, 240, 0.85);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.96));
}

.info-panel-card.data-card :deep(.ant-pagination-item),
.info-panel-card.data-card :deep(.ant-pagination-prev),
.info-panel-card.data-card :deep(.ant-pagination-next) {
  border-radius: 12px;
}

.info-panel-card.data-card :deep(.ant-pagination-options) {
  margin-left: auto;
}

.info-panel-card.data-card :deep(.ant-table-placeholder) {
  background: transparent;
}

.info-panel-card.data-card :deep(.ant-empty) {
  margin: 32px 0;
}

@media (max-width: 900px) {
  .info-workbench {
    padding: 16px;
  }

  .info-tabs-shell {
    padding: 16px;
  }

  .content-layout,
  .left-panel,
  .right-panel {
    gap: 18px;
  }

  .info-panel-card.chart-card .chart-header {
    padding: 18px 18px 14px;
  }

  .info-panel-card.chart-card .chart-header::before {
    left: 18px;
  }

  .info-panel-card.chart-card .chart-container {
    padding: 18px 18px 14px;
    height: 300px;
  }

  .info-panel-card.data-card .card-header {
    padding: 18px 18px 8px;
  }

  .info-table-toolbar.ds-page-toolbar {
    padding: 6px 18px 14px;
  }

  .info-panel-card.data-card :deep(.ant-table-thead > tr > th),
  .info-panel-card.data-card :deep(.ant-table-tbody > tr > td),
  .info-panel-card.data-card :deep(.ant-table-pagination.ant-pagination) {
    padding-left: 18px;
    padding-right: 18px;
  }
}
</style>
