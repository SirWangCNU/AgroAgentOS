# Farm Protection Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace trajectory-centric farm management with a desktop map, farm location editing, simple field records, and real-time weather risk.

**Architecture:** Keep farms and fields as the only active farm-domain tables. Add a farm-scoped weather aggregation endpoint that owns authorization and strips agricultural advice. Replace the existing single large React page with a map-first page that coordinates focused sidebar and map components through React Query and local draft-location state.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, pytest, React 19, TypeScript, TanStack React Query, Leaflet, Tailwind CSS v4.

## Global Constraints

- Implement only the desktop Web route `/workspace/farms`; do not add mobile layouts.
- Store and exchange farm coordinates as WGS84; use WGS84-compatible map layers.
- Do not expose or render agricultural advice, task lists, disease prediction, trajectory data, or field boundaries.
- Delete only `trajectory_points` and `trajectory_files`; retain legacy optional columns on `fields`.
- New backend behavior is test-first; observe each new test fail before adding its production implementation.
- Do not execute the destructive migration against `data/agro_agent.db` without a backup.
- Existing unrelated ESLint failures remain out of scope; the rewritten farm files must have no new lint errors.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `alembic/versions/007_remove_trajectory_tables.py` | Drops trajectory tables and recreates empty tables on downgrade. |
| `app/schemas/weather.py` | Defines the farm weather response without advice fields. |
| `app/services/weather_service.py` | Builds weather and risk data from farm coordinates. |
| `app/api/v1/farms.py` | Exposes the authorized farm weather endpoint. |
| `tests/services/test_farm_weather.py` | Covers no-location, mock-source, and real weather-summary behavior. |
| `tests/test_migrations.py` | Verifies the new migration removes both trajectory tables. |
| `frontend-react/src/api/farms.ts` | Contains farm/field/weather API functions only. |
| `frontend-react/src/types/farm.ts` | Contains farm and simple-field domain types only. |
| `frontend-react/src/components/map/FarmMap.tsx` | Renders farm markers and editable draft locations only. |
| `frontend-react/src/pages/Farms.tsx` | Coordinates desktop sidebar, map, CRUD dialogs, and location drafts. |

### Task 1: Add regression tests for the farm weather contract

**Files:**
- Create: `tests/services/test_farm_weather.py`
- Modify: `app/schemas/weather.py`
- Modify: `app/services/weather_service.py`

**Interfaces:**
- Produces `get_farm_weather_summary(farm: Farm) -> FarmWeatherSummary`.
- Produces `FarmWeatherSummary(available, reason, current, alerts, source)`.

- [ ] **Step 1: Write the failing tests**

```python
async def test_farm_without_coordinates_returns_unavailable():
    result = await get_farm_weather_summary(Farm(name="北地", latitude=None, longitude=None))
    assert result.available is False
    assert result.reason == "FARM_LOCATION_REQUIRED"

async def test_mock_weather_is_not_returned_as_live_data(monkeypatch):
    monkeypatch.setattr(weather_service, "get_weather_by_coordinates", fake_mock_weather)
    result = await get_farm_weather_summary(Farm(name="北地", latitude=36.1, longitude=118.1))
    assert result.available is False
    assert result.reason == "WEATHER_SERVICE_UNAVAILABLE"

async def test_live_weather_summary_excludes_advice(monkeypatch):
    monkeypatch.setattr(weather_service, "get_weather_by_coordinates", fake_live_weather)
    monkeypatch.setattr(weather_service, "get_forecast_with_alerts", fake_forecast)
    result = await get_farm_weather_summary(Farm(name="北地", location="寿光", latitude=36.1, longitude=118.1))
    assert result.available is True
    assert result.current.temperature == 28.0
    assert result.alerts[0].alert_type == "高温"
    assert "advice" not in result.model_dump_json()
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `pytest tests/services/test_farm_weather.py -q`

Expected: import failure for `get_farm_weather_summary`.

- [ ] **Step 3: Add the smallest weather response and service implementation**

```python
class FarmWeatherSummary(BaseModel):
    available: bool
    reason: str | None = None
    current: FarmWeatherCurrent | None = None
    alerts: list[FarmWeatherAlert] = Field(default_factory=list)
    source: str | None = None

async def get_farm_weather_summary(farm: Farm) -> FarmWeatherSummary:
    if farm.latitude is None or farm.longitude is None:
        return FarmWeatherSummary(available=False, reason="FARM_LOCATION_REQUIRED")
    # Fetch live weather and forecast, then return only current metrics and risk labels.
```

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `pytest tests/services/test_farm_weather.py -q`

Expected: 3 passed.

- [ ] **Step 5: Commit the completed task**

```powershell
git add app/schemas/weather.py app/services/weather_service.py tests/services/test_farm_weather.py
git commit -m "feat: add farm weather summary"
```

### Task 2: Expose authorized farm weather through the farms API

**Files:**
- Modify: `app/api/v1/farms.py`
- Test: `tests/services/test_farm_weather.py`

**Interfaces:**
- Consumes `farm_service.get_farm(farm_id, user_id)` and `get_farm_weather_summary(farm)`.
- Produces `GET /api/v1/farms/{farm_id}/weather` with `ApiResponse[FarmWeatherSummary]`.

- [ ] **Step 1: Write the failing endpoint test**

```python
def test_weather_endpoint_uses_only_the_current_users_farm(client, auth_headers, owned_farm):
    response = client.get(f"/api/v1/farms/{owned_farm.id}/weather", headers=auth_headers)
    assert response.status_code == 200
    assert "agriculture_advice" not in response.json()["data"]
```

- [ ] **Step 2: Run the test and verify RED**

Run: `pytest tests/services/test_farm_weather.py::test_weather_endpoint_uses_only_the_current_users_farm -q`

Expected: 404 because the route is not registered.

- [ ] **Step 3: Add the async route**

```python
@router.get("/farms/{farm_id}/weather", response_model=ApiResponse[FarmWeatherSummary])
async def get_farm_weather(farm_id: int, current_user: User = Depends(get_current_user)):
    farm = farm_service.get_farm(farm_id, current_user.id)
    summary = await get_farm_weather_summary(farm)
    return ApiResponse.success(data=summary)
```

- [ ] **Step 4: Run the endpoint and service tests**

Run: `pytest tests/services/test_farm_weather.py -q`

Expected: all farm weather tests pass.

- [ ] **Step 5: Commit the completed task**

```powershell
git add app/api/v1/farms.py tests/services/test_farm_weather.py
git commit -m "feat: expose farm weather endpoint"
```

### Task 3: Delete trajectory storage and runtime dependencies

**Files:**
- Create: `alembic/versions/007_remove_trajectory_tables.py`
- Delete: `app/api/v1/trajectories.py`
- Delete: `app/models/trajectory.py`
- Delete: `app/schemas/trajectory.py`
- Delete: `app/services/trajectory_service.py`
- Delete: `app/services/user_context/trajectory_context.py`
- Delete: `scripts/test_trajectory.py`
- Delete: `tests/services/user_context/test_trajectory_context.py`
- Modify: `app/main.py`, `app/core/redis.py`, `app/services/user_context/intent.py`, `app/services/user_context/service.py`, `app/runtime/agent_harness.py`, `scripts/migrate_sqlite_to_mysql.py`, and affected user-context tests.
- Create: `tests/test_migrations.py`

**Interfaces:**
- Produces an Alembic upgrade that removes `trajectory_points` then `trajectory_files`.
- Removes every import and route registration for trajectory runtime code.

- [ ] **Step 1: Write the failing migration test**

```python
def test_upgrade_to_head_does_not_create_trajectory_tables(tmp_path):
    upgrade_database(tmp_path / "farm-refactor.db")
    tables = list_table_names(tmp_path / "farm-refactor.db")
    assert "trajectory_points" not in tables
    assert "trajectory_files" not in tables
    assert {"farms", "fields"}.issubset(tables)
```

- [ ] **Step 2: Run the test and verify RED**

Run: `pytest tests/test_migrations.py::test_upgrade_to_head_does_not_create_trajectory_tables -q`

Expected: failure because `004_add_trajectory` still leaves both tables at head.

- [ ] **Step 3: Implement migration and remove runtime references**

```python
def upgrade() -> None:
    op.drop_index("ix_trajectory_points_file_id", table_name="trajectory_points")
    op.drop_table("trajectory_points")
    op.drop_index("ix_trajectory_files_field_id", table_name="trajectory_files")
    op.drop_table("trajectory_files")
```

Remove the trajectory router import and registration from `app/main.py`, then remove each trajectory-only import discovered by the required full-repository search.

- [ ] **Step 4: Run migration and user-context tests**

Run: `pytest tests/test_migrations.py tests/services/user_context -q`

Expected: migration test and surviving farm-context tests pass with no trajectory imports.

- [ ] **Step 5: Commit the completed task**

```powershell
git add -A
git commit -m "refactor: remove trajectory management"
```

### Task 4: Replace farm frontend contracts and the API client

**Files:**
- Modify: `frontend-react/src/types/farm.ts`
- Modify: `frontend-react/src/api/farms.ts`
- Modify: `frontend-react/src/types/weather.ts`

**Interfaces:**
- Produces `FarmWeatherSummary` with `available`, `reason`, `current`, `alerts`, and `source`.
- Produces `getFarmWeather(farmId: number): Promise<FarmWeatherSummary>`.
- Removes all trajectory types and HTTP functions.

- [ ] **Step 1: Write the TypeScript contract first**

```ts
export interface FarmWeatherSummary {
  available: boolean;
  reason: "FARM_LOCATION_REQUIRED" | "WEATHER_SERVICE_UNAVAILABLE" | null;
  current: FarmWeatherCurrent | null;
  alerts: FarmWeatherAlert[];
  source: string | null;
}
```

- [ ] **Step 2: Run the production typecheck and verify RED**

Run: `cd frontend-react; npx tsc -b`

Expected: the existing farm page cannot resolve removed trajectory contracts.

- [ ] **Step 3: Implement only the API client and domain types**

```ts
export async function getFarmWeather(farmId: number): Promise<FarmWeatherSummary> {
  const response = await authFetch<ApiResponse<FarmWeatherSummary>>(`/farms/${farmId}/weather`);
  return response.data;
}
```

- [ ] **Step 4: Run the typecheck and verify the expected remaining page errors**

Run: `cd frontend-react; npx tsc -b`

Expected: errors are limited to `Farms.tsx` and `FarmMap.tsx`, which Task 5 rewrites.

- [ ] **Step 5: Commit the completed task**

```powershell
git add frontend-react/src/types/farm.ts frontend-react/src/types/weather.ts frontend-react/src/api/farms.ts
git commit -m "refactor: simplify farm frontend contracts"
```

### Task 5: Implement the desktop map-first farm page

**Files:**
- Modify: `frontend-react/src/components/map/FarmMap.tsx`
- Modify: `frontend-react/src/pages/Farms.tsx`
- Delete: `frontend-react/src/components/farm/TrajectoryAnalysis.tsx`
- Modify: `frontend-react/src/pages/Dashboard.tsx`

**Interfaces:**
- Consumes `Farm`, `Field`, `getFarmWeather`, `updateFarm`, and the React Query keys `['farms']`, `['fields', farmId]`, `['farm-weather', farmId]`.
- Produces a desktop page with farm selection, simple fields, weather risk, and draft-position editing.

- [ ] **Step 1: Replace trajectory page state with the required view state**

```ts
const [selectedFarmId, setSelectedFarmId] = useState<number | null>(null);
const [isLocationEditing, setIsLocationEditing] = useState(false);
const [draftPosition, setDraftPosition] = useState<LatLngLiteral | null>(null);
```

- [ ] **Step 2: Run typecheck and verify RED**

Run: `cd frontend-react; npx tsc -b`

Expected: failures until map props, weather card, and CRUD dialogs consume the new state.

- [ ] **Step 3: Implement the focused map and sidebar behaviors**

```tsx
<FarmMap
  farms={farmMarkers}
  selectedFarmId={selectedFarmId}
  isEditing={isLocationEditing}
  draftPosition={draftPosition}
  onDraftPositionChange={setDraftPosition}
  onFarmClick={selectFarm}
/>
```

The map component must use WGS84-compatible base and satellite tiles, contain no trajectory props, and expose marker drag/click events only while editing. `save location` must call `updateFarm` once with the draft coordinates and must not write while dragging.

- [ ] **Step 4: Verify the frontend**

Run: `cd frontend-react; npx tsc -b; npm run build`

Expected: TypeScript and production build succeed.

- [ ] **Step 5: Run scoped lint and commit**

```powershell
npx eslint src/pages/Farms.tsx src/components/map/FarmMap.tsx src/api/farms.ts src/types/farm.ts src/types/weather.ts
git add frontend-react/src/pages/Farms.tsx frontend-react/src/components/map/FarmMap.tsx frontend-react/src/components/farm/TrajectoryAnalysis.tsx frontend-react/src/pages/Dashboard.tsx frontend-react/src/api/farms.ts frontend-react/src/types/farm.ts frontend-react/src/types/weather.ts
git commit -m "feat: redesign farm management workspace"
```

### Task 6: Final integration sweep and documentation sync

**Files:**
- Modify: `docs/architecture.md`, `docs/CROSS_MODULE_DATA_SHARING.md`
- Modify: `docs/superpowers/specs/2026-07-29-farm-protection-management-design.md` only if implementation intentionally changes an approved contract.

**Interfaces:**
- Produces documentation that no longer describes trajectory management as an active farm capability.

- [ ] **Step 1: Search for remaining active trajectory references**

Run:

```powershell
rg -n -S "TrajectoryFile|TrajectoryPoint|trajectory_files|trajectory_points|trajectory|轨迹" app frontend-react tests scripts
```

Expected: no active runtime references; historical migration and retired-feature documentation references are allowed only when clearly historical.

- [ ] **Step 2: Update active architecture documentation**

Change farm capability descriptions to “农场位置、地块档案与天气风险”, and remove trajectory API and UI claims.

- [ ] **Step 3: Execute the final verification matrix**

```powershell
pytest
Set-Location frontend-react
npm run lint
npm run build
Set-Location ..
alembic upgrade head
```

Expected: the final report records command output, any unrelated pre-existing lint failures, and whether a configured Python runtime was available.

- [ ] **Step 4: Commit the completed task**

```powershell
git add docs
git commit -m "docs: update farm management architecture"
```

## Plan Self-Review

### Spec coverage

- Map-first desktop layout, multi-farm switching, draft positioning, simple fields, and weather risk are covered by Task 5.
- Authorized weather aggregation and advice filtering are covered by Tasks 1 and 2.
- Destructive trajectory deletion, migration order, and user-context cleanup are covered by Task 3.
- WGS84 coordinate consistency and no mobile work are global constraints and Task 5 requirements.
- API/client contracts are covered by Tasks 2 and 4.
- Documentation, repository sweep, builds, tests, and migration verification are covered by Task 6.

### Placeholder scan

The plan contains no unassigned work markers and each implementation task declares its affected files, exported interface, test command, and commit command.

### Type consistency

- Backend returns `FarmWeatherSummary`; frontend uses the same response name and field set.
- `getFarmWeather(farmId)` calls the route registered in Task 2.
- Map draft state uses `LatLngLiteral` and maps to `FarmUpdateRequest.latitude` and `FarmUpdateRequest.longitude` only on save.
