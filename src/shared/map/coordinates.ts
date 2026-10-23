import type { Wgs84Coordinate } from '@/shared/map/types'

const PI = Math.PI
const AXIS = 6378245
const ECCENTRICITY = 0.006693421622965943
const X_PI = (PI * 3000) / 180

export function wgs84ToBd09(point: Wgs84Coordinate): Wgs84Coordinate {
  const gcj = wgs84ToGcj02(point)
  const z =
    Math.sqrt(gcj.longitude ** 2 + gcj.latitude ** 2) + 0.00002 * Math.sin(gcj.latitude * X_PI)
  const theta = Math.atan2(gcj.latitude, gcj.longitude) + 0.000003 * Math.cos(gcj.longitude * X_PI)
  return { longitude: z * Math.cos(theta) + 0.0065, latitude: z * Math.sin(theta) + 0.006 }
}

export function bd09ToWgs84(point: Wgs84Coordinate): Wgs84Coordinate {
  const x = point.longitude - 0.0065
  const y = point.latitude - 0.006
  const z = Math.sqrt(x ** 2 + y ** 2) - 0.00002 * Math.sin(y * X_PI)
  const theta = Math.atan2(y, x) - 0.000003 * Math.cos(x * X_PI)
  return gcj02ToWgs84({ longitude: z * Math.cos(theta), latitude: z * Math.sin(theta) })
}

function wgs84ToGcj02(point: Wgs84Coordinate): Wgs84Coordinate {
  if (outsideChina(point)) return point
  const delta = coordinateDelta(point)
  return { latitude: point.latitude + delta.latitude, longitude: point.longitude + delta.longitude }
}

function gcj02ToWgs84(point: Wgs84Coordinate): Wgs84Coordinate {
  if (outsideChina(point)) return point
  let estimate = point
  for (let index = 0; index < 4; index += 1) {
    const converted = wgs84ToGcj02(estimate)
    estimate = {
      latitude: estimate.latitude - (converted.latitude - point.latitude),
      longitude: estimate.longitude - (converted.longitude - point.longitude)
    }
  }
  return estimate
}

function coordinateDelta(point: Wgs84Coordinate): Wgs84Coordinate {
  const x = point.longitude - 105
  const y = point.latitude - 35
  let latitude = transformLatitude(x, y)
  let longitude = transformLongitude(x, y)
  const radianLatitude = (point.latitude / 180) * PI
  let magic = Math.sin(radianLatitude)
  magic = 1 - ECCENTRICITY * magic * magic
  const rootMagic = Math.sqrt(magic)
  latitude = (latitude * 180) / (((AXIS * (1 - ECCENTRICITY)) / (magic * rootMagic)) * PI)
  longitude = (longitude * 180) / ((AXIS / rootMagic) * Math.cos(radianLatitude) * PI)
  return { latitude, longitude }
}

function transformLatitude(x: number, y: number): number {
  return (
    -100 +
    2 * x +
    3 * y +
    0.2 * y * y +
    0.1 * x * y +
    0.2 * Math.sqrt(Math.abs(x)) +
    ((20 * Math.sin(6 * x * PI) + 20 * Math.sin(2 * x * PI)) * 2) / 3 +
    ((20 * Math.sin(y * PI) + 40 * Math.sin((y / 3) * PI)) * 2) / 3 +
    ((160 * Math.sin((y / 12) * PI) + 320 * Math.sin((y * PI) / 30)) * 2) / 3
  )
}

function transformLongitude(x: number, y: number): number {
  return (
    300 +
    x +
    2 * y +
    0.1 * x * x +
    0.1 * x * y +
    0.1 * Math.sqrt(Math.abs(x)) +
    ((20 * Math.sin(6 * x * PI) + 20 * Math.sin(2 * x * PI)) * 2) / 3 +
    ((20 * Math.sin(x * PI) + 40 * Math.sin((x / 3) * PI)) * 2) / 3 +
    ((150 * Math.sin((x / 12) * PI) + 300 * Math.sin((x / 30) * PI)) * 2) / 3
  )
}

function outsideChina(point: Wgs84Coordinate): boolean {
  return (
    point.longitude < 72.004 ||
    point.longitude > 137.8347 ||
    point.latitude < 0.8293 ||
    point.latitude > 55.8271
  )
}
