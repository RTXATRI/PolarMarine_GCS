export interface Wgs84Coordinate {
  latitude: number
  longitude: number
}

export type MapOverlay =
  | { kind: 'marker'; id: string; coordinate: Wgs84Coordinate; label: string; tone: string }
  | { kind: 'polyline'; id: string; coordinates: Wgs84Coordinate[]; tone: string }
  | { kind: 'polygon'; id: string; coordinates: Wgs84Coordinate[]; tone: string }

export interface MapProviderCapabilities {
  pointPicking: boolean
  markerEditing: boolean
  baseMapSelection: boolean
  roadNetwork: boolean
}

export interface MapProvider {
  readonly name: string
  readonly capabilities: MapProviderCapabilities
  mount(container: HTMLElement): Promise<void>
  setOverlays(overlays: MapOverlay[]): void
  setPointPickHandler(handler: ((coordinate: Wgs84Coordinate) => void) | null): void
  destroy(): void
}
