# Track 0: Fixtures and Ground Truth

## What is a Fixture?
A fixture is a fixed, known set of data used as a baseline for tests. Instead of testing our code on massive, unpredictable real-world data, we create a tiny, synthetic world where we mathematically know the correct answer.

## Why do we need it here?
When our graph logic tells us "3 settlements are cut off," we can't manually verify that on a 100km valley. By creating a synthetic `(nodes, edges, settlements, flood_mask)` where exactly two roads are broken and one hospital exists, we can write robust assertions. If the test passes on the fixture, we trust the algorithm on real data.

## Example
```python
import geopandas as gpd
from shapely.geometry import Point

# A tiny known world
settlements = gpd.GeoDataFrame({
    "id": [1, 2],
    "geometry": [Point(0, 0), Point(10, 0)]
})
# We know settlement 1 is at 0,0. We can test our logic against this exact coordinate.
```

## Quiz
1. **Why not just use real Sentinel data for our tests?**
2. **If we add a new routing feature later, how does the fixture help?**
3. **Should our fixture use geographic (lat/lon) or projected (UTM/meters) coordinates?**

<details>
<summary>Answers</summary>

1. Real data is too large, changes often, and finding edge cases manually is error-prone. A fixture is fast and deterministic.
2. It acts as a regression test: if the new feature breaks the known baseline, we immediately know the logic is flawed.
3. Projected (meters). We need to test metric operations like lengths, areas, and buffers without CRS distortion.
</details>
