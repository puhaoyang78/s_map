import { regionMatcher } from './regionMatcher.js';
import { fetchHeatmapData, refreshHeatmap } from '../api/heatmap.js';

const HEATMAP_SOURCE_ID = 'city-areas';
const HEATMAP_FILL_LAYER_ID = 'city-fill-layer';
const HEATMAP_LINE_LAYER_ID = 'city-line-layer';
const HEATMAP_LEGEND_CLASS = 'area-legend';
let boundaryGeoJsonPromise = null;

const toRegionEntries = (regionCounts) => {
  if (!regionCounts) return [];
  if (Array.isArray(regionCounts)) return regionCounts;
  if (typeof regionCounts === 'object') return Object.values(regionCounts);
  return [];
};

const cleanupLegend = (map) => {
  const container = map?.getContainer?.();
  if (!container) return;
  container.querySelectorAll(`.${HEATMAP_LEGEND_CLASS}`).forEach((node) => node.remove());
};

const addAreaLegend = (map) => {
  cleanupLegend(map);

  const legendContainer = document.createElement('div');
  legendContainer.className = `mapboxgl-ctrl mapboxgl-ctrl-group ${HEATMAP_LEGEND_CLASS}`;
  legendContainer.style.cssText = `
    background: rgba(255, 255, 255, 0.88);
    border-radius: 10px;
    padding: 10px 12px;
    margin: 10px;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.16);
    font-family: 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
    font-size: 12px;
    color: #334155;
    position: absolute;
    bottom: 30px;
    right: 10px;
    z-index: 1;
    min-width: 168px;
    border: 1px solid rgba(226, 232, 240, 0.9);
  `;

  const title = document.createElement('div');
  title.textContent = '终端设备区域分布';
  title.style.cssText = `
    font-weight: 700;
    margin-bottom: 6px;
    text-align: center;
  `;
  legendContainer.appendChild(title);

  const gradient = document.createElement('div');
  gradient.style.cssText = `
    width: 100%;
    height: 10px;
    background: linear-gradient(to right,
      rgba(33,102,172,0.6) 0%,
      rgba(103,169,207,0.6) 20%,
      rgba(209,229,240,0.6) 40%,
      rgba(253,219,199,0.6) 60%,
      rgba(239,138,98,0.6) 80%,
      rgba(178,24,43,0.7) 100%
    );
    margin-bottom: 6px;
    border-radius: 999px;
  `;
  legendContainer.appendChild(gradient);

  const labels = document.createElement('div');
  labels.style.cssText = `
    display: flex;
    justify-content: space-between;
    font-size: 10px;
    color: #64748b;
  `;
  labels.innerHTML = '<span>低</span><span>高</span>';
  legendContainer.appendChild(labels);

  map.getContainer().appendChild(legendContainer);
};

const applyHeatmapToMap = async (map, geoJsonData) => {
  const nonZeroFilter = ['>', ['get', 'count'], 0];

  if (!map.getSource(HEATMAP_SOURCE_ID)) {
    map.addSource(HEATMAP_SOURCE_ID, { type: 'geojson', data: geoJsonData });
  } else {
    map.getSource(HEATMAP_SOURCE_ID).setData(geoJsonData);
  }

  if (!map.getLayer(HEATMAP_FILL_LAYER_ID)) {
    map.addLayer({
      id: HEATMAP_FILL_LAYER_ID,
      type: 'fill',
      source: HEATMAP_SOURCE_ID,
      filter: nonZeroFilter,
      paint: {
        'fill-color': [
          'interpolate', ['linear'], ['get', 'density'],
          0, 'rgba(33,102,172,0.2)',
          0.2, 'rgba(103,169,207,0.4)',
          0.4, 'rgba(209,229,240,0.6)',
          0.6, 'rgba(253,219,199,0.6)',
          0.8, 'rgba(239,138,98,0.7)',
          1, 'rgba(178,24,43,0.8)',
        ],
        'fill-opacity': 0.7,
      },
    });
  } else {
    map.setFilter(HEATMAP_FILL_LAYER_ID, nonZeroFilter);
  }

  if (!map.getLayer(HEATMAP_LINE_LAYER_ID)) {
    map.addLayer({
      id: HEATMAP_LINE_LAYER_ID,
      type: 'line',
      source: HEATMAP_SOURCE_ID,
      filter: nonZeroFilter,
      paint: {
        'line-color': [
          'interpolate', ['linear'], ['get', 'density'],
          0, 'rgba(33,102,172,0.8)',
          0.2, 'rgba(103,169,207,0.8)',
          0.4, 'rgba(209,229,240,0.8)',
          0.6, 'rgba(253,219,199,0.8)',
          0.8, 'rgba(239,138,98,0.9)',
          1, 'rgba(178,24,43,1)',
        ],
        'line-width': 1.5,
      },
    });
  } else {
    map.setFilter(HEATMAP_LINE_LAYER_ID, nonZeroFilter);
  }

  addAreaLegend(map);

  await new Promise((resolve) => {
    const onIdle = () => resolve();
    map.once('idle', onIdle);
    setTimeout(() => {
      map.off('idle', onIdle);
      resolve();
    }, 3000);
  });
};

const loadBoundaryGeoJson = async () => {
  if (!boundaryGeoJsonPromise) {
    boundaryGeoJsonPromise = fetch('data/ne_10m_admin_1_states_provinces.json')
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`边界数据加载失败（HTTP ${response.status}）`);
        }

        const rawText = await response.text();
        // 一次性正则剔除非法控制字符（保留 \t \n \r），避免对超大文本逐字符过滤
        // eslint-disable-next-line no-control-regex
        const sanitizedText = rawText.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]/g, '');

        const data = JSON.parse(sanitizedText);
        if (!data?.features || !Array.isArray(data.features)) {
          throw new Error('边界数据格式无效');
        }
        return data;
      })
      .catch((error) => {
        boundaryGeoJsonPromise = null;
        throw error;
      });
  }

  // enrichGeoJson 会先重置全部 feature 的派生属性再写入匹配结果（幂等），
  // 且匹配只读取 admin/name（enrich 不会修改），因此可直接复用缓存对象，无需每次深拷贝。
  return boundaryGeoJsonPromise;
};

const enrichGeoJson = (geoJsonData, regionCounts) => {
  const matchResult = regionMatcher.generateMatchReport(regionCounts, geoJsonData);
  const matchedItems = Object.values(matchResult.matched || {});
  const maxCount = Math.max(...matchedItems.map((item) => item.count), 1);

  geoJsonData.features.forEach((feature) => {
    feature.properties.count = 0;
    feature.properties.density = 0;
    feature.properties.countryZh = '未知国家';
    feature.properties.regionZh = '未知地区';
    feature.properties.countryEn = feature.properties.admin || '';
    feature.properties.regionEn = feature.properties.name || '';
  });

  matchedItems.forEach((matchData) => {
    const feature = matchData.feature;
    const originalData = matchData.originalData?.[0] || {};
    const { primary: countryZh, secondary: countryEn } = regionMatcher.splitBilingualName(originalData.country || '');
    const { primary: regionZh, secondary: regionEn } = regionMatcher.splitBilingualName(originalData.region || '');

    feature.properties.count = matchData.count;
    feature.properties.density = matchData.count / maxCount;
    feature.properties.countryZh = countryZh || countryEn || feature.properties.admin;
    feature.properties.regionZh = regionZh || regionEn || feature.properties.name;
    feature.properties.countryEn = countryEn || feature.properties.admin;
    feature.properties.regionEn = regionEn || feature.properties.name;
  });
};

export const addHeatmapLayer = async (map, forceRefresh = false, snapshot = null, signal = null) => {
  try {
    const params = snapshot ? { snapshot } : {};
    const rawResult = forceRefresh
      ? await refreshHeatmap(params)
      : await fetchHeatmapData(params);

    const regionCounts = (rawResult && typeof rawResult === 'object' && rawResult.data)
      ? rawResult.data
      : rawResult;

    const entries = toRegionEntries(regionCounts);
    const totalCount = entries.reduce((sum, item) => sum + Number(item?.count || 0), 0);

    const boundaryGeoJson = await loadBoundaryGeoJson();
    // 快速连切快照时旧请求可能后返回；落地前若已被新请求取代则放弃写入，避免旧数据覆盖新热力图
    if (signal?.aborted) {
      const abortError = new Error('热力图请求已被新请求取代');
      abortError.name = 'AbortError';
      throw abortError;
    }
    enrichGeoJson(boundaryGeoJson, regionCounts || {});
    await applyHeatmapToMap(map, boundaryGeoJson);

    return {
      hasData: totalCount > 0,
      totalCount,
      regionCount: entries.length,
      snapshot: snapshot ?? null,
    };
  } catch (error) {
    console.error('添加区域热力图图层时出错:', error);
    throw new Error(error?.message || '热力图数据加载失败', { cause: error });
  }
};
