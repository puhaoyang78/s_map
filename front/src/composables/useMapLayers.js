import { fetchCacheVersion } from '../api/heatmap.js'
import {
  buildHeatmapPopupElement,
  formatStarlinkGatewayDetails,
  formatStarlinkPopDetails,
} from '../utils/mapPopupBuilders'
import { getChinesePopName } from '../utils/popNameMapping'
import { getChineseGatewayName } from '../utils/gatewayNameMapping'

let lastHeatmapCacheCheckAt = 0
let lastHeatmapForceRefresh = true
const HEATMAP_CACHE_CHECK_TTL_MS = 10_000
let mapboxModule = null
let mapboxModulePromise = null

const loadMapboxModule = async () => {
  if (mapboxModule) return mapboxModule
  if (!mapboxModulePromise) {
    mapboxModulePromise = import('mapbox-gl').then((mod) => {
      mapboxModule = mod.default || mod
      return mapboxModule
    })
  }
  return mapboxModulePromise
}

/**
 * Manage map layer mounting and side effects (events, popup, cleanup).
 * @param {{
 *   activeSnapshot: import('vue').Ref<string | null>,
 *   sidebarVisible: import('vue').Ref<boolean>,
 *   closeSidebar: () => void,
 *   openSidebar: (title: string, content: string, clickX?: number, networkSegments?: any[], selection?: any) => void,
 *   onLayerStatus?: (payload: any) => void,
 *   onLayerError?: (payload: any) => void,
 *   onSelectionChange?: (selection: any) => void,
 * }} deps
 */
export function useMapLayers(deps) {
  const {
    activeSnapshot,
    sidebarVisible,
    closeSidebar,
    openSidebar,
    onLayerStatus,
    onLayerError,
    onSelectionChange,
  } = deps

  let selectedFeatureId = null
  let heatmapPopup = null

  const eventHandlers = {
    heatmapMouseMove: null,
    heatmapMouseLeave: null,
    heatmapMouseEnter: null,
    popMouseEnter: null,
    popMouseLeave: null,
    popClick: null,
    gatewayMouseEnter: null,
    gatewayMouseLeave: null,
    gatewayClick: null,
  }

  const shouldForceRefreshHeatmap = async () => {
    const now = Date.now()
    if (lastHeatmapCacheCheckAt && now - lastHeatmapCacheCheckAt < HEATMAP_CACHE_CHECK_TTL_MS) {
      return lastHeatmapForceRefresh
    }

    try {
      const result = await fetchCacheVersion()
      const currentCacheVersion = result.data?.cache_version
      const lastCacheVersion = localStorage.getItem('heatmap_cache_version')
      lastHeatmapCacheCheckAt = now

      if (!lastCacheVersion || lastCacheVersion !== String(currentCacheVersion)) {
        localStorage.setItem('heatmap_cache_version', String(currentCacheVersion))
        lastHeatmapForceRefresh = true
        return true
      }
      lastHeatmapForceRefresh = false
      return false
    } catch {
      lastHeatmapCacheCheckAt = now
      lastHeatmapForceRefresh = true
      return true
    }
  }

  const cleanupLayerInteractions = (map) => {
    if (!map) return

    if (eventHandlers.heatmapMouseMove) {
      map.off('mousemove', 'city-fill-layer', eventHandlers.heatmapMouseMove)
    }
    if (eventHandlers.heatmapMouseLeave) {
      map.off('mouseleave', 'city-fill-layer', eventHandlers.heatmapMouseLeave)
    }
    if (eventHandlers.heatmapMouseEnter) {
      map.off('mouseenter', 'city-fill-layer', eventHandlers.heatmapMouseEnter)
    }

    if (eventHandlers.popMouseEnter) {
      map.off('mouseenter', 'starlink-points-layer', eventHandlers.popMouseEnter)
    }
    if (eventHandlers.popMouseLeave) {
      map.off('mouseleave', 'starlink-points-layer', eventHandlers.popMouseLeave)
    }
    if (eventHandlers.popClick) {
      map.off('click', 'starlink-points-layer', eventHandlers.popClick)
    }

    if (eventHandlers.gatewayMouseEnter) {
      map.off('mouseenter', 'starlink-gateways-layer', eventHandlers.gatewayMouseEnter)
    }
    if (eventHandlers.gatewayMouseLeave) {
      map.off('mouseleave', 'starlink-gateways-layer', eventHandlers.gatewayMouseLeave)
    }
    if (eventHandlers.gatewayClick) {
      map.off('click', 'starlink-gateways-layer', eventHandlers.gatewayClick)
    }

    if (heatmapPopup) {
      heatmapPopup.remove()
    }
  }

  const openSelectionSidebar = (payload) => {
    openSidebar(
      payload.title,
      payload.content,
      payload.clickX,
      payload.networkSegments || [],
      payload.selection || null,
    )
  }

  const setupLayers = async (map) => {
    if (!map) return

    const { addPopLayer } = await import('../utils/popLayer.js')
    const { addHeatmapLayer } = await import('../utils/heatmapLayer.js')

    cleanupLayerInteractions(map)

    addPopLayer(map).catch((error) => {
      onLayerError?.({
        kind: 'pop',
        title: 'PoP/地面站图层加载失败',
        message: error?.message || 'PoP 与地面站图层暂时不可用，地图其余功能不受影响。',
      })
    })
    const forceRefresh = await shouldForceRefreshHeatmap()
    onLayerStatus?.({
      kind: 'heatmap',
      state: 'loading',
      message: activeSnapshot.value
        ? '正在加载所选快照的热力图数据'
        : '正在加载最新热力图数据',
    })

    try {
      const heatmapResult = await addHeatmapLayer(map, forceRefresh, activeSnapshot.value)
      onLayerStatus?.({
        kind: 'heatmap',
        state: heatmapResult?.hasData ? 'ready' : 'empty',
        message: heatmapResult?.hasData
          ? (activeSnapshot.value ? '当前快照热力图已更新' : '最新热力图已加载')
          : (activeSnapshot.value ? '当前快照暂无可展示的热力图数据' : '最新数据暂无可展示的热力图数据'),
      })
    } catch (error) {
      onLayerError?.({
        kind: 'heatmap',
        title: '热力图加载失败',
        message: error?.message || '热力图数据暂时不可用，地图底图仍可继续浏览。',
      })
    }

    if (!heatmapPopup) {
      const mapboxgl = await loadMapboxModule()
      heatmapPopup = new mapboxgl.Popup({
        closeButton: false,
        closeOnClick: false,
        offset: 10,
        className: 'heatmap-popup',
      })
    }

    eventHandlers.heatmapMouseMove = (e) => {
      if (!e.features.length) {
        heatmapPopup.remove()
        return
      }

      const feature = e.features[0]
      const props = feature.properties
      const popupContent = buildHeatmapPopupElement(
        props.countryZh || '未知国家',
        props.regionZh || '未知地区',
        props.count || 0,
      )

      heatmapPopup
        .setLngLat(e.lngLat)
        .setDOMContent(popupContent)
        .addTo(map)
    }

    eventHandlers.heatmapMouseLeave = () => {
      map.getCanvas().style.cursor = ''
      heatmapPopup.remove()
    }

    eventHandlers.heatmapMouseEnter = () => {
      map.getCanvas().style.cursor = 'pointer'
    }

    eventHandlers.popMouseEnter = () => {
      map.getCanvas().style.cursor = 'pointer'
    }

    eventHandlers.popMouseLeave = () => {
      map.getCanvas().style.cursor = ''
    }

    eventHandlers.popClick = (e) => {
      const features = map.queryRenderedFeatures(e.point, { layers: ['starlink-points-layer'] })
      if (!features.length) return

      const feature = features[0]
      const featureId = `starlink-pop-${feature.properties.Name}`
      if (selectedFeatureId === featureId && sidebarVisible.value) {
        closeSidebar()
        selectedFeatureId = null
        onSelectionChange?.(null)
        return
      }

      selectedFeatureId = featureId
      feature.properties._geometry = feature.geometry

      let networkSegments = []
      if (feature.properties.networkSegments) {
        try {
          if (typeof feature.properties.networkSegments === 'string') {
            networkSegments = JSON.parse(feature.properties.networkSegments)
          } else if (Array.isArray(feature.properties.networkSegments)) {
            networkSegments = feature.properties.networkSegments
          }
        } catch {
          networkSegments = []
        }
      }

      openSelectionSidebar({
        title: `🛰 PoP 节点 | ${feature.properties.ChineseName || getChinesePopName(feature.properties.Name)}`,
        content: formatStarlinkPopDetails(feature.properties),
        clickX: e.point.x,
        networkSegments,
        selection: {
          id: featureId,
          type: 'pop',
          typeLabel: 'PoP 节点',
          name: feature.properties.ChineseName || getChinesePopName(feature.properties.Name),
          subtitle: feature.properties.Name || '',
          sourceLabel: '地图点选',
        },
      })
    }

    eventHandlers.gatewayMouseEnter = () => {
      map.getCanvas().style.cursor = 'pointer'
    }

    eventHandlers.gatewayMouseLeave = () => {
      map.getCanvas().style.cursor = ''
    }

    eventHandlers.gatewayClick = (e) => {
      const features = map.queryRenderedFeatures(e.point, { layers: ['starlink-gateways-layer'] })
      if (!features.length) return

      const feature = features[0]
      const featureId = `starlink-gateway-${feature.properties.Name}`
      if (selectedFeatureId === featureId && sidebarVisible.value) {
        closeSidebar()
        selectedFeatureId = null
        onSelectionChange?.(null)
        return
      }

      selectedFeatureId = featureId
      feature.properties._geometry = feature.geometry

      openSelectionSidebar({
        title: `📗 地面站 | ${getChineseGatewayName(feature.properties.Name)}`,
        content: formatStarlinkGatewayDetails(feature.properties),
        clickX: e.point.x,
        selection: {
          id: featureId,
          type: 'gateway',
          typeLabel: '地面站',
          name: getChineseGatewayName(feature.properties.Name),
          subtitle: feature.properties.Name || '',
          sourceLabel: '地图点选',
        },
      })
    }

    map.on('mousemove', 'city-fill-layer', eventHandlers.heatmapMouseMove)
    map.on('mouseleave', 'city-fill-layer', eventHandlers.heatmapMouseLeave)
    map.on('mouseenter', 'city-fill-layer', eventHandlers.heatmapMouseEnter)

    map.on('mouseenter', 'starlink-points-layer', eventHandlers.popMouseEnter)
    map.on('mouseleave', 'starlink-points-layer', eventHandlers.popMouseLeave)
    map.on('click', 'starlink-points-layer', eventHandlers.popClick)

    map.on('mouseenter', 'starlink-gateways-layer', eventHandlers.gatewayMouseEnter)
    map.on('mouseleave', 'starlink-gateways-layer', eventHandlers.gatewayMouseLeave)
    map.on('click', 'starlink-gateways-layer', eventHandlers.gatewayClick)
  }

  return {
    setupLayers,
    cleanupLayerInteractions,
  }
}
