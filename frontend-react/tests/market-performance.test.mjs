import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const marketPage = readFileSync("src/pages/MarketPrice.tsx", "utf8");
const marketApi = readFileSync("src/api/market.ts", "utf8");

assert.ok(
  marketApi.includes("includeAnalysis") &&
    marketApi.includes("include_analysis"),
  "Market overview API should support skipping slow AI analysis.",
);

assert.ok(
  marketPage.includes("getMarketAnalysis") &&
    marketPage.includes("isAnalysisLoading"),
  "Market page should load AI analysis separately from first-paint data.",
);

assert.ok(
  marketPage.includes("getMarketOverview(crop, location, false)"),
  "Market page should request fast overview data without blocking on AI analysis.",
);

assert.ok(
  marketPage.includes("inputLocation") &&
    marketPage.includes("setLocation(inputLocation.trim())"),
  "Market location typing should not trigger a new request until search submit.",
);

console.log("Market performance UI checks passed.");
