import { reactive, ref } from 'vue';
import Papa from 'papaparse';
import { fetchIpv4PrefixesCsv } from '../services/infoDataService.js';
import { calculateEndIpFromCidr } from '../utils/infoDataParsers.js';

/**
 * @param {{ onLoaded?: () => void }} [options]
 */
export function useInfoIpv4Data(options = {}) {
  const { onLoaded } = options;

  const totalIpSegments = ref(0);
  const totalIpCount = ref(0);
  const ipLoading = ref(false);
  const ipError = ref('');
  const ipSearchKeyword = ref('');
  const displayedIpData = ref([]);
  const rawIpData = ref([]);

  const ipPagination = reactive({
    current: 1,
    pageSize: 10,
    total: 0,
    showSizeChanger: true,
    pageSizeOptions: ['10', '20', '50', '100'],
  });

  const calculateIpStatistics = (data) => {
    totalIpSegments.value = data.length;
    totalIpCount.value = data.reduce((sum, item) => sum + item.ipCount, 0);
  };

  const filterIpData = () => {
    if (!ipSearchKeyword.value.trim()) {
      displayedIpData.value = rawIpData.value;
      ipPagination.total = rawIpData.value.length;
      return;
    }

    const keyword = ipSearchKeyword.value.trim().toLowerCase();
    const filtered = rawIpData.value.filter((item) => (
      (item.ipSegment && item.ipSegment.toLowerCase().includes(keyword))
      || (item.description && item.description.toLowerCase().includes(keyword))
      || (item.scanResult && item.scanResult.toLowerCase().includes(keyword))
      || (item.cidr && item.cidr.toString().includes(keyword))
      || (item.startIp && item.startIp.toLowerCase().includes(keyword))
      || (item.endIp && item.endIp.toLowerCase().includes(keyword))
    ));

    displayedIpData.value = filtered;
    ipPagination.current = 1;
    ipPagination.total = filtered.length;
  };

  const onIpSearch = (value) => {
    ipSearchKeyword.value = value;
    ipPagination.current = 1;
    filterIpData();
  };

  const handleIpTableChange = (pag) => {
    ipPagination.current = pag.current;
    ipPagination.pageSize = pag.pageSize;
  };

  const loadIpData = async () => {
    try {
      ipLoading.value = true;
      ipError.value = '';
      const csvText = await fetchIpv4PrefixesCsv();
      const parseResult = Papa.parse(csvText, {
        header: true,
        skipEmptyLines: true,
      });

      const processedData = parseResult.data.map((item, index) => {
        const [ipAddress, cidr] = String(item.prefix || '').split('/');
        const cidrNum = parseInt(cidr);
        const totalIps = Number.isFinite(cidrNum) ? Math.pow(2, 32 - cidrNum) : 0;
        const usableIps = Math.max(totalIps - 2, 0);

        return {
          key: index,
          ipSegment: item.prefix,
          cidr: cidrNum,
          startIp: ipAddress,
          endIp: Number.isFinite(cidrNum) ? calculateEndIpFromCidr(ipAddress, cidrNum) : ipAddress,
          ipCount: usableIps,
          totalIps,
          description: item.description,
          asOrganization: 'SpaceX Services, Inc. (AS14593)',
          scanResult: '查看报告',
        };
      });

      rawIpData.value = processedData;
      displayedIpData.value = processedData;
      ipPagination.total = processedData.length;
      calculateIpStatistics(processedData);
      onLoaded?.();
      return true;
    } catch (error) {
      console.error('加载IPv4数据失败:', error);
      ipError.value = error?.message || '加载 IPv4 数据失败，请稍后重试';
      return false;
    } finally {
      ipLoading.value = false;
    }
  };

  return {
    totalIpSegments,
    totalIpCount,
    ipLoading,
    ipError,
    ipSearchKeyword,
    displayedIpData,
    rawIpData,
    ipPagination,
    onIpSearch,
    filterIpData,
    handleIpTableChange,
    loadIpData,
  };
}
