import { describe, expect, it } from "vitest";

import {
  calculateFieldAreaMu,
  hasBlockingOverlap,
  mapPolygonToStored,
  storedPolygonToMap,
} from "./field-geometry";
import type { GeoJSONPolygon } from "../types/farm";

const storedPolygon: GeoJSONPolygon = {
  type: "Polygon",
  coordinates: [
    [
      [116.3, 40.0],
      [116.301, 40.0],
      [116.301, 40.001],
      [116.3, 40.001],
      [116.3, 40.0],
    ],
  ],
};

describe("field geometry helpers", () => {
  it("round trips field polygons between WGS84 storage and Gaode map coordinates", () => {
    const mapPolygon = storedPolygonToMap(storedPolygon);
    const restored = mapPolygonToStored(mapPolygon);

    expect(Math.abs(mapPolygon[0][0].lat - 40.0)).toBeGreaterThan(0.001);
    expect(restored.coordinates[0][0][0]).toBeCloseTo(116.3, 4);
    expect(restored.coordinates[0][0][1]).toBeCloseTo(40.0, 4);
  });

  it("calculates a mu preview from a polygon ring", () => {
    const areaMu = calculateFieldAreaMu(storedPolygon);

    expect(areaMu).toBeGreaterThan(10);
    expect(areaMu).toBeLessThan(20);
  });

  it("blocks overlapping fields while allowing a shared edge", () => {
    const sharedEdge: GeoJSONPolygon = {
      type: "Polygon",
      coordinates: [
        [
          [116.301, 40.0],
          [116.302, 40.0],
          [116.302, 40.001],
          [116.301, 40.001],
          [116.301, 40.0],
        ],
      ],
    };
    const overlapping: GeoJSONPolygon = {
      type: "Polygon",
      coordinates: [
        [
          [116.3005, 40.0],
          [116.3015, 40.0],
          [116.3015, 40.001],
          [116.3005, 40.001],
          [116.3005, 40.0],
        ],
      ],
    };

    expect(hasBlockingOverlap(storedPolygon, [sharedEdge])).toBe(false);
    expect(hasBlockingOverlap(storedPolygon, [overlapping])).toBe(true);
  });
});
