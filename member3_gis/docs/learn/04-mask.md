# Mask Adapter: Translating Raster to Vector

In this system, flood detections arrive as GeoTIFF files. To interact with vector infrastructure (like OpenStreetMap roads or hospitals), we must convert these raster pixels into vector polygons.

## The Dual Mask Approach

Our Earth Observation pipeline (Sentinel-1 SAR) produces two companion masks:
1. **Flood Mask**: A categorical mask where `1` = flooded/debris, `0` = no flood, and `255` = missing data.
2. **Valid Data Mask**: A categorical mask indicating radar artifacts where `0` = valid data, `1` = no data, `2` = radar shadow, and `3` = cloud.

## Understanding Unassessed Areas

SAR imagery cannot see everything. Steep valleys cause **radar shadows**, and although SAR penetrates clouds, certain artifacts or lack of coverage can leave blind spots.

Why do unassessed areas matter for cut-off analysis?
If a road passes through a radar shadow, we **cannot confidently say it is dry**. If it's a critical lifeline, treating unassessed areas as "safe" is dangerous. Our system extracts both flood polygons and unassessed polygons (annotated with a `reason`) so downstream analysis can flag infrastructure that is potentially at risk but visually unconfirmed.

### Extraction Logic
- **Flooded Pixels**: `(flood_mask == 1) AND (valid_mask == 0)`
- **Unassessed Pixels**: `(flood_mask == 255) OR (valid_mask != 0)`

## Polygonization and Filtering

We convert the thresholded binary masks into vector polygons using `rasterio.features.shapes`. 
SAR can be noisy (speckle), often producing solitary 1-pixel "floods". We apply a minimum area filter (e.g., removing polygons < 100 m²) to eliminate these spurious artifacts and reduce computational overhead for the graph analysis.

## Assessed Area Fraction

To give decision-makers confidence in the output, we compute an `assessed_area_fraction`:
`assessed_area_fraction = area(valid_mask == 0) / total_bbox_area`
A fraction of 0.9 means 90% of the bounding box was successfully analyzed by radar.
