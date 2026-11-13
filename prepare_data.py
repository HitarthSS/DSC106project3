# Download the original CMIP6 grid and export the small file used by D3.
# pip install numpy xarray 'dask[array]' 'zarr>=3' gcsfs cftime requests 'shapely>=2.1'
import json
from pathlib import Path
import numpy as np
import requests
import xarray as xr
from shapely import box, orient_polygons
from shapely.geometry import shape, mapping

folder = Path(__file__).resolve().parent / "data"
folder.mkdir(exist_ok=True)
boundary_url = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/0/query"
boundary = requests.get(boundary_url, params={
    "where": "STATE='06'", "outFields": "NAME", "f": "geojson",
    "returnGeometry": "true", "outSR": "4326"
}, timeout=60).json()["features"][0]["geometry"]
boundary = shape(boundary).simplify(.01, preserve_topology=True)

stores = {
    "historical": "gs://cmip6/CMIP6/CMIP/NOAA-GFDL/GFDL-ESM4/historical/r1i1p1f1/Amon/tas/gr1/v20190726/",
    "ssp126": "gs://cmip6/CMIP6/ScenarioMIP/NOAA-GFDL/GFDL-ESM4/ssp126/r1i1p1f1/Amon/tas/gr1/v20180701/",
    "ssp585": "gs://cmip6/CMIP6/ScenarioMIP/NOAA-GFDL/GFDL-ESM4/ssp585/r1i1p1f1/Amon/tas/gr1/v20180701/"
}
annual = {}
for experiment, store in stores.items():
    print(f"Downloading {experiment}...")
    with xr.open_zarr(store, consolidated=True, storage_options={"token": "anon"}) as ds:
        temperature = ds.tas.sel(time=slice("1850", "2100"), lat=slice(31, 44), lon=slice(234, 247))
        days = temperature.time.dt.days_in_month
        annual[experiment] = (
            (temperature * days).groupby("time.year").sum("time")
            / days.groupby("time.year").sum("time") - 273.15
        ).transpose("year", "lat", "lon").compute()

sample = annual["historical"]
latitudes, longitudes = sample.lat.values, sample.lon.values - 360

def edges(centers):
    midpoints = (centers[:-1] + centers[1:]) / 2
    return np.r_[2 * centers[0] - midpoints[0], midpoints, 2 * centers[-1] - midpoints[-1]]

latitude_edges, longitude_edges = edges(latitudes), edges(longitudes)
cells, indices = [], []
for row, latitude in enumerate(latitudes):
    for column, longitude in enumerate(longitudes):
        geometry = box(longitude_edges[column], latitude_edges[row],
                       longitude_edges[column + 1], latitude_edges[row + 1]).intersection(boundary)
        if not geometry.is_empty and geometry.area > 0:
            cells.append({"type": "Feature", "geometry": mapping(orient_polygons(geometry, exterior_cw=True)),
                          "properties": {"latitude": float(latitude), "longitude": float(longitude)}})
            indices.append((row, column))

rows, columns = np.array(indices).T
values = {experiment: data.values[:, rows, columns].round(2).tolist()
          for experiment, data in annual.items()}
all_values = np.concatenate([data.values[:, rows, columns].ravel() for data in annual.values()])
result = {
    "model": "GFDL-ESM4", "member": "r1i1p1f1", "grid": "gr1", "units": "°C",
    "aggregation": "Annual average, weighted by days in each month",
    "stores": stores, "boundarySource": boundary_url,
    "historicalStart": int(annual["historical"].year.values[0]),
    "projectionStart": int(annual["ssp126"].year.values[0]),
    "endYear": int(annual["ssp126"].year.values[-1]),
    "colorRange": [float(np.floor(all_values.min() / 5) * 5), float(np.ceil(all_values.max() / 5) * 5)],
    "boundary": {"type": "Feature", "geometry": mapping(orient_polygons(boundary, exterior_cw=True))},
    "cells": cells, "temperatures": values
}
destination = folder / "california_grid.json"
destination.write_text(json.dumps(result, separators=(",", ":"), allow_nan=False))
print(f"Saved {len(cells)} geographic cells to {destination}")
