import { useEffect, useRef } from 'react'
import L from 'leaflet'
import styles from './LeafletMap.module.css'

export interface MapOptions {
  center?: [number, number]
  zoom?: number
  onMapReady?: (map: L.Map) => void
}

const DEFAULT_CENTER: [number, number] = [8.460555, -11.779889] // Sierra Leone centroid
const DARK_TILE = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
const LIGHT_TILE = 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
const ATTRIBUTION = '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://openstreetmap.org">OSM</a>'

interface Props extends MapOptions {
  className?: string
  style?: React.CSSProperties
  id?: string
}

export default function LeafletMap({ center = DEFAULT_CENTER, zoom = 7, onMapReady, className, style, id }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const isDark = document.documentElement.getAttribute('data-theme') !== 'light'

    const map = L.map(containerRef.current, {
      center,
      zoom,
      zoomControl: true,
      attributionControl: true,
    })

    L.tileLayer(isDark ? DARK_TILE : LIGHT_TILE, {
      attribution: ATTRIBUTION,
      maxZoom: 18,
    }).addTo(map)

    mapRef.current = map
    onMapReady?.(map)

    return () => {
      map.remove()
      mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div
      ref={containerRef}
      id={id}
      className={`${styles.map} ${className ?? ''}`}
      style={style}
    />
  )
}
