# Bundled offline basemap

`states-southeast.geojson` is the planner's fallback basemap when the online style cannot load.

- Source: U.S. Census Bureau, 2023 Cartographic Boundary File, States, 1:20,000,000
  (`https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_state_20m.zip`,
  SHA-256 `0fd2d6562708ff8182c00d5d25b5556d049ecf2794d97b89ed2dac4d5e9e2c8d`). Public domain.
- Kept: AL, FL, GA, NC, SC, TN. Simplified with a 0.01° tolerance (topology preserved);
  coordinates rounded to 4 decimals. Display only — never used for any analysis.
