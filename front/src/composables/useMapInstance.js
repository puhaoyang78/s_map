import { DEFAULT_MAP_CONFIG, MAP_STYLES } from '../constants/mapConstants.js';

let mapboxModule = null;
let mapboxModulePromise = null;

const loadMapboxModule = async () => {
  if (mapboxModule) return mapboxModule;
  if (!mapboxModulePromise) {
    mapboxModulePromise = import('mapbox-gl').then((mod) => {
      mapboxModule = mod.default || mod;
      return mapboxModule;
    });
  }
  return mapboxModulePromise;
};

const normalizeToken = (token) => {
  if (!token || typeof token !== 'string') return '';
  return token.trim().replace(/^['"]|['"]$/g, '');
};

export const resolveMapboxToken = () => {
  const envToken = normalizeToken(import.meta.env.VITE_MAPBOX_TOKEN || '');
  return envToken;
};

const setMapLanguageToChinese = (map) => {
  const layers = map.getStyle().layers;
  for (const layer of layers) {
    if (layer.layout && layer.layout['text-field']) {
      try {
        map.setLayoutProperty(layer.id, 'text-field', ['coalesce', ['get', 'name_zh-Hans'], ['get', 'name']]);
      } catch {
        // Ignore unsupported layers.
      }
    }
  }
};

const applyProjectionMode = (map, is3DMode) => {
  try {
    map.setProjection(is3DMode ? 'globe' : 'mercator');
  } catch {
    // Ignore unsupported projection API in older runtimes.
  }

  if (!is3DMode) {
    return;
  }

  try {
    map.setFog({
      color: 'rgb(12, 22, 48)',
      'high-color': 'rgb(32, 46, 88)',
      'horizon-blend': 0.18,
      'space-color': 'rgb(3, 7, 18)',
      'star-intensity': 0.25,
    });
  } catch {
    // Ignore unsupported fog API in old style/runtime.
  }
};

/**
 * Create and initialize map instance with existing behavior preserved.
 * @param {{
 *   container: HTMLElement,
 *   is3DMode: boolean,
 *   previousMap?: any,
 *   onLoad?: (map: any) => Promise<void> | void,
 *   onReady?: (map: any) => void,
 *   onError?: (error: { code: string, message: string, fatal?: boolean }) => void,
 * }} options
 * @returns {Promise<any | null>}
 */
export const createMapInstance = async (options) => {
  const { container, is3DMode, previousMap, onLoad, onReady, onError } = options;
  if (!container) {
    onError?.({
      code: 'map-container-missing',
      message: '地图容器尚未准备好，请稍后重试。',
      fatal: true,
    });
    console.error('地图容器元素不存在');
    return null;
  }

  const accessToken = resolveMapboxToken();
  if (!accessToken) {
    onError?.({
      code: 'mapbox-token-missing',
      message: '未配置地图访问令牌。请在 front/.env.local 中设置 VITE_MAPBOX_TOKEN 后重启前端。',
      fatal: true,
    });
    console.error('未配置 Mapbox Token。请在 front/.env.local 中设置 VITE_MAPBOX_TOKEN 并重启前端服务。');
    return null;
  }

  const mapboxgl = await loadMapboxModule();
  mapboxgl.accessToken = accessToken;

  if (typeof mapboxgl.setTelemetryEnabled === 'function') {
    try {
      mapboxgl.setTelemetryEnabled(false);
    } catch {
      // Ignore telemetry API availability differences across Mapbox GL versions.
    }
  }

  if (previousMap) {
    previousMap.remove();
  }

  const map = new mapboxgl.Map({
    container,
    style: is3DMode ? MAP_STYLES.STANDARD_3D : MAP_STYLES.DARK_2D,
    center: DEFAULT_MAP_CONFIG.center,
    zoom: DEFAULT_MAP_CONFIG.zoom,
    maxZoom: DEFAULT_MAP_CONFIG.maxZoom,
    minZoom: DEFAULT_MAP_CONFIG.minZoom,
    renderWorldCopies: true,
    dragRotate: false,
    localIdeographFontFamily: "'Noto Sans SC', 'Microsoft YaHei', sans-serif",
  });

  let loaded = false;

  map.on('error', (event) => {
    const detail = event?.error?.message || '地图资源加载失败，请检查网络或配置后重试。';
    onError?.({
      code: loaded ? 'map-runtime-warning' : 'map-runtime-init-failed',
      message: detail,
      fatal: !loaded,
    });
  });

  map.addControl(new mapboxgl.ScaleControl(), 'bottom-left');

  map.on('load', async () => {
    loaded = true;
    try {
      applyProjectionMode(map, is3DMode);
      setMapLanguageToChinese(map);
      await onLoad?.(map);
      onReady?.(map);
    } catch (error) {
      onError?.({
        code: 'map-layer-setup-failed',
        message: error?.message || '地图图层初始化失败，请稍后重试。',
        fatal: false,
      });
    }
  });

  return map;
};

/**
 * @param {any} map
 */
export const destroyMapInstance = (map) => {
  if (map) {
    map.remove();
  }
};

/**
 * @param {any} map
 */
export const resizeMapInstance = (map) => {
  if (map) {
    map.resize();
  }
};
