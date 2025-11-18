import json
import osmnx as ox
import pandas as pd
import pydeck as pdk
import typing as T

from dataclasses import dataclass

from pyproj import Transformer


# Define coordinate data class.
# This is a simple dataclass to help manage coordinates in a consistent way

@dataclass(frozen=True)
class Coordinate:
    lat: float
    lon: float
    alt: float
    name: str = ""

#  Building & Rendering Utilities

def get_buildings(bbox):
  b = ox.features.features_from_bbox(bbox, {"building": True})
  # filter buildings without height specified
  b = b[b["height"].notnull()]
  b = b[b["height"] != ""]
  if b.empty:
      return None
  def _height(row):
      h = row.get("height")
      if isinstance(h, str):
          tok = h.split(" ")[0]
          try:
              h = float(tok)
          except Exception:
              h = 0.0
      return float(h)

  b["render_height"] = b.apply(_height, axis=1)
  return b

def get_path_layers(
    points: T.List[Coordinate],
    *,
    line_color=(0, 120, 255, 240),
    line_width_px=4,
    mid_color=(255, 60, 60, 240),
    mid_radius_px=5,
    start_color=(0, 200, 0, 240),
    start_radius_px=16,
    end_color=(200, 0, 200, 240),
    end_radius_px=18,
):
    """
    Returns (line_layer, points_layer) for a polyline through 'points' in order.
    """
    if not points or len(points) < 2:
        raise ValueError("Provide at least two points.")

    # Normalize to DataFrame with default altitude 0
    rows = []
    for i, p in enumerate(points):
        rows.append({
            "idx": i,
            "name": p.name or f"Pt {i+1}",
            "lon": float(p.lon),
            "lat": float(p.lat),
            "alt": float(p.alt),
        })

    df = pd.DataFrame(rows)

    # Style endpoints vs middles
    df["is_start"] = df["idx"] == 0
    df["is_end"]   = df["idx"] == len(df) - 1
    df["color"]    = df.apply(
        lambda r: list(start_color) if r["is_start"]
        else (list(end_color) if r["is_end"] else list(mid_color)),
        axis=1
    )
    df["radius"]   = df.apply(
        lambda r: float(start_radius_px) if r["is_start"]
        else (float(end_radius_px) if r["is_end"] else float(mid_radius_px)),
        axis=1
    )

    points_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["lon", "lat", "alt"],
        get_radius="radius",
        get_fill_color="color",
        pickable=True,
    )

    # Build segments between consecutive points for LineLayer
    segs = []
    for i in range(len(df)-1):
        a = df.iloc[i]; b = df.iloc[i+1]
        segs.append({
            "name": f"{a['name']} → {b['name']}",
            "source": [a["lon"], a["lat"], a["alt"]],
            "target": [b["lon"], b["lat"], b["alt"]],
        })
    seg_df = pd.DataFrame(segs)

    line_layer = pdk.Layer(
        "LineLayer",
        data=seg_df,
        get_source_position="source",
        get_target_position="target",
        get_width=line_width_px,
        get_color=list(line_color),
        pickable=True,
    )

    return line_layer, points_layer

def get_buildings_layer(buildings):
    # Buildings (extruded, with height fallback from building:levels)
    if buildings is not None and not buildings.empty:
        b = buildings.copy()

        # Drop unnecessary columns
        keep_cols = ["geometry", "name", "render_height"]
        for col in keep_cols:
            if col not in b.columns:
                b[col] = None
        b = b[keep_cols]

        b_geo = json.loads(b.to_json())

        return pdk.Layer(
            "GeoJsonLayer",
            b_geo,
            stroked=False,
            filled=True,
            extruded=True,
            wireframe=False,
            opacity=0.8,
            get_elevation="properties.render_height",
            get_fill_color=[200, 200, 200, 210],
            pickable=True,
        )
    return None

def get_deck(bbox, layers):
    w, s, e, n = bbox
    center_lat = (n + s) / 2.0
    center_lon = (e + w) / 2.0
    deck = pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=15,
            pitch=55,
            bearing=18,
        ),
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        tooltip={"text": "{name}"},
    )
    return deck

# Fetch buildings & Render

def create_deck(*, bbox, buildings, path_list: T.List[T.List[Coordinate]]):
    layers = []

    buildings_layer = get_buildings_layer(buildings)
    if buildings_layer:
      layers.append(buildings_layer)

    for path in path_list:
      line_layer, points_layer = get_path_layers(path)
      layers.extend([line_layer, points_layer])

    deck = get_deck(bbox, layers)

    return deck


def get_coordinate_transforms(bbox):
    w, s, e, n = bbox
    lat0 = (n + s) / 2
    lon0 = (e + w) / 2

    # pyproj transform to convert lat lon to xy
    # using azimuthal equidistant projection centered around the bbox center
    proj_str = f"+proj=aeqd +lat_0={lat0} +lon_0={lon0} +ellps=WGS84 +units=m"

    transfrom_latlon_to_xy = Transformer.from_crs("EPSG:4326", proj_str, always_xy=True)
    transform_xy_to_latlon = Transformer.from_crs(proj_str, "EPSG:4326", always_xy=True)
    return transfrom_latlon_to_xy, transform_xy_to_latlon

def filter_buildings(buildings, cutoff_height):
    # filter buildings by height and return their geometry
    b = buildings.copy()
    b["height_clean"] = b["height"].str.replace("m", "", regex=False).str.strip()
    b["height_clean"] = pd.to_numeric(b["height_clean"])
    return b[b["height_clean"] > cutoff_height].copy()

def path_to_coordinates(path_xy, transformer, alt, label="RRT Path"):
    """Convert XY polyline into Coordinate list for pydeck rendering."""
    coords = []
    for idx, (x, y) in enumerate(path_xy):
        lon, lat = transformer.transform(x, y)
        name = f"{label} Pt {idx+1}"
        coords.append(Coordinate(lat=lat, lon=lon, alt=alt, name=name))
    return coords