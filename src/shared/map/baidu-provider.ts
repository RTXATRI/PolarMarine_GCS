import { bd09ToWgs84, wgs84ToBd09 } from '@/shared/map/coordinates'
import type { MapOverlay, MapProvider, Wgs84Coordinate } from '@/shared/map/types'

interface BaiduPoint {
  lng: number
  lat: number
}
interface BaiduMap {
  centerAndZoom(point: BaiduPoint, zoom: number): void
  enableScrollWheelZoom(enabled: boolean): void
  addOverlay(overlay: object): void
  clearOverlays(): void
  panTo(point: BaiduPoint): void
  addEventListener(type: 'click', listener: (event: BaiduClickEvent) => void): void
  removeEventListener(type: 'click', listener: (event: BaiduClickEvent) => void): void
}
interface BaiduClickEvent {
  latlng?: BaiduPoint
  point?: BaiduPoint
}
interface BaiduApi {
  Map: new (container: HTMLElement) => BaiduMap
  Point: new (longitude: number, latitude: number) => BaiduPoint
  Marker: new (point: BaiduPoint) => object
  Polyline: new (points: BaiduPoint[], options: object) => object
  Polygon: new (points: BaiduPoint[], options: object) => object
}

export class BaiduMapProvider implements MapProvider {
  readonly name = '百度在线地图'
  readonly capabilities = {
    pointPicking: true,
    markerEditing: false,
    baseMapSelection: false,
    roadNetwork: false
  } as const
  private map: BaiduMap | null = null
  private api: BaiduApi | null = null
  private pointPickHandler: ((coordinate: Wgs84Coordinate) => void) | null = null
  private readonly handleClick = (event: BaiduClickEvent): void => {
    const point = event.latlng ?? event.point
    if (!point || !this.pointPickHandler) return
    this.pointPickHandler(bd09ToWgs84({ longitude: point.lng, latitude: point.lat }))
  }

  constructor(private readonly ak: string) {}

  async mount(container: HTMLElement): Promise<void> {
    this.api = await loadBaidu(this.ak)
    this.map = new this.api.Map(container)
    this.map.centerAndZoom(this.point({ latitude: 30.2755, longitude: 120.157 }), 13)
    this.map.enableScrollWheelZoom(true)
    this.map.addEventListener('click', this.handleClick)
  }

  setOverlays(overlays: MapOverlay[]): void {
    if (!this.map || !this.api) return
    this.map.clearOverlays()
    for (const overlay of overlays) {
      if (overlay.kind === 'marker')
        this.map.addOverlay(new this.api.Marker(this.point(overlay.coordinate)))
      else if (overlay.kind === 'polyline')
        this.map.addOverlay(
          new this.api.Polyline(
            overlay.coordinates.map((point) => this.point(point)),
            { strokeColor: overlay.tone, strokeWeight: 3 }
          )
        )
      else
        this.map.addOverlay(
          new this.api.Polygon(
            overlay.coordinates.map((point) => this.point(point)),
            { strokeColor: overlay.tone, fillColor: overlay.tone, fillOpacity: 0.15 }
          )
        )
    }
    const first = overlays.find((item) => item.kind === 'marker')
    if (first?.kind === 'marker') this.map.panTo(this.point(first.coordinate))
  }

  setPointPickHandler(handler: ((coordinate: Wgs84Coordinate) => void) | null): void {
    this.pointPickHandler = handler
  }

  destroy(): void {
    this.map?.removeEventListener('click', this.handleClick)
    this.map?.clearOverlays()
    this.map = null
    this.pointPickHandler = null
  }

  private point(coordinate: Wgs84Coordinate): BaiduPoint {
    const converted = wgs84ToBd09(coordinate)
    if (!this.api) throw new Error('Baidu map has not loaded')
    return new this.api.Point(converted.longitude, converted.latitude)
  }
}

let loading: Promise<BaiduApi> | null = null
function loadBaidu(ak: string): Promise<BaiduApi> {
  const existing = (window as unknown as { BMapGL?: BaiduApi }).BMapGL
  if (existing) return Promise.resolve(existing)
  if (loading) return loading
  const request = new Promise<BaiduApi>((resolve, reject) => {
    const callback = '__polarMarineBaiduReady'
    const scoped = window as unknown as { BMapGL?: BaiduApi; [key: string]: unknown }
    scoped[callback] = () =>
      scoped.BMapGL ? resolve(scoped.BMapGL) : reject(new Error('百度地图 API 未初始化'))
    const script = document.createElement('script')
    script.src =
      'https://api.map.baidu.com/api?v=1.0&type=webgl&ak=' +
      encodeURIComponent(ak) +
      '&callback=' +
      callback
    script.onerror = () => reject(new Error('百度地图加载失败'))
    document.head.append(script)
  }).catch((error: unknown) => {
    loading = null
    throw error
  })
  loading = request
  return request
}
