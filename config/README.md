# Adding plots, instruments and sites

Everything the QuickLook browser shows comes from the files in this directory.
There is no database and no code to change: add a file or a few lines, and the
next page load picks it up. No restart, no deploy.

Check your work before committing:

```bash
python3 scripts/validate_config.py config/
```

It prints every problem with the file and line it came from, and says nothing
when the tree is clean. Please run it — the service is deliberately forgiving
and will *skip* a file it cannot read rather than complain, so a typo shows up
as a quietly missing plot rather than an error message.

---

## Adding a plot

Plots live in `plots/`. **One file holds many plots** — all the ones that share
a directory and an instrument. Open the file that fits and add a line:

```yaml
sites: jue
instruments: halo
base: https://atmos.meteo.uni-koeln.de/~hatpro/quicklooks/obs/site/jue/dwl/%Y/%m/%d/

plots:
  jue-dwl-beta: beta_cont_%Y%m%d.png      # <- one line is a whole plot
  jue-dwl-speed: wind_spd_cont_%Y%m%d.png
```

`base` is glued to the front of each path, so you only write the part that
differs. `%Y`, `%m`, `%d` are filled in from the date the user picked
(`%Y`=2026, `%m`=06, `%d`=15). Anything
[strftime](https://strftime.org/) understands works.

The key (`jue-dwl-beta`) is the plot's **id**. It ends up in the URL people
bookmark, so pick it carefully and don't rename it later. **The filename does
not matter** — call the file whatever helps you find it.

### When one line isn't enough

```yaml
plots:
  jue-dwl-TKE:
    description: Turbulent kinetic energy, and the part from vertical wind.
    daily: TKE_cont_%Y%m%d.png

    # Monthly/seasonal/yearly versions, if they exist. A path starting with "/"
    # or "http" is used as-is and ignores `base`.
    monthly: /data/obs/site/jue/dwl/%Y/%m/%Y%m_TKE.png
    yearly: /data/obs/site/jue/dwl/%Y/%Y_TKE.png

    # Seasons are named by their first month: 202606 is June-July-August.
    seasonal: /data/obs/site/jue/dwl/%Y/%m/seasonal_TKE.png
```

Both local paths (`/data/obs/...`) and URLs work, and one plot can mix them.

### A plot from more than one instrument

Derived products often combine instruments. List them all — the plot then shows
up under each one:

```yaml
  wind_ppi_radar_lidar:
    instruments: [joyrad_35, halo]
    daily: '%Y%m%d_radarlidar_combined.png'
```

`sites` and `instruments` written at the top of the file are just defaults;
writing either inside a plot overrides it for that plot only.

### Many images per day

For something like radiosondes, where each day has several ascents, point
`daily` at the **directory** (trailing slash) and describe the filenames:

```yaml
  rs_jue_skewt:
    description: Radiosonde Skew-T
    multi: true
    daily: /data/obs/campaigns/vital2/site/juelich/sounding/plots/
    pattern: 'vitII_joy_rs41_comp_v00_%Y%m%d*_skewt.png'
```

The browser then shows arrows to step through the day's images. This only works
for local paths, not URLs.

---

## Adding an instrument

One file per instrument in `instruments/`. **The filename is the id** —
`halo.yaml` is the instrument `halo` — so there is no name to keep in sync.

```yaml
description: HALO Doppler Wind Lidar
wiki: https://obs.meteo.uni-koeln.de/doku.php?id=windlidar
locations:
  - site: jue
    dates:
      - [2011-11-07, 2012-07-26]    # a past deployment
      - [2012-09-12, 2025-01-22]
      - [2026-06-01]                # no end date = still there now
```

Order matters: put the spans **oldest first**. An entry with only a start date
means the instrument is currently on site, and that is what decides whether it
appears under the site today — so it has to be the last one.

---

## Adding a site

One file per site in `sites/`, again named by its id.

```yaml
name: JOYCE Jülich
description: The Jülich ObservatorY for Cloud Evolution ...
lat: 50.908547
lon: 6.413536
altitude: 111

# Optional: a live-data feed for the dashboard.
live_data: https://atmos.meteo.uni-koeln.de/~citystation/jueWebDashboard/data.json
```

---

## Things that bite

- **Quote anything starting with `%` or `*`**, and any value containing `: `.
  When in doubt, wrap it in single quotes — that is always safe.
- **Tabs are not allowed** anywhere in YAML. Use spaces.
- **Indentation is meaningful.** Two spaces per level, and be consistent.
- **Dates as `2026-06-01`**, always four-digit year and zero-padded.
- **Plot ids must be unique across every file**, not just within one.
- Files must end in `.yaml` — `.yml` and `.json` are ignored.
