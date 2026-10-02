# Graph Builder: Noding and Snapping

To run routing algorithms (like shortest path to a hospital), we must convert independent OpenStreetMap linestrings into a connected mathematical graph.

## The Problem: Digitisation Jitter and Overlaps

OpenStreetMap roads are drawn by human volunteers. Often:
1. Two roads might intersect visually, but there is no vertex at the intersection point. 
2. Two roads might be meant to connect (e.g. a side road joining a main road) but the side road's endpoint falls slightly short (by a meter or two) due to digitisation jitter.

## 1. Snapping

Before building the graph, we must **snap** loose endpoints. 
If an endpoint of a road is within a small tolerance (default: 5 metres) of another road, we modify the geometry to extend the endpoint so it exactly touches the other road.

*Note on Coordinates:* Snapping must be done in a projected coordinate system (like UTM) where Euclidean distances correspond to real-world metres. If the data is in geographic coordinates (EPSG:4326), we temporarily project it to local UTM, apply the snapping, and project it back.

## 2. Noding

**Noding** is the process of splitting linestrings wherever they intersect or touch.
In Shapely 2.0, this is easily achieved using the `shapely.node()` function.
For example, if two roads cross in the middle forming an "X", noding will split them at the intersection point, resulting in 4 separate linestrings meeting at a common central vertex.
Noding is idempotent: noding an already noded network yields the same network.

## 3. Building the NetworkX Graph

Once the geometries are snapped and noded:
1. Every linestring becomes an edge.
2. The endpoints of the linestring become nodes (vertices).
3. We use an undirected `nx.MultiGraph` because there might be multiple parallel roads between the same two intersections (e.g. dual carriageways, overpasses).
4. Edge attributes like `length_m`, `highway` class, and `is_bridge` are preserved or calculated.

## Example
If Road A is `[(0,0), (10,0)]` and Road B is `[(5,5), (5, 0.5)]`:
- Without snapping, they are disconnected.
- With 1m snapping tolerance, Road B's endpoint `(5, 0.5)` snaps to the nearest point on Road A, which is `(5, 0)`.
- Noding then splits Road A at `(5, 0)`.
- Result: 3 edges `[(0,0), (5,0)]`, `[(5,0), (10,0)]`, and `[(5,5), (5,0)]`, all correctly connected at node `(5,0)`.
