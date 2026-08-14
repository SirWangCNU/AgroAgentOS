import { area, featureCollection, intersect, polygon } from "@turf/turf";
import type { LatLngLiteral } from "leaflet";

import type { GeoJSONPolygon } from "../types/farm";
import { gcj02ToWgs84, wgs84ToGcj02 } from "./coordinates";

const MU_IN_SQUARE_METERS = 666.6667;
const OVERLAP_TOLERANCE_SQUARE_METERS = 1;

function closeRing(ring: number[][]): number[][] {
  if (ring.length === 0) return ring;
  const first = ring[0];
  const last = ring[ring.length - 1];
  if (first[0] === last[0] && first[1] === last[1]) return ring;
  return [...ring, [...first]];
}

export function storedPolygonToMap(boundary: GeoJSONPolygon): LatLngLiteral[][] {
  return boundary.coordinates.map((ring) =>
    ring.map(([lng, lat]) => {
      const converted = wgs84ToGcj02({ lat, lng });
      return { lat: converted.lat, lng: converted.lng };
    }),
  );
}

export function mapPolygonToStored(rings: LatLngLiteral[][]): GeoJSONPolygon {
  const coordinates = rings.map((ring) =>
    closeRing(
      ring.map((point) => {
        const converted = gcj02ToWgs84(point);
        return [Number(converted.lng.toFixed(8)), Number(converted.lat.toFixed(8))];
      }),
    ),
  );
  return { type: "Polygon", coordinates };
}

export function calculateFieldAreaMu(boundary: GeoJSONPolygon): number {
  return Number((area(polygon(boundary.coordinates)) / MU_IN_SQUARE_METERS).toFixed(2));
}

export function hasBlockingOverlap(candidate: GeoJSONPolygon, existing: GeoJSONPolygon[]): boolean {
  const candidateFeature = polygon(candidate.coordinates);
  return existing.some((item) => {
    const overlap = intersect(featureCollection([candidateFeature, polygon(item.coordinates)]));
    if (!overlap) return false;
    return area(overlap) > OVERLAP_TOLERANCE_SQUARE_METERS;
  });
}
