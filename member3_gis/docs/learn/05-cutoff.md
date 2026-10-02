# Cut-off Engine: Who is cut off?

The Cut-off Engine is the analytical core of the system. It bridges the mathematical road network (Track B) with the raster flood polygons (Track D) and OpenStreetMap points of interest (Track A) to determine exactly which communities have lost access to critical infrastructure.

## Multi-source Dijkstra (The Super-Destination)
To find out if a settlement can reach *any* town or hospital, we don't need to run a shortest-path algorithm to every destination separately. Instead, we add a virtual **super-destination** node to our graph. We add zero-weight edges connecting this super-destination to all actual towns and hospitals. A single Dijkstra shortest-path search from all nodes to the super-destination instantly gives us the distance to the *nearest* town or hospital for every node in the graph.

## The Before & After Paradigm
We run the routing twice:
1. **Before Scenario**: The baseline graph with no flooded edges removed.
2. **After Scenario**: The flooded graph, where any road edge whose geometry intersects a flood polygon is deleted.

By comparing the results, we classify each settlement:
- `CONNECTED`: Reachable before AND after.
- `POTENTIALLY_CUT_OFF`: Reachable before, but NOT after.
- `NO_MAPPED_ROAD_ACCESS`: The settlement is too far from any mapped road (e.g., >500m). This often happens in sparse OSM data regions.
- `INSIDE_FLOOD_ZONE`: A modifier flag indicating the settlement point itself is submerged.

## Unassessed Areas and "UNKNOWN" Status
If a settlement is still technically reachable in the "After" scenario, but its route passes through a radar shadow or cloud (unassessed area), we cannot guarantee it is safe. We flag these routes as `UNKNOWN_NO_DATA` to warn responders of a potential hidden cut-off.

## Sensitivity Analysis
Is a road *definitely* cut off if a flood polygon barely touches it? To provide a robust confidence metric, we rerun the "After" scenario with varying buffer sizes and intersection overlaps. The percentage of runs that result in a cut-off yields a **confidence score**. A score >= 0.8 is considered `ROBUST`, while < 0.8 is `SENSITIVE` to the exact boundaries of the flood mask.
