export interface MapCoordinate {
  lat: number;
  lng: number;
}

const PI = Math.PI;
const AXIS = 6378245.0;
const OFFSET = 0.00669342162296594323;

function isOutsideChina({ lat, lng }: MapCoordinate): boolean {
  return lng < 72.004 || lng > 137.8347 || lat < 0.8293 || lat > 55.8271;
}

function transformLat(lng: number, lat: number): number {
  let result =
    -100 +
    2 * lng +
    3 * lat +
    0.2 * lat * lat +
    0.1 * lng * lat +
    0.2 * Math.sqrt(Math.abs(lng));
  result += ((20 * Math.sin(6 * lng * PI) + 20 * Math.sin(2 * lng * PI)) * 2) / 3;
  result += ((20 * Math.sin(lat * PI) + 40 * Math.sin((lat / 3) * PI)) * 2) / 3;
  result += ((160 * Math.sin((lat / 12) * PI) + 320 * Math.sin((lat * PI) / 30)) * 2) / 3;
  return result;
}

function transformLng(lng: number, lat: number): number {
  let result =
    300 +
    lng +
    2 * lat +
    0.1 * lng * lng +
    0.1 * lng * lat +
    0.1 * Math.sqrt(Math.abs(lng));
  result += ((20 * Math.sin(6 * lng * PI) + 20 * Math.sin(2 * lng * PI)) * 2) / 3;
  result += ((20 * Math.sin(lng * PI) + 40 * Math.sin((lng / 3) * PI)) * 2) / 3;
  result += ((150 * Math.sin((lng / 12) * PI) + 300 * Math.sin((lng / 30) * PI)) * 2) / 3;
  return result;
}

export function wgs84ToGcj02(coordinate: MapCoordinate): MapCoordinate {
  if (isOutsideChina(coordinate)) return coordinate;

  const dLat = transformLat(coordinate.lng - 105, coordinate.lat - 35);
  const dLng = transformLng(coordinate.lng - 105, coordinate.lat - 35);
  const radLat = (coordinate.lat / 180) * PI;
  const magic = 1 - OFFSET * Math.sin(radLat) * Math.sin(radLat);
  const sqrtMagic = Math.sqrt(magic);
  const latitudeOffset = (dLat * 180) / (((AXIS * (1 - OFFSET)) / (magic * sqrtMagic)) * PI);
  const longitudeOffset = (dLng * 180) / ((AXIS / sqrtMagic) * Math.cos(radLat) * PI);

  return {
    lat: coordinate.lat + latitudeOffset,
    lng: coordinate.lng + longitudeOffset,
  };
}

export function gcj02ToWgs84(coordinate: MapCoordinate): MapCoordinate {
  if (isOutsideChina(coordinate)) return coordinate;

  const converted = wgs84ToGcj02(coordinate);
  return {
    lat: coordinate.lat * 2 - converted.lat,
    lng: coordinate.lng * 2 - converted.lng,
  };
}
