# macro_equity data layout

| Path | Git | Contents |
|---|---|---|
| `dev/raw/` | ignored | Downloaded development-period data (dates before the holdout boundary) |
| `dev/processed/` | ignored | Tables derived from licensed or raw data |
| `holdout/` | ignored, quarantined | Holdout-period data. Only the gated `macro_equity.run_oos` reads it |
| `imports/` | ignored | Staging area for user-supplied licensed files, such as a consensus EPS export. The importer splits them into `dev/` and `holdout/` without computing anything on holdout rows |
| `cache/` | ignored | HTTP and tool caches |
| `manifests/` | tracked | `source_manifest.json`, coverage metadata (first/last dates, row counts), checksums, retrieval times. No data values |
| `templates/` | tracked | Import templates (column headers and definitions only) |

The directories are created by the code that writes to them, not committed empty. The holdout boundary comes from coverage metadata in Prompt 2, never from results.
