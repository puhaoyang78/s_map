import { onUnmounted } from 'vue'
import { buildStarlinkSatelliteTooltipElement } from '../utils/mapPopupBuilders'

const MAX_RENDER_COUNT = 2200
const DEFAULT_ALTITUDE_KM = 550
const MIN_ALTITUDE_KM = 120
const EARTH_RADIUS_KM = 6371
const FRONT_DOT = 0.12
const OFFSCREEN_MARGIN_PX = 96
const MIN_HIT_RADIUS_PX = 10

let threeModule = null
let threeModulePromise = null
let mapboxModule = null
let mapboxModulePromise = null

const loadThreeModule = async () => {
  if (threeModule) return threeModule
  if (!threeModulePromise) {
    threeModulePromise = import('three').then((mod) => {
      threeModule = mod
      return mod
    })
  }
  return threeModulePromise
}

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

const toNumber = (value) => {
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

const toRadians = (deg) => (deg * Math.PI) / 180

const lngLatToUnit = (lng, lat) => {
  const lngRad = toRadians(lng)
  const latRad = toRadians(lat)
  const cosLat = Math.cos(latRad)
  return [
    cosLat * Math.cos(lngRad),
    cosLat * Math.sin(lngRad),
    Math.sin(latRad),
  ]
}

const dot3 = (a, b) => (a[0] * b[0]) + (a[1] * b[1]) + (a[2] * b[2])

const getGlobeViewVector = (map) => {
  const freeCamera = map?.getFreeCameraOptions?.()
  const cameraLngLat = freeCamera?.position?.toLngLat?.()
  const cameraLng = toNumber(cameraLngLat?.lng)
  const cameraLat = toNumber(cameraLngLat?.lat)

  if (cameraLng !== null && cameraLat !== null) {
    return lngLatToUnit(cameraLng, cameraLat)
  }

  const center = map?.getCenter?.()
  const centerLng = toNumber(center?.lng)
  const centerLat = toNumber(center?.lat)

  if (centerLng !== null && centerLat !== null) {
    return lngLatToUnit(centerLng, centerLat)
  }

  return null
}

const getAltitudeKm = (satellite) => {
  const hKm = toNumber(satellite?.height_km) ?? DEFAULT_ALTITUDE_KM
  return Math.max(MIN_ALTITUDE_KM, hKm)
}

const sampleSatellites = (satellites = [], selectedId = '') => {
  if (satellites.length <= MAX_RENDER_COUNT) {
    return satellites
  }

  const step = Math.ceil(satellites.length / MAX_RENDER_COUNT)
  const sampled = []
  for (let i = 0; i < satellites.length; i += step) {
    sampled.push(satellites[i])
  }

  if (selectedId) {
    const selected = satellites.find((item) => item?.id === selectedId)
    if (selected && !sampled.some((item) => item?.id === selectedId)) {
      if (sampled.length >= MAX_RENDER_COUNT) {
        sampled[sampled.length - 1] = selected
      } else {
        sampled.push(selected)
      }
    }
  }

  return sampled
}

export function useStarlinkThreeOverlay(options) {
  const { getMap, getContainer, onSatelliteClick } = options

  let mounted = false
  let enabled = false

  let satellites = []
  let sampledSatellites = []
  let selectedSatelliteId = ''
  let hoveredSatelliteId = ''
  let renderedSatellites = []

  let scene = null
  let camera = null
  let renderer = null
  let points = null
  let geometry = null
  let material = null
  let positions = null
  let colors = null
  let baseColor = null
  let selectedColor = null

  let satellitePopup = null
  let domEventTarget = null
  let overlayInitPromise = null
  let lastWidth = 0
  let lastHeight = 0

  const rebuildSampledSatellites = () => {
    sampledSatellites = sampleSatellites(satellites, selectedSatelliteId)
  }

  const getMapCanvas = () => {
    const map = getMap?.()
    return map?.getCanvas?.() || null
  }

  const resetHoverState = () => {
    hoveredSatelliteId = ''
    if (satellitePopup) {
      satellitePopup.remove()
    }
  }

  const resetCursor = () => {
    const mapCanvas = getMapCanvas()
    if (mapCanvas) {
      mapCanvas.style.cursor = ''
    }
  }

  const disposeThreeResources = () => {
    if (renderer?.domElement?.parentElement) {
      renderer.domElement.parentElement.removeChild(renderer.domElement)
    }

    geometry?.dispose?.()
    material?.dispose?.()

    scene = null
    camera = null
    renderer?.dispose?.()
    renderer = null
    points = null
    geometry = null
    material = null
    positions = null
    colors = null
    renderedSatellites = []
    lastWidth = 0
    lastHeight = 0
  }

  const ensureThreeOverlay = async () => {
    if (renderer || !mounted) return
    if (overlayInitPromise) return overlayInitPromise

    overlayInitPromise = (async () => {
      const container = getContainer?.()
      if (!container || renderer || !mounted) return
      const THREE = await loadThreeModule()

      scene = new THREE.Scene()
      baseColor = new THREE.Color('#ff4d4f')
      selectedColor = new THREE.Color('#ffd166')

      camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -10, 10)
      camera.position.set(0, 0, 5)

      renderer = new THREE.WebGLRenderer({
        alpha: true,
        antialias: true,
        powerPreference: 'high-performance',
      })
      renderer.setPixelRatio(Math.min(globalThis.devicePixelRatio || 1, 2))
      renderer.setClearColor(0x000000, 0)

      renderer.domElement.className = 'starlink-three-overlay-canvas'
      renderer.domElement.style.position = 'absolute'
      renderer.domElement.style.top = '0'
      renderer.domElement.style.left = '0'
      renderer.domElement.style.width = '100%'
      renderer.domElement.style.height = '100%'
      renderer.domElement.style.pointerEvents = 'none'
      renderer.domElement.style.zIndex = '160'
      renderer.domElement.style.opacity = enabled ? '1' : '0'

      container.appendChild(renderer.domElement)

      positions = new Float32Array(MAX_RENDER_COUNT * 3)
      colors = new Float32Array(MAX_RENDER_COUNT * 3)

      geometry = new THREE.BufferGeometry()
      geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
      geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
      geometry.setDrawRange(0, 0)

      material = new THREE.PointsMaterial({
        size: 3,
        sizeAttenuation: false,
        transparent: false,
        opacity: 1,
        depthTest: false,
        depthWrite: false,
        vertexColors: true,
      })

      points = new THREE.Points(geometry, material)
      points.frustumCulled = false
      points.visible = false
      scene.add(points)
    })().finally(() => {
      overlayInitPromise = null
    })

    return overlayInitPromise
  }

  const syncCanvasSize = () => {
    const container = getContainer?.()
    if (!container || !renderer || !camera) return false

    const width = Math.max(1, Math.floor(container.clientWidth))
    const height = Math.max(1, Math.floor(container.clientHeight))

    if (width === lastWidth && height === lastHeight) {
      return false
    }

    lastWidth = width
    lastHeight = height
    renderer.setSize(width, height, false)

    camera.left = -width / 2
    camera.right = width / 2
    camera.top = height / 2
    camera.bottom = -height / 2
    camera.near = -10
    camera.far = 10
    camera.updateProjectionMatrix()

    return true
  }

  const renderOverlay = async () => {
    await ensureThreeOverlay()

    const map = getMap?.()
    if (!map || !renderer || !scene || !camera || !geometry || !points) return

    syncCanvasSize()

    if (!lastWidth || !lastHeight) {
      points.visible = false
      renderer.render(scene, camera)
      return
    }

    const projectionName = map.getProjection?.()?.name
    const isGlobeProjection = projectionName === 'globe' || Boolean(map._showingGlobe?.())
    let cameraVector = isGlobeProjection ? getGlobeViewVector(map) : null

    const mapCenter = map.getCenter?.()
    const centerLng = toNumber(mapCenter?.lng)
    const centerLat = toNumber(mapCenter?.lat)
    const centerVector = (centerLng === null || centerLat === null)
      ? null
      : lngLatToUnit(centerLng, centerLat)

    if (cameraVector && centerVector) {
      const centerDot = dot3(centerVector, cameraVector)
      if (centerDot < 0) {
        cameraVector = [-cameraVector[0], -cameraVector[1], -cameraVector[2]]
      }
    }

    const projectedCenter = mapCenter ? map.project(mapCenter) : null
    const globeCenterX = Number.isFinite(projectedCenter?.x) ? projectedCenter.x : (lastWidth / 2)
    const globeCenterY = Number.isFinite(projectedCenter?.y) ? projectedCenter.y : (lastHeight / 2)
    const centerX = lastWidth / 2
    const centerY = lastHeight / 2
    const zoomScale = Math.min(2.4, Math.max(1, map.getZoom() / 3.2))

    let count = 0
    renderedSatellites = []

    for (const item of sampledSatellites) {
      const lng = toNumber(item?.longitude)
      const lat = toNumber(item?.latitude)
      if (lng === null || lat === null) continue

      const altitudeKm = getAltitudeKm(item)
      let depthValue = null
      let frontT = 1

      if (cameraVector) {
        const satelliteVector = lngLatToUnit(lng, lat)
        depthValue = dot3(satelliteVector, cameraVector)
        if (depthValue <= FRONT_DOT) {
          continue
        }
        frontT = Math.min(1, Math.max(0, (depthValue - FRONT_DOT) / (1 - FRONT_DOT)))
      }

      const groundPoint = map.project([lng, lat])
      const screenX = groundPoint?.x
      const screenY = groundPoint?.y
      if (!Number.isFinite(screenX) || !Number.isFinite(screenY)) {
        continue
      }

      const dx = screenX - globeCenterX
      const dy = screenY - globeCenterY
      const radiusPx = Math.hypot(dx, dy)
      const directionLength = radiusPx || 1
      const edgeRatio = depthValue === null
        ? Math.min(1, radiusPx / Math.max(1, Math.min(lastWidth, lastHeight) * 0.5))
        : (1 - frontT)

      const liftPx = Math.max(
        2,
        radiusPx * (altitudeKm / EARTH_RADIUS_KM) * (0.55 + edgeRatio * 0.9) * zoomScale,
      )

      const fade = depthValue === null ? 1 : Math.min(1, Math.max(0, (depthValue - FRONT_DOT) / 0.18))
      const colorScale = 0.2 + (0.8 * fade)

      const liftedX = screenX + (dx / directionLength) * liftPx
      const liftedY = screenY + (dy / directionLength) * liftPx

      if (
        liftedX < -OFFSCREEN_MARGIN_PX
        || liftedX > lastWidth + OFFSCREEN_MARGIN_PX
        || liftedY < -OFFSCREEN_MARGIN_PX
        || liftedY > lastHeight + OFFSCREEN_MARGIN_PX
      ) {
        continue
      }

      if (count >= MAX_RENDER_COUNT) break

      const offset = count * 3
      positions[offset] = liftedX - centerX
      positions[offset + 1] = centerY - liftedY
      positions[offset + 2] = 0

      const color = item?.id && item.id === selectedSatelliteId ? selectedColor : baseColor
      colors[offset] = color.r * colorScale
      colors[offset + 1] = color.g * colorScale
      colors[offset + 2] = color.b * colorScale

      renderedSatellites[count] = {
        satellite: item,
        screenX: liftedX,
        screenY: liftedY,
        hitRadius: MIN_HIT_RADIUS_PX + Math.min(8, edgeRatio * 6),
      }
      count += 1
    }

    geometry.setDrawRange(0, count)
    geometry.attributes.position.needsUpdate = true
    geometry.attributes.color.needsUpdate = true

    points.visible = enabled && count > 0
    renderer.domElement.style.opacity = enabled ? '1' : '0'
    renderer.render(scene, camera)
  }

  const requestOverlayRender = () => {
    if (!mounted) return
    if (!enabled && !renderer) return
    const map = getMap?.()
    map?.triggerRepaint?.()
    void renderOverlay()
  }

  const resolveSatelliteByPointer = (event) => {
    if (!enabled || !renderer || !lastWidth || !lastHeight || renderedSatellites.length === 0) {
      return null
    }

    const rect = renderer.domElement.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top

    if (x < 0 || y < 0 || x > rect.width || y > rect.height) {
      return null
    }

    let closestSatellite = null
    let closestDistanceSq = Infinity

    for (const renderedItem of renderedSatellites) {
      if (!renderedItem?.satellite) continue
      const dx = renderedItem.screenX - x
      const dy = renderedItem.screenY - y
      const distanceSq = (dx * dx) + (dy * dy)
      const hitRadius = renderedItem.hitRadius || MIN_HIT_RADIUS_PX
      if (distanceSq > hitRadius * hitRadius) continue
      if (distanceSq >= closestDistanceSq) continue

      closestDistanceSq = distanceSq
      closestSatellite = renderedItem.satellite
    }

    return closestSatellite
  }

  const handlePointerMove = async (event) => {
    if (!enabled) {
      resetCursor()
      resetHoverState()
      return
    }

    const map = getMap?.()
    if (!map) return

    const hitSatellite = resolveSatelliteByPointer(event)
    if (!hitSatellite) {
      resetCursor()
      resetHoverState()
      return
    }

    const mapCanvas = getMapCanvas()
    if (mapCanvas) {
      mapCanvas.style.cursor = 'pointer'
    }

    if (hoveredSatelliteId === hitSatellite.id) {
      return
    }

    hoveredSatelliteId = hitSatellite.id || ''

    if (!satellitePopup) {
      const mapboxgl = await loadMapboxModule()
      satellitePopup = new mapboxgl.Popup({
        closeButton: false,
        closeOnClick: false,
        offset: 10,
        className: 'starlink-popup',
      })
    }

    const lng = toNumber(hitSatellite.longitude)
    const lat = toNumber(hitSatellite.latitude)
    if (lng === null || lat === null) {
      satellitePopup.remove()
      return
    }

    satellitePopup
      .setLngLat([lng, lat])
      .setDOMContent(buildStarlinkSatelliteTooltipElement(hitSatellite))
      .addTo(map)
  }

  const handlePointerLeave = () => {
    resetCursor()
    resetHoverState()
  }

  const handlePointerClick = (event) => {
    if (!enabled) return
    const hitSatellite = resolveSatelliteByPointer(event)
    if (!hitSatellite?.id) return
    onSatelliteClick?.(hitSatellite.id)
  }

  const onMapRender = () => {
    if (!mounted || !enabled) return
    void renderOverlay()
  }

  const onMapViewChange = () => {
    if (!mounted || !enabled) return
    void renderOverlay()
  }

  const onMapResize = () => {
    if (!mounted) return
    syncCanvasSize()
    if (enabled) {
      void renderOverlay()
    }
  }

  const attachEvents = () => {
    const map = getMap?.()
    if (!map) return

    map.on('render', onMapRender)
    map.on('move', onMapViewChange)
    map.on('zoom', onMapViewChange)
    map.on('pitch', onMapViewChange)
    map.on('rotate', onMapViewChange)
    map.on('resize', onMapResize)

    domEventTarget = map.getCanvasContainer?.() || null
    if (!domEventTarget) return

    domEventTarget.addEventListener('mousemove', handlePointerMove)
    domEventTarget.addEventListener('mouseleave', handlePointerLeave)
    domEventTarget.addEventListener('click', handlePointerClick)
  }

  const detachEvents = () => {
    const map = getMap?.()
    if (map) {
      map.off('render', onMapRender)
      map.off('move', onMapViewChange)
      map.off('zoom', onMapViewChange)
      map.off('pitch', onMapViewChange)
      map.off('rotate', onMapViewChange)
      map.off('resize', onMapResize)
    }

    if (domEventTarget) {
      domEventTarget.removeEventListener('mousemove', handlePointerMove)
      domEventTarget.removeEventListener('mouseleave', handlePointerLeave)
      domEventTarget.removeEventListener('click', handlePointerClick)
      domEventTarget = null
    }
  }

  const mount = async () => {
    if (mounted) return

    const map = getMap?.()
    const container = getContainer?.()
    if (!map || !container) return

    mounted = true
    attachEvents()

    if (enabled) {
      await ensureThreeOverlay()
      syncCanvasSize()
      await renderOverlay()
    }
  }

  const unmount = () => {
    if (!mounted) return

    detachEvents()
    resetCursor()
    resetHoverState()
    disposeThreeResources()
    mounted = false
  }

  const setEnabled = (nextEnabled) => {
    enabled = Boolean(nextEnabled)

    if (!enabled) {
      resetCursor()
      resetHoverState()
      if (points) {
        points.visible = false
      }
      if (renderer?.domElement) {
        renderer.domElement.style.opacity = '0'
      }
      return
    }

    if (!renderer) {
      void ensureThreeOverlay().then(() => {
        if (renderer?.domElement) {
          renderer.domElement.style.opacity = '1'
        }
        requestOverlayRender()
      })
      return
    }

    renderer.domElement.style.opacity = '1'
    requestOverlayRender()
  }

  const setSatellites = (nextSatellites = []) => {
    satellites = Array.isArray(nextSatellites) ? nextSatellites : []
    rebuildSampledSatellites()
    requestOverlayRender()
  }

  const setSelectedSatelliteId = (satelliteId = '') => {
    selectedSatelliteId = satelliteId || ''
    rebuildSampledSatellites()
    requestOverlayRender()
  }

  onUnmounted(() => {
    unmount()
  })

  return {
    mount,
    unmount,
    setEnabled,
    setSatellites,
    setSelectedSatelliteId,
  }
}
