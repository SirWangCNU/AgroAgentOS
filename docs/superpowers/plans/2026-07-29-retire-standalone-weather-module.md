# 独立天气查询模块下线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除按城市或浏览器定位查询天气的独立 Web 模块，只保留农场管理页的农场天气能力。

**Architecture:** 后端移除仅服务独立天气页面的 `/api/v1/weather*` 路由注册和实现，但保留 `weather_service` 及农场范围的 `/api/v1/farms/{farm_id}/weather`。前端删除独立天气页面、入口、城市天气徽标、仪表盘摘要及其 API 客户端；农场管理仍使用 `getFarmWeather` 和 `FarmWeatherSummary`。

**Tech Stack:** FastAPI、pytest、React 19、TypeScript、Vite、TanStack React Query。

## Global Constraints

- 天气仅在农场管理中以当前农场坐标展示。
- 不删除 `weather_service`、AI Skill/MCP 工具或农场天气接口。
- 不引入新的前端依赖；历史记录中的 `weather` 类型数据保持不变。

---

### Task 1: 以回归测试锁定路由边界

**Files:**
- Create: `tests/test_weather_module_retirement.py`
- Modify: `app/main.py`
- Delete: `app/api/v1/weather.py`

**Interfaces:** Consumes FastAPI `app.routes`; produces no `/api/v1/weather*` route while retaining `/api/v1/farms/{farm_id}/weather`.

- [ ] **Step 1: Write the failing test**

```python
from app.main import app

def test_standalone_weather_routes_are_not_registered():
    paths = {route.path for route in app.routes}
    assert "/api/v1/weather" not in paths
    assert "/api/v1/weather/location" not in paths
    assert "/api/v1/weather/config" not in paths
    assert "/api/v1/farms/{farm_id}/weather" in paths
```

- [ ] **Step 2: Verify RED**

Run `$env:DEBUG='false'; py -3.11 -m pytest tests/test_weather_module_retirement.py -q`.

Expected: fail because `weather.router` is registered.

- [ ] **Step 3: Write minimal implementation**

Remove `weather` from the `app.api.v1` import list and delete `app.include_router(weather.router, prefix=API_PREFIX)` in `app/main.py`. Delete `app/api/v1/weather.py`. Do not modify `app/services/weather_service.py` or `app/api/v1/farms.py`.

- [ ] **Step 4: Verify GREEN**

Run `$env:DEBUG='false'; py -3.11 -m pytest tests/test_weather_module_retirement.py tests/services/test_farm_weather.py -q`.

Expected: both files pass.

- [ ] **Step 5: Commit**

Run `git add app/main.py tests/test_weather_module_retirement.py; git add -u app/api/v1/weather.py; git commit -m "refactor: retire standalone weather api"`.

### Task 2: 删除独立天气前端及入口

**Files:**
- Create: `frontend-react/tests/standalone-weather-retirement.test.mjs`
- Modify: `frontend-react/src/App.tsx`
- Modify: `frontend-react/src/components/layout/TopBar.tsx`
- Modify: `frontend-react/src/pages/Dashboard.tsx`
- Modify: `frontend-react/src/types/weather.ts`
- Delete: `frontend-react/src/pages/Weather.tsx`
- Delete: `frontend-react/src/components/layout/WeatherBadge.tsx`
- Delete: `frontend-react/src/api/weather.ts`

**Interfaces:** Consumes `getFarmWeather(farmId)` and `FarmWeatherSummary`; produces a workspace with no standalone weather route or city-weather request.

- [ ] **Step 1: Write the failing test**

```js
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

assert.equal(existsSync("src/pages/Weather.tsx"), false);
assert.equal(existsSync("src/components/layout/WeatherBadge.tsx"), false);
assert.equal(existsSync("src/api/weather.ts"), false);
assert.equal(readFileSync("src/App.tsx", "utf8").includes("/workspace/weather"), false);
assert.equal(readFileSync("src/pages/Dashboard.tsx", "utf8").includes("getWeather"), false);
console.log("Standalone weather module retirement checks passed.");
```

- [ ] **Step 2: Verify RED**

Run `node tests/standalone-weather-retirement.test.mjs` from `frontend-react`.

Expected: fail because independent weather files and references exist.

- [ ] **Step 3: Write minimal implementation**

Delete the Weather import and `/workspace/weather` route from `App.tsx`. Remove `CloudSun`, `WeatherBadge`, and the weather workspace item from `TopBar.tsx`. Remove `getWeather`, the weather query, the weather status card, the weather tool card, and the quick weather summary from `Dashboard.tsx`. Keep only `FarmWeatherCurrent`, `FarmWeatherAlert`, and `FarmWeatherSummary` in `types/weather.ts`; delete the three standalone weather files. Do not modify `Farms.tsx` or `api/farms.ts`.

- [ ] **Step 4: Verify GREEN**

Run `node tests/standalone-weather-retirement.test.mjs && npm run build && rg -n 'api/weather|workspace/weather|WeatherBadge|getWeatherByLocation|getWeatherLocationConfig' src` from `frontend-react`.

Expected: test and build pass; `rg` has no matches.

- [ ] **Step 5: Commit**

Run `git add frontend-react/src/App.tsx frontend-react/src/components/layout/TopBar.tsx frontend-react/src/pages/Dashboard.tsx frontend-react/src/types/weather.ts frontend-react/tests/standalone-weather-retirement.test.mjs; git add -u frontend-react/src/pages/Weather.tsx frontend-react/src/components/layout/WeatherBadge.tsx frontend-react/src/api/weather.ts; git commit -m "refactor: remove standalone weather workspace"`.

### Task 3: 更新架构文档并做最终验证

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/superpowers/plans/2026-07-29-retire-standalone-weather-module.md`

**Interfaces:** Consumes completed route/module set; produces documentation that no longer lists `/workspace/weather` or `/weather` as active Web functionality.

- [ ] **Step 1: Update route documentation**

Delete the `/workspace/weather` workspace row and `/weather` API row in `docs/architecture.md`. Preserve descriptions of the weather MCP/tool capability and farm weather endpoint.

- [ ] **Step 2: Run final verification**

Run `$env:DEBUG='false'; py -3.11 -m pytest tests/test_weather_module_retirement.py tests/services/test_farm_weather.py -q; npm --prefix frontend-react run build; rg -n 'api/weather|workspace/weather|WeatherBadge|getWeatherByLocation|getWeatherLocationConfig' frontend-react/src app`.

Expected: pytest and build pass; final search has no matches.

- [ ] **Step 3: Commit**

Run `git add docs/architecture.md docs/superpowers/plans/2026-07-29-retire-standalone-weather-module.md; git commit -m "docs: retire standalone weather module"`.
