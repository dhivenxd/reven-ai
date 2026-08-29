# KKBOX data pipeline (inspection only)

This folder currently contains a **read-only inspector** for the raw KKBOX/media CSVs. It does not clean data, train models, or write processed files.

## Dataset location

From the repository root:

```
data/raw/kkbox/
  members_v3.csv
  transactions_v2.csv
  user_logs_v2.csv
  train_v2.csv
```

## What `inspect_kkbox.py` does

- Resolves paths from the **repository root** (not a hard-coded Windows path).
- Inspects the four CSVs by those filenames.
- Reports file size, row count, columns, dtypes, missing values, duplicate rows, a small sample, and date ranges.
- Reports duplicate counts for an obvious primary ID (`msno` when present).
- Reads `user_logs_v2.csv` **only in chunks** (never a full `pandas.read_csv()` into memory) and reports unique-user count and basic stats for listening/activity fields when present.
- Uses chunked reads for the other files as well so large CSVs stay memory-efficient.
- Handles missing files, malformed CSV, encoding issues, unexpected columns, and insufficient memory with visible error messages.
- Does **not** modify, rename, move, or overwrite raw files, and does **not** create processed datasets.

## How to run

From the **repository root**, with pandas available in your environment:

```bash
python backend/data_pipeline/inspect_kkbox.py
```

On Windows PowerShell (same command):

```powershell
python backend/data_pipeline/inspect_kkbox.py
```

Optional flags:

```bash
python backend/data_pipeline/inspect_kkbox.py --chunksize 200000 --user-logs-chunksize 100000
```

If memory is tight, lower `--user-logs-chunksize` (for example `50000`).
