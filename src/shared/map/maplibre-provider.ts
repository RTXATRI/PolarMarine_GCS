import {
  addProtocol,
  GeoJSONSource,
  Map,
  NavigationControl,
  type GeoJSONSourceSpecification
} from 'maplibre-gl'
import { Protocol } from 'pmtiles'
import type { MapOverlay, MapProvider, Wgs84Coordinate } from '@/shared/map/types'

export class MapLibreProvider implements MapProvider {
  readonly name = 'MapLibre 离线地图'
  readonly capabilities = {
    pointPicking: true,
    markerEditing: false,
    baseMapSelection: false,
    roadNetwork: false
  } as const
  private map: Map | null = null
  private overlays: MapOverlay[] = []
  private pointPickHandler: ((coordinate: Wgs84Coordinate) => void) | null = null
  private readonly handleClick = (event: { lngLat: { lat: number; lng: number } }): void => {
    this.pointPickHandler?.({
      latitude: event.lngLat.lat,
      longitude: event.lngLat.lng
    })
  }

  constructor(private readonly styleUrl: string) {}

  async mount(container: HTMLElement): Promise<void> {
    ensurePmtilesProtocol()
    this.map = new Map({
      container,
      style: this.styleUrl,
      center: [120.157, 30.2755],
      zoom: 12
    })
    this.map.addControl(new NavigationControl(), 'top-right')
    this.map.on('click', this.handleClick)
    await new Promise<void>((resolve, reject) => {
      this.map?.once('load', () => resolve())
      this.map?.once('error', (event) => reject(event.error))
    })
    this.map.addSource('gcs-overlays', { type: 'geojson', data: featureCollection(this.overlays) })
    this.map.addLayer({
      id: 'gcs-lines',
      type: 'line',
      source: 'gcs-overlays',
      filter: ['in', '$type', 'LineString', 'Polygon'],
      paint: { 'line-color': ['get', 'color'], 'line-width': 3 }
    })
    this.map.addLayer({
      id: 'gcs-markers',
      type: 'circle',
      source: 'gcs-overlays',
      filter: ['==', '$type', 'Point'],
      paint: {
        'circle-radius': 7,
        'circle-color': ['get', 'color'],
        'circle-stroke-color': '#dbeafe',
        'circle-stroke-width': 2
      }
    })
    this.setOverlays(this.overlays)
  }

  setOverlays(overlays: MapOverlay[]): void {
    this.overlays = overlays
    const source = this.map?.getSource('gcs-overlays') as GeoJSONSource | undefined
    source?.setData(featureCollection(overlays))
    const first = overlays.find((item) => item.kind === 'marker')
    if (first?.kind === 'marker')
      this.map?.easeTo({ center: [first.coordinate.longitude, first.coordinate.latitude] })
  }

  setPointPickHandler(handler: ((coordinate: Wgs84Coordinate) => void) | null): void {
    this.pointPickHandler = handler
  }

  destroy(): void {
    this.map?.off('click', this.handleClick)
    this.map?.remove()
    this.map = null
    this.pointPickHandler = null
  }
}

let pmtilesRegistered = false

function ensurePmtilesProtocol(): void {
  if (pmtilesRegistered) return
  const protocol = new Protocol()
  addProtocol('pmtiles', protocol.tile)
  pmtilesRegistered = true
}

function featureCollection(
  overlays: MapOverlay[]
): Exclude<GeoJSONSourceSpecification['data'], string> {
  return {
    type: 'FeatureCollection',
    features: overlays.map((overlay) => ({
      type: 'Feature',
      id: overlay.id,
      properties: {
        label: overlay.kind === 'marker' ? overlay.label : overlay.id,
        color: overlay.tone
      },
      geometry:
        overlay.kind === 'marker'
          ? {
              type: 'Point',
              coordinates: [overlay.coordinate.longitude, overlay.coordinate.latitude]
            }
          : overlay.kind === 'polyline'
            ? {
                type: 'LineString',
                coordinates: overlay.coordinates.map((point) => [point.longitude, point.latitude])
              }
            : {
                type: 'Polygon',
                coordinates: [overlay.coordinates.map((point) => [point.longitude, point.latitude])]
              }
    }))
  } as Exclude<GeoJSONSourceSpecification['data'], string>
}
