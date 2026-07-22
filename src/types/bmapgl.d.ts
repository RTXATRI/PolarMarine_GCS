/* 百度地图 JavaScript API GL 版本全局类型声明（最小化） */

declare namespace BMapGL {
  class Map {
    constructor(container: string | HTMLElement, opts?: MapOptions)
    centerAndZoom(center: Point, zoom: number): void
    enableScrollWheelZoom(enabled?: boolean): void
    enableContinuousZoom(): void
    setMapType(type: MapType): void
    getMapType(): MapType
    addOverlay(overlay: Overlay): void
    removeOverlay(overlay: Overlay): void
    getCenter(): Point
    getZoom(): number
    setCenter(center: Point): void
    panTo(center: Point): void
    setZoom(zoom: number): void
    clearOverlays(): void
    openInfoWindow(infoWindow: InfoWindow, position: Point): void
    closeInfoWindow(): void
    addEventListener(event: string, handler: Function): void
    removeEventListener(event: string, handler: Function): void
    disableDragging(): void
    enableDragging(): void
    addControl(control: Control): void
    removeControl(control: Control): void
  }

  interface MapOptions {
    minZoom?: number
    maxZoom?: number
    enableMapClick?: boolean
  }

  class Point {
    constructor(lng: number, lat: number)
    lng: number
    lat: number
  }

  class Marker extends Overlay {
    constructor(point: Point, opts?: MarkerOptions)
    setPosition(position: Point): void
    getPosition(): Point
    setIcon(icon: Icon): void
    setLabel(label: Label): void
    getLabel(): Label | null
    setTitle(title: string): void
    addEventListener(event: string, handler: Function): void
    removeEventListener(event: string, handler: Function): void
  }

  interface MarkerOptions {
    icon?: Icon
    enableDragging?: boolean
    title?: string
  }

  class Icon {
    constructor(url: string, size: Size, opts?: IconOptions)
  }

  interface IconOptions {
    anchor?: Size
    imageOffset?: Size
  }

  class Size {
    constructor(width: number, height: number)
    width: number
    height: number
  }

  class Label {
    constructor(content: string, opts?: { offset?: Size; position?: Point })
    setContent(content: string): void
    setPosition(position: Point): void
    setStyle(style: Record<string, string>): void
  }

  class Polyline extends Overlay {
    constructor(points: Point[], opts?: PolylineOptions)
    setPath(path: Point[]): void
  }

  interface PolylineOptions {
    strokeColor?: string
    strokeWeight?: number
    strokeOpacity?: number
    strokeStyle?: string
  }

  class InfoWindow {
    constructor(content: string | HTMLElement, opts?: InfoWindowOptions)
  }

  interface InfoWindowOptions {
    width?: number
    height?: number
    title?: string
  }

  class Overlay {
    isVisible(): boolean
    show(): void
    hide(): void
  }

  /** 控件基类 */
  class Control {
    constructor(opts?: ControlOptions)
  }

  interface ControlOptions {
    anchor?: number
    offset?: Size
  }

  /** 地图类型切换控件（卫星/平面/卫星+路网） */
  class MapTypeControl extends Control {
    constructor(opts?: MapTypeControlOptions)
  }

  interface MapTypeControlOptions extends ControlOptions {
    mapTypes?: MapType[]
    type?: number
  }

  /** 比例尺控件 */
  class ScaleControl extends Control {
    constructor(opts?: ScaleControlOptions)
  }

  interface ScaleControlOptions extends ControlOptions {
    type?: number
  }

  /** 缩放控件 */
  class ZoomControl extends Control {
    constructor(opts?: ZoomControlOptions)
  }

  interface ZoomControlOptions extends ControlOptions {
    type?: number
  }

  const BMAP_NORMAL_MAP: MapType
  const BMAP_SATELLITE_MAP: MapType
  const BMAP_EARTH_MAP: MapType

  /** MapTypeControl type 常量：标准下拉 */
  const BMAP_MAPTYPE_CONTROL_HORIZONTAL: number
  /** MapTypeControl type 常量：下拉列表 */
  const BMAP_MAPTYPE_CONTROL_DROPDOWN: number
  /** MapTypeControl type 常量：地图图标 */
  const BMAP_MAPTYPE_CONTROL_MAP: number

  type MapType = string
}
