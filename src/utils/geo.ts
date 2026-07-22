/**
 * 地理坐标工具函数
 */

const PI = Math.PI
const X_PI = (PI * 3000.0) / 180.0
const EARTH_SEMI_MAJOR_AXIS = 6378245.0
const EARTH_ECCENTRICITY_SQUARED = 0.006693421622965943

function outsideChina(lng: number, lat: number): boolean {
  return lng < 72.004 || lng > 137.8347 || lat < 0.8293 || lat > 55.8271
}

function transformLatitude(x: number, y: number): number {
  let result = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x))
  result += ((20 * Math.sin(6 * x * PI) + 20 * Math.sin(2 * x * PI)) * 2) / 3
  result += ((20 * Math.sin(y * PI) + 40 * Math.sin((y / 3) * PI)) * 2) / 3
  result += ((160 * Math.sin((y / 12) * PI) + 320 * Math.sin((y * PI) / 30)) * 2) / 3
  return result
}

function transformLongitude(x: number, y: number): number {
  let result = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x))
  result += ((20 * Math.sin(6 * x * PI) + 20 * Math.sin(2 * x * PI)) * 2) / 3
  result += ((20 * Math.sin(x * PI) + 40 * Math.sin((x / 3) * PI)) * 2) / 3
  result += ((150 * Math.sin((x / 12) * PI) + 300 * Math.sin((x / 30) * PI)) * 2) / 3
  return result
}

function wgs84ToGcj02(lng: number, lat: number): { lng: number; lat: number } {
  if (outsideChina(lng, lat)) return { lng, lat }

  let dLat = transformLatitude(lng - 105, lat - 35)
  let dLng = transformLongitude(lng - 105, lat - 35)
  const radLat = (lat / 180) * PI
  const sinLat = Math.sin(radLat)
  const magic = 1 - EARTH_ECCENTRICITY_SQUARED * sinLat * sinLat
  const sqrtMagic = Math.sqrt(magic)
  dLat = (dLat * 180) / (((EARTH_SEMI_MAJOR_AXIS * (1 - EARTH_ECCENTRICITY_SQUARED)) / (magic * sqrtMagic)) * PI)
  dLng = (dLng * 180) / ((EARTH_SEMI_MAJOR_AXIS / sqrtMagic) * Math.cos(radLat) * PI)
  return { lng: lng + dLng, lat: lat + dLat }
}

function gcj02ToWgs84(lng: number, lat: number): { lng: number; lat: number } {
  if (outsideChina(lng, lat)) return { lng, lat }

  let wgsLng = lng
  let wgsLat = lat
  for (let index = 0; index < 3; index++) {
    const converted = wgs84ToGcj02(wgsLng, wgsLat)
    wgsLng -= converted.lng - lng
    wgsLat -= converted.lat - lat
  }
  return { lng: wgsLng, lat: wgsLat }
}

function gcj02ToBd09(lng: number, lat: number): { lng: number; lat: number } {
  const z = Math.sqrt(lng * lng + lat * lat) + 0.00002 * Math.sin(lat * X_PI)
  const theta = Math.atan2(lat, lng) + 0.000003 * Math.cos(lng * X_PI)
  return { lng: z * Math.cos(theta) + 0.0065, lat: z * Math.sin(theta) + 0.006 }
}

function bd09ToGcj02(lng: number, lat: number): { lng: number; lat: number } {
  const x = lng - 0.0065
  const y = lat - 0.006
  const z = Math.sqrt(x * x + y * y) - 0.00002 * Math.sin(y * X_PI)
  const theta = Math.atan2(y, x) - 0.000003 * Math.cos(x * X_PI)
  return { lng: z * Math.cos(theta), lat: z * Math.sin(theta) }
}

/** MAVROS WGS-84 → GCJ-02 → Baidu BD-09. */
export function wgs84ToBd09(lng: number, lat: number): { lng: number; lat: number } {
  const gcj = wgs84ToGcj02(lng, lat)
  return gcj02ToBd09(gcj.lng, gcj.lat)
}

/** Baidu BD-09 → GCJ-02 → WGS-84 for clicked and dragged points. */
export function bd09ToWgs84(bdLng: number, bdLat: number): { lng: number; lat: number } {
  const gcj = bd09ToGcj02(bdLng, bdLat)
  return gcj02ToWgs84(gcj.lng, gcj.lat)
}

/** 计算两点间的距离（米），使用 Haversine 公式 */
export function distanceM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371000 // 地球平均半径，米
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLon = ((lon2 - lon1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) * Math.sin(dLon / 2)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return R * c
}

/** 计算从 (lat1,lon1) 到 (lat2,lon2) 的方位角(度), 0=北, 顺时针 */
export function bearingTo(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const lat1Rad = (lat1 * Math.PI) / 180
  const lat2Rad = (lat2 * Math.PI) / 180
  const dLon = ((lon2 - lon1) * Math.PI) / 180
  const y = Math.sin(dLon) * Math.cos(lat2Rad)
  const x =
    Math.cos(lat1Rad) * Math.sin(lat2Rad) -
    Math.sin(lat1Rad) * Math.cos(lat2Rad) * Math.cos(dLon)
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360
}

/** 从 (lat,lon) 沿方位角 bearing(度) 移动 distM 米后的新坐标 */
export function moveByBearing(
  lat: number,
  lon: number,
  bearingDeg: number,
  distM: number
): { lat: number; lon: number } {
  const R = 6371000
  const brng = (bearingDeg * Math.PI) / 180
  const lat1 = (lat * Math.PI) / 180
  const lon1 = (lon * Math.PI) / 180
  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(distM / R) +
    Math.cos(lat1) * Math.sin(distM / R) * Math.cos(brng)
  )
  const lon2 =
    lon1 +
    Math.atan2(
      Math.sin(brng) * Math.sin(distM / R) * Math.cos(lat1),
      Math.cos(distM / R) - Math.sin(lat1) * Math.sin(lat2)
    )
  return { lat: (lat2 * 180) / Math.PI, lon: (lon2 * 180) / Math.PI }
}
