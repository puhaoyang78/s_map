import { ref, watch } from 'vue';
import Papa from 'papaparse';
import { findScanReport } from '../api/scan.js';
import { fetchScanReportCsv } from '../services/infoDataService.js';

const scanReportColumns = [
  {
    title: '风险等级',
    dataIndex: 'Risk',
    key: 'risk',
    width: 100,
    fixed: 'left',
    filters: [
      { text: 'Critical', value: 'Critical' },
      { text: 'High', value: 'High' },
      { text: 'Medium', value: 'Medium' },
      { text: 'Low', value: 'Low' },
      { text: 'None', value: 'None' },
    ],
    onFilter: (value, record) => record.Risk === value,
  },
  {
    title: 'Plugin ID',
    dataIndex: 'Plugin ID',
    key: 'pluginId',
    width: 100,
  },
  {
    title: '漏洞名称',
    dataIndex: 'Name',
    key: 'name',
    width: 300,
  },
  {
    title: 'CVSS',
    dataIndex: 'CVSS v2.0 Base Score',
    key: 'cvss',
    width: 80,
    sorter: (a, b) => {
      const scoreA = parseFloat(a['CVSS v2.0 Base Score']) || 0;
      const scoreB = parseFloat(b['CVSS v2.0 Base Score']) || 0;
      return scoreB - scoreA;
    },
  },
  {
    title: 'CVE',
    dataIndex: 'CVE',
    key: 'cve',
    width: 150,
  },
  {
    title: '主机',
    dataIndex: 'Host',
    key: 'host',
    width: 140,
  },
  {
    title: '端口',
    dataIndex: 'Port',
    key: 'port',
    width: 100,
  },
  {
    title: '概述',
    dataIndex: 'Synopsis',
    key: 'synopsis',
    width: 200,
    ellipsis: true,
  },
];

const getRiskColor = (risk) => {
  const colorMap = {
    Critical: '#91243E',
    High: '#DD4B50',
    Medium: '#F18C43',
    Low: '#F8C851',
    None: '#67ACE1',
  };
  return colorMap[risk] || '#67ACE1';
};

export function useInfoScanReport({ messageApi }) {
  const scanReportVisible = ref(false);
  const scanReportLoading = ref(false);
  const selectedIpSegment = ref('');
  const scanReportData = ref([]);
  const filteredScanReportData = ref([]);
  const selectedThreatLevel = ref('');
  const reportCache = new Map();
  const REPORT_CACHE_MAX_ENTRIES = 3;

  const readReportCache = (key) => {
    if (!reportCache.has(key)) return null;
    const value = reportCache.get(key);
    // 刷新为最近使用，保证 LRU 淘汰的是最旧未用的条目
    reportCache.delete(key);
    reportCache.set(key, value);
    return value;
  };

  const writeReportCache = (key, value) => {
    if (reportCache.has(key)) reportCache.delete(key);
    reportCache.set(key, value);
    while (reportCache.size > REPORT_CACHE_MAX_ENTRIES) {
      const oldestKey = reportCache.keys().next().value;
      reportCache.delete(oldestKey);
    }
  };

  // 大文件解析放到 Worker 线程，避免阻塞主线程
  const parseScanReportCsv = (csvText) => new Promise((resolve, reject) => {
    Papa.parse(csvText, {
      header: true,
      skipEmptyLines: true,
      quoteChar: '"',
      escapeChar: '"',
      worker: true,
      complete: resolve,
      error: reject,
    });
  });

  const filterScanReportByThreatLevel = (level) => {
    selectedThreatLevel.value = level;
    filteredScanReportData.value = level
      ? scanReportData.value.filter((item) => item.Risk === level)
      : scanReportData.value;
  };

  const resetScanReportFilter = () => {
    selectedThreatLevel.value = '';
    filteredScanReportData.value = scanReportData.value;
  };

  watch(scanReportData, () => {
    resetScanReportFilter();
  });

  const showScanReport = async (record) => {
    const ipSegment = record.ipSegment;
    selectedIpSegment.value = ipSegment;
    scanReportVisible.value = true;
    scanReportLoading.value = true;

    const cachedReport = readReportCache(ipSegment);
    if (cachedReport) {
      scanReportData.value = cachedReport;
      scanReportLoading.value = false;
      return;
    }

    scanReportData.value = [];

    try {
      const result = await findScanReport(ipSegment);
      if (!result.success) {
        messageApi.warning(result.message || '该网段暂无扫描报告');
        scanReportLoading.value = false;
        return;
      }

      const csvPath = result.data?.path || result.path;
      const csvText = await fetchScanReportCsv(csvPath);
      const parseResult = await parseScanReportCsv(csvText);

      if (parseResult.data && parseResult.data.length > 0) {
        scanReportData.value = parseResult.data;
        writeReportCache(ipSegment, parseResult.data);
      } else {
        messageApi.warning('扫描报告为空');
      }
    } catch (error) {
      if (error?.status === 404) {
        messageApi.warning('该网段暂无扫描报告');
      } else {
        console.error('加载扫描报告失败:', error);
        messageApi.error('扫描报告加载失败，请稍后重试');
      }
    } finally {
      scanReportLoading.value = false;
    }
  };

  const closeScanReport = () => {
    scanReportVisible.value = false;
    scanReportLoading.value = false;
    scanReportData.value = [];
    selectedIpSegment.value = '';
  };

  return {
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
  };
}
