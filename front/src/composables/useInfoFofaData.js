import { reactive, ref } from 'vue';
import { fetchFofaAsnCsv } from '../services/infoDataService.js';
import { parseFofaCsvRows } from '../utils/infoDataParsers.js';

const normalizeKeyword = (value = '') => String(value || '').trim().toLowerCase();

const splitKeywords = (value = '') => normalizeKeyword(value)
  .split(/[\s,]+/)
  .filter(Boolean);

const normalizeField = (value = '') => String(value || '').trim().toLowerCase();

const matchesIp = (ip = '', keyword = '') => {
  const normalizedIp = normalizeField(ip);
  if (!normalizedIp) return false;
  return normalizedIp === keyword || normalizedIp.startsWith(keyword);
};

const normalizeEndpoint = (value = '') => normalizeField(value)
  .replace(/^[a-z][a-z0-9+.-]*:\/\//i, '')
  .replace(/[/?#].*$/, '');

const matchesEndpoint = (item, keyword = '') => {
  const normalizedKeyword = normalizeEndpoint(keyword);
  if (!normalizedKeyword) return false;

  const ip = normalizeField(item.ip);
  const port = normalizeField(item.port);
  const candidates = [
    ip && port ? `${ip}:${port}` : '',
    item.host,
    item.link,
  ].map(normalizeEndpoint);

  return candidates.some((candidate) => (
    candidate === normalizedKeyword || candidate.startsWith(normalizedKeyword)
  ));
};

const matchesTextToken = (value = '', keyword = '') => {
  const normalized = normalizeField(value);
  if (!normalized) return false;
  return normalized
    .split(/[^a-z0-9\u4e00-\u9fa5]+/i)
    .filter(Boolean)
    .some((token) => token === keyword || token.startsWith(keyword));
};

const matchesFofaItem = (item, keyword) => {
  if (!keyword) return true;
  if (matchesEndpoint(item, keyword)) return true;

  if (/^\d+$/.test(keyword)) {
    return matchesIp(item.ip, keyword) || normalizeField(item.port) === keyword || normalizeField(item.as_number) === keyword;
  }

  return (
    matchesIp(item.ip, keyword)
    || matchesTextToken(item.protocol, keyword)
    || matchesTextToken(item.base_protocol, keyword)
    || matchesTextToken(item.country_name, keyword)
    || matchesTextToken(item.region, keyword)
    || matchesTextToken(item.city, keyword)
    || matchesTextToken(item.as_organization, keyword)
    || matchesTextToken(item.server, keyword)
  );
};

export function useInfoFofaData() {
  const fofaLoading = ref(false);
  const fofaError = ref('');
  const fofaSearchKeyword = ref('');
  const displayedFofaData = ref([]);
  const rawFofaData = ref([]);
  const filteredFofaData = ref(null);

  const fofaPagination = reactive({
    current: 1,
    pageSize: 6,
    total: 0,
    showSizeChanger: true,
    pageSizeOptions: ['5', '10', '20', '50'],
  });

  const updateDisplayedFofaData = () => {
    const dataSource = filteredFofaData.value !== null
      ? filteredFofaData.value
      : rawFofaData.value;

    const start = (fofaPagination.current - 1) * fofaPagination.pageSize;
    const end = start + fofaPagination.pageSize;
    displayedFofaData.value = dataSource.slice(start, end);
  };

  const onFofaSearch = (value) => {
    const keywords = splitKeywords(value);
    if (!keywords.length) {
      filteredFofaData.value = null;
      fofaPagination.current = 1;
      fofaPagination.total = rawFofaData.value.length;
      updateDisplayedFofaData();
      return;
    }

    const filtered = rawFofaData.value.filter((item) => keywords.every((keyword) => matchesFofaItem(item, keyword)));

    filteredFofaData.value = filtered;
    fofaPagination.current = 1;
    fofaPagination.total = filtered.length;
    updateDisplayedFofaData();
  };

  const handleFofaPageChange = (page) => {
    fofaPagination.current = page;
    updateDisplayedFofaData();
  };

  const handleFofaPageSizeChange = (_current, size) => {
    // 每页条数变化后重置到第一页，避免当前页超出新页数范围显示空白
    fofaPagination.current = 1;
    fofaPagination.pageSize = size;
    updateDisplayedFofaData();
  };

  const loadFofaData = async () => {
    try {
      fofaLoading.value = true;
      fofaError.value = '';
      const csvText = await fetchFofaAsnCsv();
      const parsedData = parseFofaCsvRows(csvText);
      rawFofaData.value = parsedData;
      fofaPagination.total = parsedData.length;
      updateDisplayedFofaData();
      fofaLoading.value = false;
      return true;
    } catch (error) {
      console.error('加载FOFA数据失败:', error);
      fofaError.value = error?.message || '加载 FOFA 数据失败，请稍后重试';
      fofaLoading.value = false;
      return false;
    }
  };

  return {
    fofaLoading,
    fofaError,
    fofaSearchKeyword,
    displayedFofaData,
    rawFofaData,
    fofaPagination,
    onFofaSearch,
    handleFofaPageChange,
    handleFofaPageSizeChange,
    loadFofaData,
  };
}
