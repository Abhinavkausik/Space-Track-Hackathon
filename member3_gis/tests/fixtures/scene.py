import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString, Polygon

CRS = "EPSG:32645"

def get_fixture_data():
    # Nodes
    # Main highway
    A, B, C, D, E = Point(0, 0), Point(100, 0), Point(200, 0), Point(300, 0), Point(400, 0)
    # Branch 1 (gets cut)
    F, G, K = Point(100, 100), Point(100, 200), Point(100, 300)
    # Branch 2 (with bridge)
    H, I = Point(300, 100), Point(300, 200)
    # Branch 3
    J = Point(200, -100)

    # Roads
    roads = [
        {"id": "R1", "geometry": LineString([A, B]), "highway": "primary", "bridge": False},
        {"id": "R2", "geometry": LineString([B, C]), "highway": "primary", "bridge": False},
        {"id": "R3", "geometry": LineString([C, D]), "highway": "primary", "bridge": False},
        {"id": "R4", "geometry": LineString([D, E]), "highway": "primary", "bridge": False},
        {"id": "R5", "geometry": LineString([B, F]), "highway": "secondary", "bridge": False},
        {"id": "R6", "geometry": LineString([F, G]), "highway": "secondary", "bridge": False}, # Gets cut
        {"id": "R7", "geometry": LineString([G, K]), "highway": "secondary", "bridge": False},
        {"id": "R8", "geometry": LineString([D, H]), "highway": "tertiary", "bridge": False},
        {"id": "R9", "geometry": LineString([H, I]), "highway": "tertiary", "bridge": True},
        {"id": "R10", "geometry": LineString([C, J]), "highway": "track", "bridge": False},
    ]
    roads_gdf = gpd.GeoDataFrame(roads, crs=CRS)

    # Destinations (Hospitals / Towns)
    # A is a hospital, E is a town
    destinations = [
        {"id": "H1", "geometry": A, "type": "hospital", "name": "Alpha Hosp"},
        {"id": "T1", "geometry": E, "type": "town", "name": "Echo Town"},
    ]
    dest_gdf = gpd.GeoDataFrame(destinations, crs=CRS)

    # Settlements
    # S1 at A (0,0) - connected
    # S2 at G (100,200) - gets cut
    # S3 at K (100,300) - gets cut
    # S4 at I (300,200) - connected
    # S5 at J (200,-100) - connected
    # S6 at (1000, 1000) - no road mapped
    settlements = [
        {"id": "S1", "geometry": Point(0, 5), "name": "S1_Conn"},
        {"id": "S2", "geometry": Point(105, 200), "name": "S2_Cut"},
        {"id": "S3", "geometry": Point(100, 305), "name": "S3_Cut"},
        {"id": "S4", "geometry": Point(300, 205), "name": "S4_Conn"},
        {"id": "S5", "geometry": Point(205, -100), "name": "S5_Conn"},
        {"id": "S6", "geometry": Point(1000, 1000), "name": "S6_NoRoad"},
    ]
    settlements_gdf = gpd.GeoDataFrame(settlements, crs=CRS)

    # Flood Polygon (intersects R6)
    # R6 goes from (100,100) to (100,200).
    # A box from x 50 to 150, y 140 to 160 intersects R6.
    flood = [
        {"id": "F1", "geometry": Polygon([(50, 140), (150, 140), (150, 160), (50, 160)])}
    ]
    flood_gdf = gpd.GeoDataFrame(flood, crs=CRS)

    return roads_gdf, dest_gdf, settlements_gdf, flood_gdf
