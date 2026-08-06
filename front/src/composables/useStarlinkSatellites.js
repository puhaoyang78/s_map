import { computed, onUnmounted, ref, shallowRef, watch } from 'vue'
import { fetchStarlinkVisualization, fetchStarlinkVisualizationDetail } from '../api/starlink.js'
import { notify } from '../utils/notify.js'

const POSITION_UPDATE_INTERVAL_MS = 5000
const TLE_REFRESH_INTERVAL_MS = 2 * 60 * 60 * 1000
let satelliteLib = null
let satelliteLibPromise = null

const loadSatelliteLib = async () => {
  if (satelliteLib) return satelliteLib
  if (!satelliteLibPromise) {
    satelliteLibPromise = import('satellite.js').then((mod) => {
      satelliteLib = mod
      return mod
    })
  }
  return satelliteLibPromise
}

const toNumberOrNull = (value) => {
  if (value === '' || value === null || value === undefined) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

const computeSatellitePosition = (satrec, now) => {
  if (!satelliteLib) {
    return {
      latitude: null,
      longitude: null,
      height_km: null,
      velocity_kms: null,
      position_computed_at: now.toISOString(),
    }
  }

  if (!satrec) {
    return {
      latitude: null,
      longitude: null,
      height_km: null,
      velocity_kms: null,
      position_computed_at: now.toISOString(),
    }
  }

  const propagated = satelliteLib.propagate(satrec, now)
  const positionEci = propagated?.position
  const velocityEci = propagated?.velocity

  if (!positionEci) {
    return {
      latitude: null,
      longitude: null,
      height_km: null,
      velocity_kms: null,
      position_computed_at: now.toISOString(),
    }
  }

  const gmst = satelliteLib.gstime(now)
  const geodetic = satelliteLib.eciToGeodetic(positionEci, gmst)

  const velocityKms = velocityEci
    ? Math.sqrt(
      (velocityEci.x || 0) ** 2
        + (velocityEci.y || 0) ** 2
        + (velocityEci.z || 0) ** 2,
    )
    : null

  return {
    latitude: Number.isFinite(satelliteLib.degreesLat(geodetic.latitude)) ? satelliteLib.degreesLat(geodetic.latitude) : null,
    longitude: Number.isFinite(satelliteLib.degreesLong(geodetic.longitude)) ? satelliteLib.degreesLong(geodetic.longitude) : null,
    height_km: Number.isFinite(geodetic.height) ? geodetic.height : null,
    velocity_kms: Number.isFinite(velocityKms) ? velocityKms : null,
    position_computed_at: now.toISOString(),
  }
}

export function useStarlinkSatellites() {
  const loading = ref(false)
  const detailLoading = ref(false)
  const error = ref('')
  const sourceMeta = ref({})

  // 卫星数组每 5s 整体重建且消费方只读，用浅响应避免大数组深响应式开销
  const rawTleSatellites = shallowRef([])
  const allSatellites = shallowRef([])
  const selectedId = ref('')
  const selectedDetail = ref(null)

  const satrecById = new Map()
  let positionTimer = null
  let refreshTimer = null

  const filters = ref({
    keyword: '',
    minHeight: '',
    maxHeight: '',
  })

  const filteredSatellites = computed(() => {
    const keyword = (filters.value.keyword || '').trim().toLowerCase()
    const minHeight = toNumberOrNull(filters.value.minHeight)
    const maxHeight = toNumberOrNull(filters.value.maxHeight)

    return allSatellites.value.filter((item) => {
      if (keyword) {
        const haystack = [
          item.id,
          item.name,
          item.object_name,
          String(item.norad_cat_id || ''),
        ].join(' ').toLowerCase()
        if (!haystack.includes(keyword)) {
          return false
        }
      }

      const h = item.height_km
      if (minHeight !== null) {
        if (h === null || h === undefined || Number(h) < minHeight) return false
      }
      if (maxHeight !== null) {
        if (h === null || h === undefined || Number(h) > maxHeight) return false
      }
      return true
    })
  })

  const networkBlockNotice = computed(() => {
    const meta = sourceMeta.value || {}
    if (!meta.networkRefreshBlocked) return ''
    return meta.networkRefreshBlockReason || '上游数据源限频中，请稍后再试'
  })

  const degradedNotice = computed(() => {
    const meta = sourceMeta.value || {}
    if (!meta.stale) return ''
    if (meta.source === 'degraded-empty') {
      return meta.fallbackReason || '上游数据源不可用，当前返回空数据'
    }
    if (meta.fallbackReason) {
      return `上游暂不可用，当前使用缓存数据（${meta.fallbackReason}）`
    }
    return '上游暂不可用，当前使用缓存数据'
  })

  const rebuildSatrecIndex = () => {
    satrecById.clear()
    if (!satelliteLib) return
    rawTleSatellites.value.forEach((item) => {
      const line1 = item?.tle?.line1 || ''
      const line2 = item?.tle?.line2 || ''
      if (!line1 || !line2) return
      try {
        satrecById.set(item.id, satelliteLib.twoline2satrec(line1, line2))
      } catch {
        satrecById.set(item.id, null)
      }
    })
  }

  const recomputePositions = () => {
    if (!rawTleSatellites.value.length) {
      allSatellites.value = []
      return
    }

    const now = new Date()
    allSatellites.value = rawTleSatellites.value.map((item) => {
      const satrec = satrecById.get(item.id) || null
      const computedPosition = computeSatellitePosition(satrec, now)

      return {
        ...item,
        metadata_source: item.metadata_source || 'celestrak',
        orbit_source: item.orbit_source || 'celestrak',
        ...computedPosition,
      }
    })

    if (selectedId.value) {
      const selected = allSatellites.value.find((it) => it.id === selectedId.value)
      if (selected) {
        selectedDetail.value = selected
      }
    }
  }

  const ensureTimers = () => {
    if (!positionTimer) {
      positionTimer = globalThis.setInterval(() => {
        recomputePositions()
      }, POSITION_UPDATE_INTERVAL_MS)
    }

    if (!refreshTimer) {
      refreshTimer = globalThis.setInterval(() => {
        loadSatellites(false)
      }, TLE_REFRESH_INTERVAL_MS)
    }
  }

  const clearTimers = () => {
    if (positionTimer) {
      globalThis.clearInterval(positionTimer)
      positionTimer = null
    }
    if (refreshTimer) {
      globalThis.clearInterval(refreshTimer)
      refreshTimer = null
    }
  }

  const loadSatellites = async (forceRefresh = false) => {
    loading.value = true
    error.value = ''
    try {
      const [, res] = await Promise.all([
        loadSatelliteLib(),
        fetchStarlinkVisualization({ forceRefresh }),
      ])
      const items = res?.data?.items || []
      sourceMeta.value = res?.sourceMeta || {}
      rawTleSatellites.value = items
      rebuildSatrecIndex()
      recomputePositions()
      ensureTimers()

      if (!selectedId.value && items.length > 0) {
        selectedId.value = items[0].id
      }
    } catch (e) {
      error.value = e?.message || '加载 Starlink TLE 数据失败'
      notify.error(error.value)
    } finally {
      loading.value = false
    }
  }

  const loadSatelliteDetail = async (satelliteId, forceRefresh = false) => {
    if (!satelliteId) return null
    detailLoading.value = true
    try {
      const local = allSatellites.value.find((item) => item.id === satelliteId)
      if (local && !forceRefresh) {
        selectedDetail.value = local
        selectedId.value = satelliteId
        return local
      }

      const [, res] = await Promise.all([
        loadSatelliteLib(),
        fetchStarlinkVisualizationDetail(satelliteId, { forceRefresh }),
      ])
      const detailRaw = res?.data?.item || null
      if (!detailRaw) return null

      let satrec = satrecById.get(detailRaw.id)
      if (!satrec && detailRaw?.tle?.line1 && detailRaw?.tle?.line2) {
        satrec = satelliteLib.twoline2satrec(detailRaw.tle.line1, detailRaw.tle.line2)
      }

      const enriched = {
        ...detailRaw,
        metadata_source: detailRaw.metadata_source || 'celestrak',
        orbit_source: detailRaw.orbit_source || 'celestrak',
        ...computeSatellitePosition(satrec || null, new Date()),
      }

      selectedDetail.value = enriched
      selectedId.value = enriched?.id || satelliteId
      return enriched
    } catch (e) {
      notify.error(e?.message || '加载卫星详情失败')
      return null
    } finally {
      detailLoading.value = false
    }
  }

  watch(filteredSatellites, (items) => {
    if (!items.length) {
      selectedId.value = ''
      selectedDetail.value = null
      return
    }

    const exists = items.some((item) => item.id === selectedId.value)
    if (!exists) {
      selectedId.value = items[0].id
      selectedDetail.value = null
    }
  })

  onUnmounted(() => {
    clearTimers()
  })

  return {
    loading,
    detailLoading,
    error,
    sourceMeta,
    networkBlockNotice,
    degradedNotice,
    allSatellites,
    selectedId,
    selectedDetail,
    filters,
    filteredSatellites,
    loadSatellites,
    loadSatelliteDetail,
  }
}
