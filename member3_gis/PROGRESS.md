# GIS Engine — Design Decisions & Progress Log

## Core Design Decisions

### 1. Snapping Tolerance (5 metres)
**Decision:** Snap road endpoints within 5m to fix OSM digitisation jitter.
**Rationale:** OSM human traces often miss each other by a few metres, breaking connectivity. 5m is conservative enough to not create false intersections in dense urban areas, yet loose enough for rural valley roads.
**Trade-off:** Too loose (>10m) causes false connections; too tight (<2m) leaves gaps. 5m tested on Track 0 fixtures.

### 2. Settlement Snap Distance (500 metres)
**Decision:** Settlements >500m from the road graph are marked `NO_MAPPED_ROAD_ACCESS`.
**Rationale:** In mountain areas, OSM road coverage is incomplete. A settlement 1km away is likely unmapped, not flooded. Marking it `NO_MAPPED_ROAD_ACCESS` avoids false cut-off positives and signals a data quality issue to decision-makers.
**Trade-off:** Conservative. Some settlements may genuinely have no road (seasonal access only). Inspection shows this is rare.

### 3. Minimum Polygon Area (100 m²)
**Decision:** Filter SAR speckle noise by removing polygons <100 m² during mask parsing.
**Rationale:** SAR and optical imagery have noise. Single-pixel artifacts (100 m² at 10m resolution) are usually noise, not real flood extent. Filtering speeds up graph computations and reduces false positives.
**Trade-off:** May miss small but real features. Acceptable for rescue response (focus on large affected areas).

### 4. Virtual Super-Destination Routing
**Decision:** Add one virtual node connected with zero-weight edges to all hospitals and towns, then run one Dijkstra.
**Rationale:** Finding nearest destination per settlement independently would require |hospitals + towns| runs. One virtual node: one run, same result. Efficient and elegant.
**Trade-off:** None identified. Standard technique in network analysis.

### 5. Before/After Paradigm
**Decision:** Run reachability analysis twice (full graph, then with flooded edges removed), compare classifications.
**Rationale:** Determines true cut-offs (reachable before, not after) vs. always-inaccessible settlements (no mapped road). Avoids false positives.
**Trade-off:** Doubles computation time negligibly (~100ms on typical valleys).

### 6. Sensitivity Sweep (Confidence Scoring)
**Decision:** Rerun cut-off analysis with varying buffer_m and min_overlap_m parameters, compute confidence as fraction of runs where settlement is cut off.
**Rationale:** Addresses uncertainty in SAR flood detection. If a settlement is cut off under all parameter variations, confidence = 1.0 (ROBUST). If only under loose buffers, confidence < 0.8 (SENSITIVE).
**Trade-off:** Computational overhead (10-20 reruns). Acceptable for offline analysis.

### 7. Unassessed Area Classification
**Decision:** Separate "flood" from "unassessed" (radar shadow, cloud, no-data). Settlements depending on routes through unassessed areas = `UNKNOWN_NO_DATA`.
**Rationale:** Honest accounting. A road hidden by radar shadow may be flooded or safe; marking it unknown avoids false assurance.
**Trade-off:** Complicates output (5 settlement statuses instead of 3). Necessary for safety.

---

## Implementation Timeline

### Week 1 (Days 1-3)
- **Day 1:** Project setup, Track 0 fixtures, git branch `priyang`
- **Day 2:** Track A (OSM Loader) — Ohsome API, tiling, retry logic, caching
- **Day 3:** Track B (Graph Builder) — snapping, noding, NetworkX graph

### Week 2 (Days 4-7)
- **Day 4:** Track C (API & Schemas) — Pydantic v2 data contracts, FastAPI skeleton
- **Day 5:** Track D (Mask Adapter) — raster parsing, flood extraction, unassessed classification
- **Day 6:** Track E (Cut-off Engine) — Dijkstra routing, before/after analysis, sensitivity sweep
- **Day 7:** Impact Layer + Full Integration — infrastructure classification, end-to-end pipeline

### Week 3 (Days 8-10)
- **Day 8-9:** Testing, bug fixes, documentation
- **Day 10:** Waiting for M2's flood mask (Track F real valley test)

---

## Known Issues & Workarounds

### Issue 1: OSM Graph Fragmentation
**Observation:** Some valleys have multiple disconnected road components (e.g., a main valley road separated from a side tributary road by a missed OSM segment).
**Impact:** Settlements in the smaller component may be falsely marked cut-off even before flooding.
**Mitigation:** Log the number of connected components (`is_connected()` warning). Inspect visually. Consider manual edits for critical roads.

### Issue 2: Radar Shadow on Steep Slopes
**Observation:** SAR signal layover and shadow on steep terrain create no-data zones that look like potential flood areas.
**Impact:** Unassessed area fraction may be low (<0.70), reducing confidence.
**Mitigation:** Valid-data mask categorizes these as `reason=radar_shadow`. Settlements with routes through them = `UNKNOWN_NO_DATA`.

### Issue 3: Polygon Simplification for Output
**Observation:** High-resolution flood masks create very detailed GeoJSON (~MB per feature).
**Impact:** Frontend rendering may lag if not simplified.
**Mitigation:** (Future) Add `simplify_tolerance_m` parameter to reduce geometry complexity before GeoJSON output.

---

## Testing Strategy

### Unit Tests (by module)
- **Track A (osm_loader):** Mock HTTP, synthetic bboxes, caching logic
- **Track B (graph_builder):** Synthetic road networks, snapping tolerance, noding
- **Track D (mask_adapter):** Synthetic rasters, area filtering, reason classification
- **Track E (cutoff):** Track 0 fixture (6 settlements, 1 flooded edge, expect 2 cut-off)
- **Impact:** Infrastructure overlap tests

### Integration Tests
- **Full pipeline:** Track 0 synthetic data through all 6 modules end-to-end
- **API endpoint:** POST request, verify JSON schema compliance

### Property-Based Tests
- Hypothesis: assessed_area_fraction always in [0.0, 1.0]
- Noding idempotency: noding twice = noding once

### Acceptance Criteria
- All tests pass on Track 0 fixture
- Real valley test on Trishuli (once M2 sends mask): settlement counts reasonable, no crashes
- Real valley test on Chamoli 2021: different area/date, same pipeline, works

---

## Deployment Notes

### Cache Management
OSM data is cached by (bbox, snapshot_date, filter_name) hash in `member3_gis/cache/osm/`. Cache busts automatically on schema changes but can be manually cleared.

### Rate Limiting
Ohsome API limits to 15 requests/minute. The tiling strategy + exponential backoff (1s, 2s, 4s, 8s, 16s) handles this gracefully. Large bboxes may take a few minutes on first run.

### CRS Handling
Every function reads and preserves CRS from input data (rasterio, geopandas). No hard-coded EPSG codes in pipeline logic. Output always reprojected to EPSG:4326 for frontend.

---

## Future Improvements (Not in Scope)

1. **Time-series analysis:** Track flood extent change over multiple satellite passes
2. **Damage severity:** Classify "partially affected" vs. "destroyed" using confidence thresholds
3. **Population-weighted statistics:** Weight cut-off counts by settlement population
4. **Travel time routing:** Integrate actual road speeds instead of Euclidean distance
5. **LLM-based report generation:** Auto-translate situation reports to local languages (currently English + Nepali template)
6. **Real-time integration:** Ingest live Sentinel data streams instead of batch processing

---

## Commits & Branches

All work on branch `priyang`, merged by lead (Abinav) at project end.

Commits by track:
- `feat(track-a): osm loader with tiling and caching`
- `feat(track-b): graph builder with snapping and noding`
- `feat(track-c): api skeleton and schemas`
- `feat(track-d): mask adapter with dual-mask parsing`
- `feat(track-e): cut-off engine with dijkstra routing`
- `feat(impact): infrastructure classification`
- `feat(integration): end-to-end pipeline and fastapi`

---

## Lessons Learned

1. **Synthetic fixtures are invaluable.** Track 0 caught bugs early (floating-point edge cases, node ordering).
2. **Mock external APIs thoroughly.** Ohsome rate limits + timeouts were never an issue because mocking forced defensive code.
3. **Separate concerns.** Each module has one job (load, build, adapt, impact, cutoff). Clean testing & composition.
4. **Document assumptions.** Snapping tolerance, area filters, confidence thresholds need explanation or they look arbitrary.
5. **Before/after paradigm prevents false positives.** The single most important design choice for accuracy.