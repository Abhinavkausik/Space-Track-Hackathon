import pytest
import datetime
from unittest.mock import patch, MagicMock
from gis_engine.loaders.osm_loader import load_osm_data, _create_tiles, _generate_cache_key
import geopandas as gpd
from shapely.geometry import Point

@pytest.fixture
def mock_ohsome_response():
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [85.3, 27.7]},
                "properties": {"highway": "primary", "name": "Test Road"}
            }
        ]
    }

def test_create_tiles():
    bbox = (85.2, 27.6, 85.4, 27.8)
    tiles = _create_tiles(bbox, step=0.1)
    assert len(tiles) == 4
    assert tiles[0] == (85.2, 27.6, 85.3, 27.7)

def test_generate_cache_key():
    bbox = (85.2, 27.6, 85.4, 27.8)
    snapshot = datetime.datetime(2015, 4, 1, tzinfo=datetime.timezone.utc)
    key1 = _generate_cache_key(bbox, snapshot, "highways")
    key2 = _generate_cache_key(bbox, snapshot, "buildings")
    assert key1 != key2

@patch("gis_engine.loaders.osm_loader.requests.post")
def test_load_osm_data_mocked(mock_post, mock_ohsome_response, tmp_path):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_ohsome_response
    mock_post.return_value = mock_response

    with patch("gis_engine.loaders.osm_loader._get_cache_dir", return_value=tmp_path):
        bbox = (85.3, 27.7, 85.35, 27.75) # Small bbox, 1 tile
        snapshot = datetime.datetime(2015, 4, 1, tzinfo=datetime.timezone.utc)
        event = datetime.datetime(2015, 4, 25, tzinfo=datetime.timezone.utc)
        
        result = load_osm_data(bbox, snapshot, event, cache_bust=True)
        
        assert "highways" in result
        assert "buildings" in result
        
        highways = result["highways"]
        assert isinstance(highways, gpd.GeoDataFrame)
        assert len(highways) == 1
        assert "highway" in highways.columns
        assert highways.iloc[0]["name"] == "Test Road"
        
        buildings = result["buildings"]
        assert isinstance(buildings, gpd.GeoDataFrame)
        # It's mocked with the same response, so it has 1 point too, but different expected columns
        # However, Ohsome returns properties regardless of the filter if mocked this simply
        # In reality, it returns what matches the filter.
        assert len(buildings) == 1

def test_load_osm_data_asserts_dates():
    bbox = (85.3, 27.7, 85.35, 27.75)
    snapshot = datetime.datetime(2015, 4, 25, tzinfo=datetime.timezone.utc)
    event = datetime.datetime(2015, 4, 1, tzinfo=datetime.timezone.utc)
    
    with pytest.raises(AssertionError, match="snapshot_date must be earlier than event_date"):
        load_osm_data(bbox, snapshot, event, cache_bust=True)

@pytest.mark.network
def test_load_osm_data_live(tmp_path):
    # Very small bbox to ensure fast, safe request
    bbox = (85.3, 27.7, 85.31, 27.71)
    snapshot = datetime.datetime(2015, 4, 1, tzinfo=datetime.timezone.utc)
    event = datetime.datetime(2015, 4, 25, tzinfo=datetime.timezone.utc)
    
    with patch("gis_engine.loaders.osm_loader._get_cache_dir", return_value=tmp_path):
        result = load_osm_data(bbox, snapshot, event, cache_bust=True)
        
        assert "highways" in result
        assert isinstance(result["highways"], gpd.GeoDataFrame)
        assert "highway" in result["highways"].columns
