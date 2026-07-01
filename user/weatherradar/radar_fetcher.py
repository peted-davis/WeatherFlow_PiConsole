""" Weather Radar panel helper for the Raspberry Pi Python console for
WeatherFlow Tempest and Smart Home Weather stations.

Fetches radar tile frames from the free RainViewer API and composites them
onto OpenStreetMap base tiles using Pillow.  Output is a list of PNG file
paths that the WeatherRadarPanel cycles through as an animation.

Free data sources (no API key required):
  - Radar:    https://www.rainviewer.com/api.html
  - Geocode:  https://api.zippopotam.us/
  - Base map: https://tile.openstreetmap.org/ (OSM tile usage policy applies)

Dependencies:
  pip install Pillow requests
"""

import io
import json
import math
import os

import requests
from PIL import Image

# ---------------------------------------------------------------------------
# Paths relative to this file's directory
# ---------------------------------------------------------------------------
_HERE         = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH   = os.path.join(_HERE, 'weatherradar_config.json')
FRAMES_DIR    = os.path.join(_HERE, 'frames')
BASE_MAP_PATH = os.path.join(_HERE, 'base_map.png')
BASE_KEY_PATH = os.path.join(_HERE, 'base_map_key.txt')

_HEADERS       = {'User-Agent': 'WeatherFlow-PIConsole/RadarPanel/1.0 (personal use)'}
_RAINVIEWER    = 'https://api.rainviewer.com/public/weather-maps.json'
_ZIPPOPOTAM   = 'https://api.zippopotam.us/{country}/{zip}'
_OSM_TILE     = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
_RADAR_TILE   = '{host}{path}/512/{z}/{x}/{y}/{color}/{smooth}_{snow}.png'
_TILE_PX      = 256   # OSM tiles are always 256 px; RainViewer 512 px tiles are scaled down


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def load_config():
    """Return the parsed weatherradar_config.json dict."""
    with open(CONFIG_PATH, 'r') as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------
def zip_to_coords(zip_code, country='us'):
    """Return (lat, lng) floats for a postal code via zippopotam.us."""
    url  = _ZIPPOPOTAM.format(country=country, zip=zip_code)
    resp = requests.get(url, timeout=10, headers=_HEADERS)
    resp.raise_for_status()
    place = resp.json()['places'][0]
    return float(place['latitude']), float(place['longitude'])


def coords_to_tile(lat, lng, zoom):
    """Convert (lat, lng) to Web Mercator tile (x, y) at *zoom*."""
    lat_r = math.radians(lat)
    n     = 2 ** zoom
    tx    = int((lng + 180.0) / 360.0 * n)
    ty    = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return tx, ty


# ---------------------------------------------------------------------------
# Internal tile fetch
# ---------------------------------------------------------------------------
def _fetch_image(url, timeout=15):
    """GET *url* and return a PIL RGBA Image."""
    resp = requests.get(url, timeout=timeout, headers=_HEADERS)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert('RGBA')


# ---------------------------------------------------------------------------
# OSM base map
# ---------------------------------------------------------------------------
def _ensure_base_map(tile_x, tile_y, zoom, grid_size):
    """
    Return a stitched OSM base-map PIL Image for the given tile grid,
    rebuilding it only when the view parameters change.
    """
    os.makedirs(FRAMES_DIR, exist_ok=True)
    key = f'{zoom}_{tile_x}_{tile_y}_{grid_size}'

    cached_key = ''
    if os.path.exists(BASE_KEY_PATH):
        with open(BASE_KEY_PATH) as fh:
            cached_key = fh.read().strip()

    if cached_key == key and os.path.exists(BASE_MAP_PATH):
        return Image.open(BASE_MAP_PATH).convert('RGBA')

    print(f'[WeatherRadar] Rebuilding base map zoom={zoom} grid={grid_size}x{grid_size}')
    half   = grid_size // 2
    size   = _TILE_PX * grid_size
    canvas = Image.new('RGBA', (size, size))

    for row in range(grid_size):
        for col in range(grid_size):
            tx  = tile_x - half + col
            ty  = tile_y - half + row
            url = _OSM_TILE.format(z=zoom, x=tx, y=ty)
            try:
                tile = _fetch_image(url)
                tile = tile.resize((_TILE_PX, _TILE_PX), Image.LANCZOS)
                canvas.paste(tile, (col * _TILE_PX, row * _TILE_PX))
            except Exception as exc:
                print(f'[WeatherRadar] OSM tile {zoom}/{tx}/{ty} failed: {exc}')

    canvas.save(BASE_MAP_PATH)
    with open(BASE_KEY_PATH, 'w') as fh:
        fh.write(key)
    return canvas


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def fetch_radar_frames(config):
    """
    Fetch RainViewer radar frames and composite with the OSM base map.

    Returns a list of absolute paths to rendered PNG frames (oldest → newest).
    Returns an empty list on any unrecoverable error.
    """
    try:
        zip_code    = str(config.get('zip_code', ''))
        country     = config.get('country', 'us')
        zoom        = int(config.get('zoom', 7))
        grid_size   = int(config.get('tile_grid', 3))
        past_frames = int(config.get('past_frames', 12))
        color       = int(config.get('color_scheme', 6))
        smooth      = int(config.get('smooth', 1))
        snow        = int(config.get('snow', 0))
        half        = grid_size // 2

        lat, lng           = zip_to_coords(zip_code, country)
        tile_x, tile_y     = coords_to_tile(lat, lng, zoom)
        base               = _ensure_base_map(tile_x, tile_y, zoom, grid_size)

        rv        = requests.get(_RAINVIEWER, timeout=10, headers=_HEADERS)
        rv.raise_for_status()
        rv_data   = rv.json()
        host      = rv_data['host']
        meta_list = rv_data['radar']['past'][-past_frames:]

        if not meta_list:
            print('[WeatherRadar] RainViewer returned no radar frames')
            return []

        os.makedirs(FRAMES_DIR, exist_ok=True)
        frame_paths = []

        for i, meta in enumerate(meta_list):
            frame = base.copy()

            for row in range(grid_size):
                for col in range(grid_size):
                    tx  = tile_x - half + col
                    ty  = tile_y - half + row
                    url = _RADAR_TILE.format(
                        host=host, path=meta['path'],
                        z=zoom, x=tx, y=ty,
                        color=color, smooth=smooth, snow=snow)
                    try:
                        radar = _fetch_image(url)
                        # RainViewer tiles are 512 px; scale to match OSM
                        radar = radar.resize((_TILE_PX, _TILE_PX), Image.LANCZOS)
                        frame.paste(radar,
                                    (col * _TILE_PX, row * _TILE_PX),
                                    radar)          # alpha channel as mask
                    except Exception as exc:
                        print(f'[WeatherRadar] Radar tile error: {exc}')

            out_path = os.path.join(FRAMES_DIR, f'frame_{i:02d}.png')
            frame.convert('RGB').save(out_path)
            frame_paths.append(out_path)

        print(f'[WeatherRadar] {len(frame_paths)} frames ready')
        return frame_paths

    except Exception as exc:
        print(f'[WeatherRadar] fetch_radar_frames failed: {exc}')
        return []
