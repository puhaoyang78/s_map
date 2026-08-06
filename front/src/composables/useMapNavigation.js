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

export function useMapNavigation(deps) {
  const { getMap, switchToMapView } = deps

  const addTemporaryMarker = async (lng, lat, color = '#4a90e2') => {
    const map = getMap()
    if (!map) return

    const mapboxgl = await loadMapboxModule()
    const marker = new mapboxgl.Marker({ color })
      .setLngLat([lng, lat])
      .addTo(map)

    setTimeout(() => {
      marker.remove()
    }, 3000)
  }

  const flyToTerminal = async (location) => {
    const map = getMap()
    if (!map) return

    map.flyTo({
      center: [location.lng, location.lat],
      zoom: location.zoom || 10,
      essential: true,
    })

    await addTemporaryMarker(location.lng, location.lat)
  }

  const highlightDevice = async (device) => {
    const map = getMap()
    if (!device || !map) return

    await addTemporaryMarker(device.longitude, device.latitude)
    map.flyTo({
      center: [device.longitude, device.latitude],
      zoom: 10,
      essential: true,
    })
  }

  const handleLocateDevice = (event) => {
    if (!event?.detail) return

    switchToMapView()
    setTimeout(() => {
      void flyToTerminal({
        lng: event.detail.lng,
        lat: event.detail.lat,
        zoom: event.detail.zoom || 10,
      })
    }, 100)
  }

  const registerLocateListener = () => {
    window.addEventListener('locate-device', handleLocateDevice)
  }

  const unregisterLocateListener = () => {
    window.removeEventListener('locate-device', handleLocateDevice)
  }

  return {
    flyToTerminal,
    highlightDevice,
    registerLocateListener,
    unregisterLocateListener,
  }
}
