# System Limitations & Known Constraints

## 1. OpenStreetMap Completeness
Remote mountain settlements may be unmapped, incompletely positioned, or tagged incorrectly in OSM. This causes false `NO_MAPPED_ROAD_ACCESS` classifications. Always assess local OSM quality before deployment.

**Mitigation:** Compare settlement counts with local authorities. Flag settlements >500m from the road network for manual verification.

## 2. Overlap ≠ Destruction
A road, bridge, or building whose geometry overlaps the flood polygon is marked "potentially affected" but may still be passable. Overlap is a statistical flag, not proof of destruction.

**Mitigation:** Field teams must verify critical infrastructure before reopening. The system prioritizes false positives (safety) over false negatives.

## 3. Satellite Revisit Intervals
Sentinel-1 SAR revisits an area every 12 days, Sentinel-2 optical every 5-10 days (weather-dependent). This system is NOT a real-time minute-ahead warning for sudden glacier collapse or flash floods.

**Mitigation:** Use this for post-event damage assessment, not early warning. For real-time alerts, integrate with ground sensors or weather radar.

## 4. Unassessed Areas (Radar Shadow & Cloud)
Steep mountain terrain causes SAR radar shadow. Monsoon clouds obscure optical imagery. The `assessed_area_fraction` metric (e.g., 0.98 = 98% observed) quantifies data gaps. Routes through unassessed areas are flagged `UNKNOWN_NO_DATA`.

**Mitigation:** Prioritize roads in well-assessed areas. Flag cut-off settlements that depend on unassessed routes as "confidence: sensitive."

## 5. Snapping Tolerance & Graph Artifacts
Road networks are snapped within 5 metres tolerance to fix OSM digitisation jitter. In areas with sparse or fragmented road data, this may artificially connect or separate settlements.

**Mitigation:** Visual inspection of the road graph for unrealistic connections. Manual override if needed.

## 6. Flood Mask Quality Dependency
The entire analysis depends on the accuracy of the AI flood/debris detector (Track E). SAR speckle noise, radar shadow, and phase unwrapping errors can produce false positives.

**Mitigation:** Always inspect the flood polygon visually. Cross-reference with Copernicus EMS or UNOSAT maps for validation (comparison only, not as input).

## 7. Computational Assumptions
- Graph shortest paths assume Euclidean distance / road length, not travel time or actual driving routes.
- No consideration for road condition (landslide damage reduces passability even if not flooded).
- Assumes settlements stay in place (no evacuation or relocation).

## 8. Data Currency
The OSM snapshot date is fixed at event_date - 1 day. Any post-event OSM edits are excluded (correct). Pre-event data may be weeks or months old, especially in remote areas.

**Mitigation:** Verify settlement names, populations, and accessibility against recent ground surveys.

## When This System Is Most Reliable
- Large, well-mapped valleys (Nepal's major corridors, Uttarakhand tourist routes)
- Floods with clear SAR signatures (standing water, debris fans)
- Areas with dense OSM coverage (>80% of roads mapped)
- Post-event analysis (12+ days after flood, when satellite revisit occurs)

## When to Use Human Judgment
- Sparse OSM regions (<50% road coverage)
- Ambiguous SAR signatures (radar shadow near flood)
- Critical decisions (hospital evacuation, lifeline routing)
- Unassessed area fraction <0.70 (less than 70% of bbox clearly observed)