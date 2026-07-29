import assert from "node:assert/strict";

import { gcj02ToWgs84, wgs84ToGcj02 } from "../src/lib/coordinates.js";

const beijing = { lat: 39.9042, lng: 116.4074 };
const beijingOnGaode = wgs84ToGcj02(beijing);

assert.ok(
  Math.abs(beijingOnGaode.lat - beijing.lat) > 0.001,
  "北京的 WGS84 坐标在高德图层中应转换为 GCJ-02 坐标",
);

const restoredBeijing = gcj02ToWgs84(beijingOnGaode);
assert.ok(
  Math.abs(restoredBeijing.lat - beijing.lat) < 0.0001 &&
    Math.abs(restoredBeijing.lng - beijing.lng) < 0.0001,
  "从高德图层保存时应还原为 WGS84 坐标",
);

const paris = { lat: 48.8566, lng: 2.3522 };
assert.deepEqual(
  wgs84ToGcj02(paris),
  paris,
  "中国境外的坐标不应转换",
);

console.log("Coordinate conversion checks passed.");
