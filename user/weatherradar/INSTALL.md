# Weather Radar Panel — Installation Guide

Adds a looping radar animation panel to the WeatherFlow PiConsole.  
Data comes from the free [RainViewer API](https://www.rainviewer.com/api.html) overlaid on OpenStreetMap tiles.  
No API keys are needed.

---

## Files

```
user/
  customPanels.py            ← panel Python classes
  customPanels.kv            ← panel Kivy UI definition
  weatherradar/
    __init__.py
    radar_fetcher.py         ← tile fetching & compositing logic
    weatherradar_config.json ← your configuration (edit this)
    frames/                  ← created at runtime (PNG frame cache)
    base_map.png             ← created at runtime (OSM tile cache)
```

---

## Step 1 — Copy files to the Raspberry Pi

From your development machine (replace `pi@raspberrypi.local` with your Pi's address):

```bash
# Copy the user folder contents
scp -r user/customPanels.py   pi@raspberrypi.local:~/wfpiconsole/user/
scp -r user/customPanels.kv   pi@raspberrypi.local:~/wfpiconsole/user/
scp -r user/weatherradar/     pi@raspberrypi.local:~/wfpiconsole/user/
```

Or copy via USB / SD card if you prefer.

---

## Step 2 — Install Python dependencies

SSH into the Pi and run:

```bash
pip install Pillow requests
```

Both packages are small and install quickly.  
`requests` may already be present; `Pillow` handles image compositing.

---

## Step 3 — Edit the configuration

Open `~/wfpiconsole/user/weatherradar/weatherradar_config.json` on the Pi:

```json
{
    "zip_code": "29403",
    "country": "us",
    "zoom": 7,
    "tile_grid": 3,
    "refresh_interval": 300,
    "past_frames": 12,
    "color_scheme": 6,
    "smooth": 1,
    "snow": 0,
    "frame_delay": 0.2
}
```

| Key | Description | Recommended values |
|-----|-------------|-------------------|
| `zip_code` | Your US postal code | any valid ZIP |
| `country` | Country code for zippopotam.us | `us`, `ca`, `gb`, etc. |
| `zoom` | Map zoom level | `6`–`9` (7 = regional ~300 mi wide per tile) |
| `tile_grid` | Grid of tiles around center (N×N) | `1`–`5` (3 = good regional view) |
| `refresh_interval` | Seconds between data refreshes | `300` (RainViewer updates every 5 min) |
| `past_frames` | How many historical frames to animate | `6`–`13` |
| `color_scheme` | RainViewer color palette (0–8) | `6` = vivid, `1` = original |
| `smooth` | Smooth radar edges (0 or 1) | `1` |
| `snow` | Show snow as separate color (0 or 1) | `0` |
| `frame_delay` | Seconds between animation frames | `0.15`–`0.4` |

**Coverage guide for `zoom` + `tile_grid`:**

| zoom | Single tile width | 3×3 grid width |
|------|-------------------|----------------|
| 6    | ~310 mi           | ~930 mi        |
| 7    | ~155 mi           | ~465 mi ✓      |
| 8    | ~78 mi            | ~234 mi        |
| 9    | ~39 mi            | ~117 mi        |

---

## Step 4 — Enable the panel in the console

1. Start the console and open **Menu → Settings**.
2. Go to **Primary Panels** or **Secondary Panels**.
3. Select a panel slot and choose **WeatherRadar** from the dropdown.
4. Save and restart the console.

The panel button labelled **Weather Radar** will appear in the bottom bar.

> **First launch note:** On the first load the panel downloads the base map
> tiles and all radar frames (up to ~120 HTTP requests for a 3×3 grid × 12
> frames). This takes 20–60 seconds on a Pi with a normal internet connection.
> Subsequent refreshes are faster because the base map is cached.

---

## Troubleshooting

**"Radar unavailable" is shown:**  
- Check internet connectivity on the Pi.  
- Run `python3 -c "import user.weatherradar.radar_fetcher as r; print(r.fetch_radar_frames(r.load_config()))"` from the `wfpiconsole/` directory to see error output.

**Panel shows a blank/black image:**  
- Verify that `Pillow` is installed: `python3 -c "from PIL import Image; print('OK')"`.
- Check that `user/weatherradar/frames/` contains PNG files after the first refresh.

**Base map tiles show as grey squares:**  
- OpenStreetMap rate-limits aggressive tile fetching. Wait a minute and restart.

**Animation is jerky:**  
- Increase `frame_delay` to `0.3` or `0.4` to reduce CPU usage during animation.
- Reduce `tile_grid` to `2` or `1` to decrease the number of tiles fetched.

---

## Attribution

- Radar data: [RainViewer](https://www.rainviewer.com/) (free for personal/educational use)
- Base map: © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors
