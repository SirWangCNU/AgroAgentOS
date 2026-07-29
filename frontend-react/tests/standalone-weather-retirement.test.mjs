import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

assert.equal(existsSync("src/pages/Weather.tsx"), false);
assert.equal(existsSync("src/components/layout/WeatherBadge.tsx"), false);
assert.equal(existsSync("src/api/weather.ts"), false);
assert.equal(readFileSync("src/App.tsx", "utf8").includes("/workspace/weather"), false);
assert.equal(readFileSync("src/pages/Dashboard.tsx", "utf8").includes("getWeather"), false);

console.log("Standalone weather module retirement checks passed.");
