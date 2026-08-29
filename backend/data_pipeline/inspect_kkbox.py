"""
Inspect the raw KKBOX/media CSVs under data/raw/kkbox/.

Read-only: does not modify, rename, move, or write processed datasets.
Large files (especially user_logs_v2.csv) are read in chunks.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print(
        "ERROR: pandas is required. Install it in your environment, then re-run.",
        file=sys.stderr,
    )
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "raw" / "kkbox"

# Actual filenames currently present in data/raw/kkbox/
MEMBERS_FILE = "members_v3.csv"
TRANSACTIONS_FILE = "transactions_v2.csv"
TRAIN_FILE = "train_v2.csv"
USER_LOGS_FILE = "user_logs_v2.csv"

EXPECTED_COLUMNS = {
    MEMBERS_FILE: [
        "msno",
        "city",
        "bd",
        "gender",
        "registered_via",
        "registration_init_time",
    ],
    TRANSACTIONS_FILE: [
        "msno",
        "payment_method_id",
        "payment_plan_days",
        "plan_list_price",
        "actual_amount_paid",
        "is_auto_renew",
        "transaction_date",
        "membership_expire_date",
        "is_cancel",
    ],
    TRAIN_FILE: ["msno", "is_churn"],
    USER_LOGS_FILE: [
        "msno",
        "date",
        "num_25",
        "num_50",
        "num_75",
        "num_985",
        "num_100",
        "num_unq",
        "total_secs",
    ],
}

PRIMARY_ID_CANDIDATES = ("msno", "user_id", "customer_id", "member_id")
DATE_NAME_HINTS = (
    "date",
    "time",
    "expire",
    "registration_init",
    "membership_expire",
    "transaction_date",
)
USER_LOG_NUMERIC_FIELDS = (
    "num_25",
    "num_50",
    "num_75",
    "num_985",
    "num_100",
    "num_unq",
    "total_secs",
)

ENCODINGS_TO_TRY = ("utf-8", "utf-8-sig", "latin-1")
SAMPLE_ROWS = 5
SEPARATOR = "=" * 78
THIN_SEPARATOR = "-" * 78
# Bound hash storage so duplicate-row / unique-id checks cannot balloon RAM.
# ~25M uint64 hashes is on the order of 200MB plus pandas overhead.
MAX_HASH_VALUES = 25_000_000
MAX_UNIQUE_USER_HASHES = 5_000_000


def format_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(n)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{n:,} bytes ({size:.2f} {unit})"
        size /= 1024
    return f"{n:,} bytes"


def print_heading(title: str) -> None:
    print()
    print(SEPARATOR)
    print(title)
    print(SEPARATOR)


def print_subheading(title: str) -> None:
    print()
    print(title)
    print(THIN_SEPARATOR)


def detect_id_column(columns: list[str]) -> str | None:
    lowered = {c.lower(): c for c in columns}
    for candidate in PRIMARY_ID_CANDIDATES:
        if candidate in lowered:
            return lowered[candidate]
    return None


def looks_like_date_column(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in DATE_NAME_HINTS)


def parse_kkbox_dates(series: pd.Series) -> pd.Series:
    """Parse KKBOX-style YYYYMMDD integers/strings, then generic datetime."""
    as_str = series.astype("string").str.replace(r"\.0$", "", regex=True)
    parsed = pd.to_datetime(as_str, format="%Y%m%d", errors="coerce")
    if parsed.notna().any():
        return parsed
    return pd.to_datetime(series, errors="coerce")


def choose_encoding(path: Path) -> str:
    last_error: Exception | None = None
    for encoding in ENCODINGS_TO_TRY:
        try:
            reader = pd.read_csv(path, chunksize=1, encoding=encoding)
            next(reader)
            return encoding
        except StopIteration:
            return encoding
        except UnicodeDecodeError as exc:
            last_error = exc
        except pd.errors.ParserError:
            # Encoding may be fine; parser issues are handled on the full read.
            return encoding
        except MemoryError:
            raise
    raise UnicodeDecodeError(
        "unknown",
        b"",
        0,
        1,
        f"Could not decode {path.name} with {ENCODINGS_TO_TRY}: {last_error}",
    )


def warn_unexpected_columns(filename: str, columns: list[str]) -> None:
    expected = EXPECTED_COLUMNS.get(filename)
    if expected is None:
        print("Expected columns: (no schema recorded for this file)")
        return
    actual = list(columns)
    missing = [c for c in expected if c not in actual]
    extra = [c for c in actual if c not in expected]
    print(f"Expected columns: {expected}")
    if missing:
        print(f"WARNING: missing expected columns: {missing}")
    if extra:
        print(f"WARNING: unexpected extra columns: {extra}")
    if not missing and not extra:
        print("Column names match the expected KKBOX schema.")


def print_missing(missing_counts: pd.Series, total_rows: int) -> None:
    if total_rows == 0:
        print("No rows; missing-value percentages cannot be computed.")
        return
    pct = (missing_counts / total_rows) * 100
    frame = pd.DataFrame(
        {
            "missing_count": missing_counts.astype("int64"),
            "missing_pct": pct.round(4),
        }
    )
    print(frame.to_string())


def print_sample(sample: pd.DataFrame) -> None:
    with pd.option_context("display.max_columns", None, "display.width", 120):
        print(sample.to_string(index=False))


def report_date_ranges(date_mins: dict, date_maxs: dict) -> None:
    if not date_mins:
        print("No date-like columns identified.")
        return
    for col in date_mins:
        lo, hi = date_mins[col], date_maxs[col]
        if pd.isna(lo) or pd.isna(hi):
            print(f"  {col}: could not parse a valid date range")
        else:
            print(f"  {col}: min={lo.date()}  max={hi.date()}")


def bounded_concat(parts: list[pd.Series], label: str) -> pd.Series | None:
    total = sum(len(p) for p in parts)
    if total > MAX_HASH_VALUES:
        print(
            f"{label}: skipped (would store {total:,} hash values; "
            f"limit is {MAX_HASH_VALUES:,} to stay memory-safe)."
        )
        return None
    if not parts:
        return pd.Series(dtype="uint64")
    return pd.concat(parts, ignore_index=True)


def inspect_chunked_csv(
    path: Path,
    *,
    chunksize: int,
    collect_row_hashes: bool,
    collect_id_hashes: bool,
    unique_user_hashes: bool,
    numeric_stat_columns: tuple[str, ...] = (),
) -> None:
    print_heading(f"FILE: {path.name}")
    print(f"Path (relative to repo root): {path.relative_to(REPO_ROOT).as_posix()}")
    print(f"File size: {format_bytes(path.stat().st_size)}")
    print(f"Read mode: chunked pandas.read_csv(chunksize={chunksize:,})")

    try:
        encoding = choose_encoding(path)
    except UnicodeDecodeError as exc:
        print(f"ERROR: encoding issue while reading {path.name}: {exc}")
        return

    print(f"Encoding used: {encoding}")

    columns: list[str] = []
    id_col: str | None = None
    date_cols: list[str] = []
    numeric_cols: list[str] = []
    missing_counts = pd.Series(dtype="int64")
    total_rows = 0
    sample = pd.DataFrame()
    dtypes_from_first_chunk: pd.Series | None = None
    date_mins: dict = {}
    date_maxs: dict = {}
    row_hash_parts: list[pd.Series] = []
    id_hash_parts: list[pd.Series] = []
    unique_user_set: set[int] = set()
    numeric_stats: dict[str, dict[str, float]] = {}
    row_hashes_capped = False
    id_hashes_capped = False
    user_hashes_capped = False

    try:
        reader = pd.read_csv(path, chunksize=chunksize, encoding=encoding)
        for i, chunk in enumerate(reader):
            if i == 0:
                dtypes_from_first_chunk = chunk.dtypes
                sample = chunk.head(SAMPLE_ROWS)
                columns = list(chunk.columns)
                missing_counts = pd.Series(0, index=columns, dtype="int64")
                print(f"Column names: {columns}")
                print("Data types (from first chunk):")
                print(chunk.dtypes.to_string())
                warn_unexpected_columns(path.name, columns)
                id_col = detect_id_column(columns) if collect_id_hashes else None
                date_cols = [c for c in columns if looks_like_date_column(c)]
                numeric_cols = [c for c in numeric_stat_columns if c in columns]
                numeric_stats = {
                    c: {
                        "count": 0.0,
                        "sum": 0.0,
                        "sumsq": 0.0,
                        "min": float("inf"),
                        "max": float("-inf"),
                    }
                    for c in numeric_cols
                }
            total_rows += len(chunk)
            missing_counts = missing_counts.add(chunk.isna().sum(), fill_value=0)

            if collect_row_hashes and not row_hashes_capped:
                row_hash_parts.append(
                    pd.util.hash_pandas_object(chunk, index=False)
                )
                if sum(len(p) for p in row_hash_parts) > MAX_HASH_VALUES:
                    row_hashes_capped = True
                    row_hash_parts.clear()

            if id_col and id_col in chunk.columns and not id_hashes_capped:
                id_hash_parts.append(
                    pd.util.hash_pandas_object(chunk[id_col], index=False)
                )
                if sum(len(p) for p in id_hash_parts) > MAX_HASH_VALUES:
                    id_hashes_capped = True
                    id_hash_parts.clear()

            if unique_user_hashes and "msno" in chunk.columns and not user_hashes_capped:
                unique_user_set.update(
                    pd.util.hash_pandas_object(chunk["msno"], index=False).tolist()
                )
                if len(unique_user_set) > MAX_UNIQUE_USER_HASHES:
                    user_hashes_capped = True
                    unique_user_set.clear()

            for col in date_cols:
                parsed = parse_kkbox_dates(chunk[col])
                valid = parsed.dropna()
                if valid.empty:
                    continue
                lo, hi = valid.min(), valid.max()
                date_mins[col] = lo if col not in date_mins else min(date_mins[col], lo)
                date_maxs[col] = hi if col not in date_maxs else max(date_maxs[col], hi)

            for col in numeric_cols:
                values = pd.to_numeric(chunk[col], errors="coerce").dropna()
                if values.empty:
                    continue
                stats = numeric_stats[col]
                stats["count"] += float(values.count())
                stats["sum"] += float(values.sum())
                stats["sumsq"] += float((values.astype("float64") ** 2).sum())
                stats["min"] = min(stats["min"], float(values.min()))
                stats["max"] = max(stats["max"], float(values.max()))

    except pd.errors.EmptyDataError:
        print("ERROR: file is empty or has no columns.")
        return
    except pd.errors.ParserError as exc:
        print(f"ERROR: malformed CSV while reading chunks: {exc}")
        return
    except UnicodeDecodeError as exc:
        print(f"ERROR: encoding issue while reading chunks: {exc}")
        return
    except MemoryError:
        print(
            "ERROR: insufficient memory while reading chunks. "
            "Re-run with a smaller --chunksize."
        )
        return
    except OSError as exc:
        print(f"ERROR: OS/IO error while reading {path.name}: {exc}")
        return

    if not columns:
        print("ERROR: file is empty or has no columns.")
        return

    print_subheading("Row count")
    print(f"Total rows: {total_rows:,}")

    if dtypes_from_first_chunk is not None:
        print_subheading("Data types (first full chunk)")
        print(dtypes_from_first_chunk.to_string())

    print_subheading("Missing values")
    print_missing(missing_counts.astype("int64"), total_rows)

    print_subheading("Duplicate rows")
    if row_hashes_capped:
        print(
            "Duplicate-row count skipped: too many rows to store hashes in memory."
        )
    else:
        try:
            row_hashes = bounded_concat(row_hash_parts, "Duplicate-row count")
            if row_hashes is not None:
                dup_rows = int(row_hashes.duplicated().sum())
                print(f"Duplicate-row count: {dup_rows:,}")
        except MemoryError:
            print("ERROR: insufficient memory while computing duplicate-row count.")

    if id_col:
        print_subheading(f"Primary ID column: {id_col}")
        if id_hashes_capped:
            print("Duplicate primary-ID count skipped: too many IDs to hash in memory.")
        else:
            try:
                id_hashes = bounded_concat(id_hash_parts, "Duplicate primary-ID count")
                if id_hashes is not None:
                    unique_ids = int(id_hashes.nunique(dropna=False))
                    extra = total_rows - unique_ids
                    print(f"Unique {id_col} values: {unique_ids:,}")
                    print(
                        f"Duplicate primary-ID extra rows "
                        f"(row_count - unique_ids): {extra:,}"
                    )
            except MemoryError:
                print("ERROR: insufficient memory while computing ID uniqueness.")
    elif collect_id_hashes:
        print_subheading("Primary ID")
        print("No obvious primary ID column (msno / user_id / customer_id / member_id).")

    print_subheading(f"Sample rows (first {SAMPLE_ROWS})")
    print_sample(sample)

    print_subheading("Date columns (min / max)")
    if date_cols:
        print(f"Identified date-like columns: {date_cols}")
    report_date_ranges(date_mins, date_maxs)

    if unique_user_hashes:
        print_subheading("Unique users")
        if "msno" not in columns:
            print("Column 'msno' not found; unique user count skipped.")
        elif user_hashes_capped:
            print(
                "Unique user count skipped: more distinct users than the "
                f"in-memory cap ({MAX_UNIQUE_USER_HASHES:,})."
            )
        else:
            print(f"Unique msno count: {len(unique_user_set):,}")

    if numeric_cols:
        print_subheading("Numeric activity / listening fields")
        rows = []
        for col in numeric_cols:
            stats = numeric_stats[col]
            count = stats["count"]
            if count == 0:
                rows.append(
                    {
                        "column": col,
                        "count": 0,
                        "mean": None,
                        "std": None,
                        "min": None,
                        "max": None,
                    }
                )
                continue
            mean = stats["sum"] / count
            variance = max(stats["sumsq"] / count - mean**2, 0.0)
            rows.append(
                {
                    "column": col,
                    "count": int(count),
                    "mean": round(mean, 4),
                    "std": round(variance**0.5, 4),
                    "min": stats["min"],
                    "max": stats["max"],
                }
            )
        print(pd.DataFrame(rows).to_string(index=False))


def inspect_standard_file(path: Path, chunksize: int) -> None:
    inspect_chunked_csv(
        path,
        chunksize=chunksize,
        collect_row_hashes=True,
        collect_id_hashes=True,
        unique_user_hashes=False,
    )


def inspect_user_logs(path: Path, chunksize: int) -> None:
    print()
    print(
        "NOTE: user_logs_v2.csv is never loaded in full. "
        "pandas.read_csv() is called only with chunksize."
    )
    inspect_chunked_csv(
        path,
        chunksize=chunksize,
        collect_row_hashes=True,
        collect_id_hashes=False,
        unique_user_hashes=True,
        numeric_stat_columns=USER_LOG_NUMERIC_FIELDS,
    )


def resolve_csv_path(data_dir: Path, filename: str) -> Path:
    path = data_dir / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Missing file: {path.relative_to(REPO_ROOT).as_posix()} "
            f"(looked under {data_dir.relative_to(REPO_ROOT).as_posix()}/)"
        )
    if path.is_dir():
        nested = path / filename
        raise FileNotFoundError(
            f"{path.relative_to(REPO_ROOT).as_posix()} is a directory, not a CSV. "
            f"Expected a file named {filename}. Nested candidate "
            f"{nested.relative_to(REPO_ROOT).as_posix()} was not used."
        )
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only inspection of raw KKBOX CSVs (no writes, no downloads)."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing the KKBOX CSVs (default: <repo>/data/raw/kkbox)",
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=200_000,
        help="Rows per chunk for pandas.read_csv (default: 200000)",
    )
    parser.add_argument(
        "--user-logs-chunksize",
        type=int,
        default=100_000,
        help="Rows per chunk for user_logs_v2.csv (default: 100000)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_dir = args.data_dir
    if not data_dir.is_absolute():
        data_dir = (REPO_ROOT / data_dir).resolve()

    print_heading("REVEN — KKBOX raw dataset inspector")
    print(f"Repository root: {REPO_ROOT}")
    print(f"Data directory: {data_dir}")
    print("This script is read-only. Raw files are not modified.")

    if args.chunksize < 1 or args.user_logs_chunksize < 1:
        print("ERROR: chunksize must be >= 1")
        return 1

    if not data_dir.exists():
        print(f"ERROR: data directory does not exist: {data_dir}")
        return 1

    filenames = [MEMBERS_FILE, TRANSACTIONS_FILE, TRAIN_FILE, USER_LOGS_FILE]
    errors: list[str] = []

    for filename in filenames:
        try:
            path = resolve_csv_path(data_dir, filename)
        except FileNotFoundError as exc:
            print_heading(f"FILE: {filename}")
            print(f"ERROR: {exc}")
            errors.append(str(exc))
            continue

        try:
            if filename == USER_LOGS_FILE:
                inspect_user_logs(path, chunksize=args.user_logs_chunksize)
            else:
                inspect_standard_file(path, chunksize=args.chunksize)
        except FileNotFoundError as exc:
            print(f"ERROR: missing file: {exc}")
            errors.append(str(exc))
        except UnicodeDecodeError as exc:
            print(f"ERROR: encoding issue: {exc}")
            errors.append(str(exc))
        except pd.errors.ParserError as exc:
            print(f"ERROR: malformed CSV: {exc}")
            errors.append(str(exc))
        except MemoryError:
            msg = f"ERROR: insufficient memory while inspecting {filename}"
            print(msg)
            errors.append(msg)
        except Exception as exc:
            print(f"ERROR: unexpected failure while inspecting {filename}: {exc}")
            traceback.print_exc()
            errors.append(str(exc))

    print_heading("Inspection complete")
    if errors:
        print(f"Finished with {len(errors)} error(s). See messages above.")
        return 1
    print("Finished successfully. No raw files were changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
