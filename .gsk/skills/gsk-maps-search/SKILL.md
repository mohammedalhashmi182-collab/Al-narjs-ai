---
name: gsk-maps-search
version: 1.0.0
description: Search maps for places, local businesses, distances between locations,
  and directions. Use ONLY for geographical/location queries — NOT general facts,
  news, or weather.
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk maps-search --help
---

# gsk-maps-search

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

Search maps for places, local businesses, distances between locations, and directions. Use ONLY for geographical/location queries — NOT general facts, news, or weather.

## Usage

```bash
gsk maps-search [options]
```

**Aliases:** `maps-search`

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `--query_type` | Yes | The type of query to perform. (string, one of: search, place, distances, directions) |
| `--engine` | Yes | The engine to use for the query. (string, one of: maps, maps_directions) |
| `<query>` (positional) | No | The query to search for places, if engine is maps, this is required. (string) |
| `--start_addr` | No | The starting address to calculate distances or get directions.If engine is maps_directions, this is required. (string) |
| `--end_addr` | No | The ending address to calculate distances or get directions.If engine is maps_directions, this is required. (string) |
| `--travel_mode` | No | The mode of transportation to use for directions. (string, one of: 0, 1, 2, 3, 4, 6, 9) |
| `--avoid` | No | The avoid mode to use for directions. (string, one of: highways, tolls, ferries) |
| `--prefer` | No | The prefer mode to use for directions. (string, one of: bus, subway, train, tram_light_rail) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
