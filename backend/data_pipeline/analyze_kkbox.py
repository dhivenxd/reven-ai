"""
Read-only statistical calibration analysis of raw KKBOX CSVs.

Does not train a model, write processed datasets, download data, or modify
anything under data/raw/. Large files are read only via pandas chunksize.
user_logs_v2.csv is never loaded into memory as a single DataFrame.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from collections import Counter
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
except ImportError:
    print(
        "ERROR: pandas and numpy are required. Install them in your environment, then re-run.",
        file=sys.stderr,
    )
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "raw" / "kkbox"

MEMBERS_FILE = "members_v3.csv"
TRANSACTIONS_FILE = "transactions_v2.csv"
USER_LOGS_FILE = "user_logs_v2.csv"
TRAIN_FILE = "train_v2.csv"

MEMBERS_COLS = [
    "msno",
    "city",
    "bd",
    "gender",
    "registered_via",
    "registration_init_time",
]
TRANSACTIONS_COLS = [
    "msno",
    "payment_method_id",
    "payment_plan_days",
    "plan_list_price",
    "actual_amount_paid",
    "is_auto_renew",
    "transaction_date",
    "membership_expire_date",
    "is_cancel",
]
USER_LOGS_COLS = ["msno", "date", "num_unq", "total_secs"]
TRAIN_COLS = ["msno", "is_churn"]

ENCODINGS_TO_TRY = ("utf-8", "utf-8-sig", "latin-1")
SEPARATOR = "=" * 50
THIN = "-" * 50

# Compact numeric sample for user-day percentiles (not raw log rows).
PERCENTILE_RESERVOIR = 400_000
# Plausible human age for inspection only; not a REVEN feature.
BD_PLAUSIBLE_MIN = 10
BD_PLAUSIBLE_MAX = 90


def print_heading(title: str) -> None:
    print()
    print(SEPARATOR)
    print(title)
    print(SEPARATOR)


def print_subheading(title: str) -> None:
    print()
    print(title)
    print(THIN)


def pct(numerator: float, denominator: float) -> str:
    if denominator <= 0:
        return "n/a"
    return f"{(100.0 * numerator / denominator):.4f}%"


def fmt_num(value: float | int | None, digits: int = 4) -> str:
    if value is None or (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
        return "n/a"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    return f"{value:,.{digits}f}"


def fmt_date(value) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    ts = pd.Timestamp(value)
    return str(ts.date())


def parse_kkbox_dates(series: pd.Series) -> pd.Series:
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


def resolve_csv_path(data_dir: Path, filename: str) -> Path:
    path = data_dir / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Missing file: {path.relative_to(REPO_ROOT).as_posix()} "
            f"(looked under {data_dir.relative_to(REPO_ROOT).as_posix()}/)"
        )
    if path.is_dir():
        raise FileNotFoundError(
            f"{path.relative_to(REPO_ROOT).as_posix()} is a directory, not a CSV."
        )
    return path


def chunk_reader(
    path: Path,
    *,
    chunksize: int,
    encoding: str,
    usecols: list[str] | None = None,
):
    return pd.read_csv(
        path,
        chunksize=chunksize,
        encoding=encoding,
        usecols=usecols,
        low_memory=False,
    )


def print_counter(counter: Counter, *, total: int, top: int | None = None, label: str = "value") -> None:
    if total <= 0 or not counter:
        print("No values to report.")
        return
    items = counter.most_common(top) if top is not None else counter.most_common()
    rows = []
    for key, count in items:
        rows.append(
            {
                label: key,
                "count": int(count),
                "pct": round(100.0 * count / total, 4),
            }
        )
    print(pd.DataFrame(rows).to_string(index=False))


def describe_numeric(values: np.ndarray) -> dict[str, float]:
    values = np.asarray(values, dtype=np.float64)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {
            "count": 0.0,
            "mean": float("nan"),
            "median": float("nan"),
            "p25": float("nan"),
            "p75": float("nan"),
            "min": float("nan"),
            "max": float("nan"),
        }
    return {
        "count": float(values.size),
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p25": float(np.percentile(values, 25)),
        "p75": float(np.percentile(values, 75)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


def print_numeric_stats(name: str, stats: dict[str, float]) -> None:
    print(f"{name}:")
    print(f"  count  = {fmt_num(int(stats['count']))}")
    print(f"  mean   = {fmt_num(stats['mean'])}")
    print(f"  median = {fmt_num(stats['median'])}")
    print(f"  p25    = {fmt_num(stats['p25'])}")
    print(f"  p75    = {fmt_num(stats['p75'])}")
    print(f"  min    = {fmt_num(stats['min'])}")
    print(f"  max    = {fmt_num(stats['max'])}")


def add_value_counts(counter: Counter, series: pd.Series) -> None:
    counts = series.value_counts(dropna=False)
    for key, count in counts.items():
        if pd.isna(key):
            counter["<NA>"] += int(count)
        else:
            counter[key] += int(count)


class ReservoirSampler:
    """Vectorized reservoir sample of float64 values. Does not keep raw CSV rows."""

    def __init__(self, capacity: int, seed: int = 42) -> None:
        self.capacity = int(capacity)
        self.rng = np.random.default_rng(seed)
        self.buf = np.empty(self.capacity, dtype=np.float64)
        self.filled = 0
        self.seen = 0

    def update(self, values: np.ndarray) -> None:
        if values.size == 0:
            return
        vals = np.asarray(values, dtype=np.float64)
        vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            return
        if self.filled < self.capacity:
            space = self.capacity - self.filled
            take = min(space, vals.size)
            self.buf[self.filled : self.filled + take] = vals[:take]
            self.filled += take
            self.seen += take
            vals = vals[take:]
        if vals.size == 0:
            return
        idx = np.arange(self.seen + 1, self.seen + vals.size + 1, dtype=np.float64)
        include = self.rng.random(vals.size) < (self.capacity / idx)
        chosen = vals[include]
        if chosen.size:
            slots = self.rng.integers(0, self.capacity, size=chosen.size)
            self.buf[slots] = chosen
        self.seen += vals.size

    def values(self) -> np.ndarray:
        return self.buf[: self.filled]


def merge_customer_frame(acc: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    """Sum-merge customer aggregates (counts and totals)."""
    if new.empty:
        return acc if acc is not None else new
    if acc is None or acc.empty:
        return new
    return acc.add(new, fill_value=0)


def merge_engagement_frame(acc: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    """Merge per-user log summaries: sums for totals, min/max for dates."""
    if new.empty:
        return acc if acc is not None else new
    if acc is None or acc.empty:
        return new.copy()
    idx = acc.index.union(new.index)
    a = acc.reindex(idx)
    b = new.reindex(idx)
    out = pd.DataFrame(index=idx)
    out["active_days"] = a["active_days"].add(b["active_days"], fill_value=0)
    out["total_secs"] = a["total_secs"].add(b["total_secs"], fill_value=0)
    out["total_num_unq"] = a["total_num_unq"].add(b["total_num_unq"], fill_value=0)
    out["last_active_date"] = np.fmax(
        a["last_active_date"].to_numpy(dtype=np.float64),
        b["last_active_date"].to_numpy(dtype=np.float64),
    )
    out["first_active_date"] = np.fmin(
        a["first_active_date"].to_numpy(dtype=np.float64),
        b["first_active_date"].to_numpy(dtype=np.float64),
    )
    return out


def update_date_bounds(current_min, current_max, series: pd.Series):
    parsed = parse_kkbox_dates(series).dropna()
    if parsed.empty:
        return current_min, current_max
    lo, hi = parsed.min(), parsed.max()
    current_min = lo if current_min is None else min(current_min, lo)
    current_max = hi if current_max is None else max(current_max, hi)
    return current_min, current_max


def analyze_members(path: Path, chunksize: int, labeled_ids: set[str]) -> dict:
    print_heading("1. CUSTOMER / MEMBERSHIP")
    print(f"Source: {path.relative_to(REPO_ROOT).as_posix()}")
    print("Note: gender, city, and bd are inspected only. They are not core REVEN features.")
    encoding = choose_encoding(path)
    print(f"Encoding: {encoding}")
    print(f"Read mode: chunked pandas.read_csv(chunksize={chunksize:,})")

    total = 0
    unique_msno: set[int] = set()
    unique_capped = False
    reg_min = reg_max = None
    via_counts: Counter = Counter()
    city_counts: Counter = Counter()
    gender_missing = 0
    gender_present = 0
    bd_raw_parts: list[np.ndarray] = []
    bd_plausible_parts: list[np.ndarray] = []
    bd_zero = 0
    bd_negative = 0
    bd_over_100 = 0
    bd_over_120 = 0
    bd_missing = 0
    bd_implausible = 0
    labeled_reg: dict[str, int] = {}

    for chunk in chunk_reader(path, chunksize=chunksize, encoding=encoding, usecols=MEMBERS_COLS):
        total += len(chunk)
        if "msno" in chunk.columns and not unique_capped:
            unique_msno.update(
                pd.util.hash_pandas_object(chunk["msno"], index=False).to_numpy()
            )
            if len(unique_msno) > 8_000_000:
                unique_capped = True
                unique_msno.clear()

        if "registration_init_time" in chunk.columns:
            reg_min, reg_max = update_date_bounds(
                reg_min, reg_max, chunk["registration_init_time"]
            )

        if "registered_via" in chunk.columns:
            add_value_counts(via_counts, chunk["registered_via"])
        if "city" in chunk.columns:
            add_value_counts(city_counts, chunk["city"])

        if "gender" in chunk.columns:
            g = chunk["gender"]
            missing_mask = g.isna() | (g.astype("string").str.strip() == "")
            gender_missing += int(missing_mask.sum())
            gender_present += int((~missing_mask).sum())

        if "bd" in chunk.columns:
            bd = pd.to_numeric(chunk["bd"], errors="coerce")
            bd_missing += int(bd.isna().sum())
            valid = bd.dropna()
            if not valid.empty:
                arr = valid.to_numpy(dtype=np.float64)
                bd_raw_parts.append(arr)
                bd_zero += int((arr == 0).sum())
                bd_negative += int((arr < 0).sum())
                bd_over_100 += int((arr > 100).sum())
                bd_over_120 += int((arr > 120).sum())
                plausible = (arr >= BD_PLAUSIBLE_MIN) & (arr <= BD_PLAUSIBLE_MAX)
                bd_implausible += int((~plausible).sum())
                if plausible.any():
                    bd_plausible_parts.append(arr[plausible])

        if labeled_ids and "msno" in chunk.columns and "registration_init_time" in chunk.columns:
            mask = chunk["msno"].isin(labeled_ids)
            if mask.any():
                sub = chunk.loc[mask, ["msno", "registration_init_time"]]
                for msno, raw in zip(sub["msno"].to_numpy(), sub["registration_init_time"].to_numpy()):
                    if msno not in labeled_reg:
                        labeled_reg[msno] = raw

    print()
    print(f"Total member rows: {total:,}")
    if unique_capped:
        print("Unique members: skipped (unique-id cap reached; using row count as proxy).")
        unique_count = total
    else:
        unique_count = len(unique_msno)
        print(f"Unique members (hashed msno): {unique_count:,}")
        if unique_count != total:
            print(
                f"NOTE: row count and unique msno differ by {abs(total - unique_count):,}."
            )
    print(f"Registration date min: {fmt_date(reg_min)}")
    print(f"Registration date max: {fmt_date(reg_max)}")

    print_subheading("registered_via distribution")
    print_counter(via_counts, total=total, label="registered_via")

    print_subheading("city distribution (top 10)")
    print_counter(city_counts, total=total, top=10, label="city")
    print("Inspection only — do not use city as a core REVEN feature.")

    print_subheading("gender availability (inspection only)")
    print(f"Present: {gender_present:,} ({pct(gender_present, total)})")
    print(f"Missing / blank: {gender_missing:,} ({pct(gender_missing, total)})")
    print("Do not use gender as a core REVEN feature.")

    print_subheading("age / bd (inspection only; invalid values flagged)")
    raw = np.concatenate(bd_raw_parts) if bd_raw_parts else np.array([], dtype=np.float64)
    print_numeric_stats("bd raw (including invalid)", describe_numeric(raw))
    print(f"bd missing: {bd_missing:,} ({pct(bd_missing, total)})")
    print(f"bd == 0: {bd_zero:,} ({pct(bd_zero, total)})  [treated as invalid / placeholder]")
    print(f"bd < 0: {bd_negative:,} ({pct(bd_negative, total)})  [invalid]")
    print(f"bd > 100: {bd_over_100:,} ({pct(bd_over_100, total)})  [likely invalid]")
    print(f"bd > 120: {bd_over_120:,} ({pct(bd_over_120, total)})  [invalid]")
    print(
        f"bd outside plausible range [{BD_PLAUSIBLE_MIN}, {BD_PLAUSIBLE_MAX}]: "
        f"{bd_implausible:,} ({pct(bd_implausible, total)})"
    )
    plausible = (
        np.concatenate(bd_plausible_parts) if bd_plausible_parts else np.array([], dtype=np.float64)
    )
    print_numeric_stats(
        f"bd restricted to plausible ages {BD_PLAUSIBLE_MIN}-{BD_PLAUSIBLE_MAX}",
        describe_numeric(plausible),
    )
    print("Do not use bd/age as a core REVEN feature.")

    return {
        "total_members": total,
        "unique_members": unique_count,
        "reg_min": reg_min,
        "reg_max": reg_max,
        "labeled_registration": labeled_reg,
    }


def analyze_transactions(path: Path, chunksize: int) -> dict:
    print_heading("2. TRANSACTIONS / PAYMENT")
    print(f"Source: {path.relative_to(REPO_ROOT).as_posix()}")
    encoding = choose_encoding(path)
    print(f"Encoding: {encoding}")
    print(f"Read mode: chunked pandas.read_csv(chunksize={chunksize:,})")

    total = 0
    txn_min = txn_max = None
    exp_min = exp_max = None
    auto_renew_n = 0
    cancel_n = 0
    auto_and_cancel = 0
    non_auto_n = 0
    non_auto_and_cancel = 0
    price_mismatch = 0
    paid_zero = 0
    method_counts: Counter = Counter()
    plan_day_counts: Counter = Counter()
    list_price_parts: list[np.ndarray] = []
    paid_parts: list[np.ndarray] = []
    customer_agg: pd.DataFrame | None = None

    for chunk in chunk_reader(
        path, chunksize=chunksize, encoding=encoding, usecols=TRANSACTIONS_COLS
    ):
        total += len(chunk)
        if "transaction_date" in chunk.columns:
            txn_min, txn_max = update_date_bounds(txn_min, txn_max, chunk["transaction_date"])
        if "membership_expire_date" in chunk.columns:
            exp_min, exp_max = update_date_bounds(exp_min, exp_max, chunk["membership_expire_date"])

        auto = pd.to_numeric(chunk["is_auto_renew"], errors="coerce").fillna(0).astype("int64")
        cancel = pd.to_numeric(chunk["is_cancel"], errors="coerce").fillna(0).astype("int64")
        auto_renew_n += int((auto == 1).sum())
        cancel_n += int((cancel == 1).sum())
        auto_and_cancel += int(((auto == 1) & (cancel == 1)).sum())
        non_auto_n += int((auto != 1).sum())
        non_auto_and_cancel += int(((auto != 1) & (cancel == 1)).sum())

        list_price = pd.to_numeric(chunk["plan_list_price"], errors="coerce")
        paid = pd.to_numeric(chunk["actual_amount_paid"], errors="coerce")
        comparable = list_price.notna() & paid.notna()
        price_mismatch += int((comparable & (paid != list_price)).sum())
        paid_zero += int((paid == 0).sum())
        list_price_parts.append(list_price.dropna().to_numpy(dtype=np.float64))
        paid_parts.append(paid.dropna().to_numpy(dtype=np.float64))

        add_value_counts(method_counts, chunk["payment_method_id"])
        add_value_counts(plan_day_counts, chunk["payment_plan_days"])

        chunk = chunk.copy()
        chunk["is_auto_renew"] = auto
        chunk["is_cancel"] = cancel
        chunk["actual_amount_paid"] = paid
        chunk["_paid_valid"] = paid.notna().astype("int64")
        g = chunk.groupby("msno", sort=False).agg(
            txn_count=("msno", "size"),
            auto_renew_sum=("is_auto_renew", "sum"),
            cancel_sum=("is_cancel", "sum"),
            amount_sum=("actual_amount_paid", "sum"),
            amount_count=("_paid_valid", "sum"),
        )
        customer_agg = merge_customer_frame(customer_agg, g)

    unique_customers = 0 if customer_agg is None else len(customer_agg)
    freq = (
        customer_agg["txn_count"].to_numpy(dtype=np.float64)
        if customer_agg is not None
        else np.array([], dtype=np.float64)
    )
    at_least_2 = int((freq >= 2).sum()) if freq.size else 0
    at_least_3 = int((freq >= 3).sum()) if freq.size else 0

    list_price_all = (
        np.concatenate(list_price_parts) if list_price_parts else np.array([], dtype=np.float64)
    )
    paid_all = np.concatenate(paid_parts) if paid_parts else np.array([], dtype=np.float64)

    print()
    print(f"Total transactions: {total:,}")
    print(f"Unique customers: {unique_customers:,}")
    print(f"Transaction date range: {fmt_date(txn_min)} to {fmt_date(txn_max)}")
    print(f"Membership expiry date range: {fmt_date(exp_min)} to {fmt_date(exp_max)}")
    print(f"Auto-renew transactions: {auto_renew_n:,} ({pct(auto_renew_n, total)})")
    print(f"Cancellation transactions: {cancel_n:,} ({pct(cancel_n, total)})")

    print_subheading("payment_method_id distribution (top 15)")
    print_counter(method_counts, total=total, top=15, label="payment_method_id")

    print_subheading("payment_plan_days distribution")
    print_counter(plan_day_counts, total=total, label="payment_plan_days")

    print_subheading("plan_list_price statistics")
    print_numeric_stats("plan_list_price", describe_numeric(list_price_all))

    print_subheading("actual_amount_paid statistics")
    print_numeric_stats("actual_amount_paid", describe_numeric(paid_all))

    print()
    print(
        f"actual_amount_paid != plan_list_price: {price_mismatch:,} ({pct(price_mismatch, total)})"
    )
    print(f"actual_amount_paid == 0: {paid_zero:,} ({pct(paid_zero, total)})")

    print_subheading("transaction frequency per customer")
    print_numeric_stats("transactions per customer", describe_numeric(freq))
    print(f"Customers with at least 2 transactions: {at_least_2:,} ({pct(at_least_2, unique_customers)})")
    print(f"Customers with at least 3 transactions: {at_least_3:,} ({pct(at_least_3, unique_customers)})")

    print_subheading("cancellation by auto-renew flag (descriptive only, not causal)")
    print(
        f"Cancellation rate among auto-renewing transactions: "
        f"{auto_and_cancel:,} / {auto_renew_n:,} = {pct(auto_and_cancel, auto_renew_n)}"
    )
    print(
        f"Cancellation rate among non-auto-renewing transactions: "
        f"{non_auto_and_cancel:,} / {non_auto_n:,} = {pct(non_auto_and_cancel, non_auto_n)}"
    )

    if customer_agg is not None:
        customer_agg["avg_amount_paid"] = np.where(
            customer_agg["amount_count"] > 0,
            customer_agg["amount_sum"] / customer_agg["amount_count"],
            np.nan,
        )
        customer_agg["auto_renew_rate"] = np.where(
            customer_agg["txn_count"] > 0,
            customer_agg["auto_renew_sum"] / customer_agg["txn_count"],
            np.nan,
        )
        customer_agg["cancel_rate"] = np.where(
            customer_agg["txn_count"] > 0,
            customer_agg["cancel_sum"] / customer_agg["txn_count"],
            np.nan,
        )

    return {
        "total_txns": total,
        "unique_customers": unique_customers,
        "txn_min": txn_min,
        "txn_max": txn_max,
        "exp_min": exp_min,
        "exp_max": exp_max,
        "auto_renew_pct": (100.0 * auto_renew_n / total) if total else None,
        "cancel_pct": (100.0 * cancel_n / total) if total else None,
        "auto_cancel_pct": (100.0 * auto_and_cancel / auto_renew_n) if auto_renew_n else None,
        "non_auto_cancel_pct": (100.0 * non_auto_and_cancel / non_auto_n) if non_auto_n else None,
        "plan_day_counts": plan_day_counts,
        "list_price_stats": describe_numeric(list_price_all),
        "paid_stats": describe_numeric(paid_all),
        "freq_stats": describe_numeric(freq),
        "at_least_2": at_least_2,
        "at_least_3": at_least_3,
        "customer_agg": customer_agg,
        "paid_zero_pct": (100.0 * paid_zero / total) if total else None,
        "mismatch_pct": (100.0 * price_mismatch / total) if total else None,
    }


def analyze_user_logs(path: Path, chunksize: int, labeled_ids: set[str]) -> dict:
    print_heading("3. ENGAGEMENT / USER LOGS")
    print(f"Source: {path.relative_to(REPO_ROOT).as_posix()}")
    print("user_logs_v2.csv is never loaded in full. Only chunked reads and bounded aggregates are kept.")
    encoding = choose_encoding(path)
    print(f"Encoding: {encoding}")
    print(f"Read mode: chunked pandas.read_csv(chunksize={chunksize:,})")
    print(f"Columns read: {USER_LOGS_COLS}")

    total_rows = 0
    unique_user_hashes: set[int] = set()
    date_min = date_max = None
    daily_unique: dict[int, np.ndarray] = {}
    all_user_days: dict[int, int] = {}
    secs_reservoir = ReservoirSampler(PERCENTILE_RESERVOIR, seed=42)
    unq_reservoir = ReservoirSampler(PERCENTILE_RESERVOIR, seed=43)
    secs_sum = 0.0
    secs_count = 0
    unq_sum = 0.0
    unq_count = 0
    negative_secs = 0
    over_day_secs = 0
    labeled_eng: pd.DataFrame | None = None
    user_date_dupes = 0
    secs_by_date_sum: dict[int, float] = {}
    secs_by_date_n: dict[int, int] = {}

    for chunk in chunk_reader(
        path, chunksize=chunksize, encoding=encoding, usecols=USER_LOGS_COLS
    ):
        total_rows += len(chunk)
        hashes = pd.util.hash_pandas_object(chunk["msno"], index=False).to_numpy(dtype=np.uint64)
        unique_user_hashes.update(hashes.tolist())

        date_min, date_max = update_date_bounds(date_min, date_max, chunk["date"])
        date_int = pd.to_numeric(chunk["date"], errors="coerce").fillna(-1).astype(np.int64).to_numpy()

        for d in np.unique(date_int):
            if d < 0:
                continue
            part = np.unique(hashes[date_int == d])
            if d in daily_unique:
                daily_unique[d] = np.unique(np.concatenate([daily_unique[d], part]))
            else:
                daily_unique[d] = part

        dupes = chunk.duplicated(subset=["msno", "date"]).sum()
        user_date_dupes += int(dupes)
        day_counts = pd.Series(hashes).value_counts()
        for h, c in day_counts.items():
            all_user_days[int(h)] = all_user_days.get(int(h), 0) + int(c)

        secs = pd.to_numeric(chunk["total_secs"], errors="coerce")
        unq = pd.to_numeric(chunk["num_unq"], errors="coerce")
        secs_valid = secs.dropna()
        unq_valid = unq.dropna()
        if not secs_valid.empty:
            arr = secs_valid.to_numpy(dtype=np.float64)
            negative_secs += int((arr < 0).sum())
            over_day_secs += int((arr > 86400).sum())
            secs_sum += float(arr.sum())
            secs_count += int(arr.size)
            secs_reservoir.update(arr)
            date_for_secs = date_int[secs.notna().to_numpy()]
            for d in np.unique(date_for_secs):
                if d < 0:
                    continue
                part = arr[date_for_secs == d]
                secs_by_date_sum[int(d)] = secs_by_date_sum.get(int(d), 0.0) + float(part.sum())
                secs_by_date_n[int(d)] = secs_by_date_n.get(int(d), 0) + int(part.size)
        if not unq_valid.empty:
            arr = unq_valid.to_numpy(dtype=np.float64)
            unq_sum += float(arr.sum())
            unq_count += int(arr.size)
            unq_reservoir.update(arr)

        if labeled_ids:
            mask = chunk["msno"].isin(labeled_ids)
            if mask.any():
                sub = chunk.loc[mask, ["msno", "date", "total_secs", "num_unq"]].copy()
                sub["total_secs"] = pd.to_numeric(sub["total_secs"], errors="coerce")
                sub["num_unq"] = pd.to_numeric(sub["num_unq"], errors="coerce")
                sub["date"] = pd.to_numeric(sub["date"], errors="coerce")
                g = sub.groupby("msno", sort=False).agg(
                    active_days=("date", "nunique"),
                    total_secs=("total_secs", "sum"),
                    total_num_unq=("num_unq", "sum"),
                    last_active_date=("date", "max"),
                    first_active_date=("date", "min"),
                )
                labeled_eng = merge_engagement_frame(labeled_eng, g)

    dau = np.array([len(v) for v in daily_unique.values()], dtype=np.float64)
    active_days_arr = (
        np.fromiter(all_user_days.values(), dtype=np.float64, count=len(all_user_days))
        if all_user_days
        else np.array([], dtype=np.float64)
    )
    secs_stats = describe_numeric(secs_reservoir.values())
    unq_stats = describe_numeric(unq_reservoir.values())
    mean_secs = (secs_sum / secs_count) if secs_count else float("nan")
    mean_unq = (unq_sum / unq_count) if unq_count else float("nan")

    if labeled_eng is not None and not labeled_eng.empty:
        labeled_eng["avg_daily_total_secs"] = np.where(
            labeled_eng["active_days"] > 0,
            labeled_eng["total_secs"] / labeled_eng["active_days"],
            np.nan,
        )

    print()
    print(f"Total log rows: {total_rows:,}")
    print(f"Unique users (hashed msno): {len(unique_user_hashes):,}")
    print(f"Date range: {fmt_date(date_min)} to {fmt_date(date_max)}")
    print(f"Distinct calendar dates with logs: {len(daily_unique):,}")
    print(f"Duplicate (msno, date) rows observed: {user_date_dupes:,}")
    print(
        "Active days per user uses row counts per hashed user. "
        "If the file is one row per user-day, this equals active days."
    )
    if dau.size:
        print(f"Average daily active users: {fmt_num(float(np.mean(dau)))}")
        print(f"Median daily active users: {fmt_num(float(np.median(dau)))}")
        print(f"Min / max DAU: {fmt_num(int(np.min(dau)))} / {fmt_num(int(np.max(dau)))}")
    else:
        print("Daily active users: n/a (no parseable dates)")

    print_subheading("active days per user (observation window)")
    print_numeric_stats("active days per user", describe_numeric(active_days_arr))

    print_subheading("total_secs per active user-day")
    print(f"Exact mean (all finite values): {fmt_num(mean_secs)}")
    print(
        f"Percentiles from reservoir sample n={secs_reservoir.filled:,} "
        f"of {secs_count:,} finite values (not a full in-memory column)."
    )
    print_numeric_stats("total_secs (reservoir)", secs_stats)
    print(f"Negative total_secs rows: {negative_secs:,} ({pct(negative_secs, total_rows)})")
    print(
        f"total_secs > 86400 (more than 24h in one day): {over_day_secs:,} "
        f"({pct(over_day_secs, total_rows)})"
    )

    print_subheading("num_unq per active user-day")
    print(f"Exact mean (all finite values): {fmt_num(mean_unq)}")
    print(
        f"Percentiles from reservoir sample n={unq_reservoir.filled:,} "
        f"of {unq_count:,} finite values."
    )
    print_numeric_stats("num_unq (reservoir)", unq_stats)

    print_subheading("per-user engagement summaries (labeled customers only)")
    if labeled_eng is None or labeled_eng.empty:
        print("No overlap between user logs and train_v2 msno values, or train file missing.")
    else:
        print(f"Labeled customers with at least one log row: {len(labeled_eng):,}")
        print_numeric_stats("active_days (labeled, in log window)", describe_numeric(labeled_eng["active_days"].to_numpy()))
        print_numeric_stats("total_secs (labeled, summed over window)", describe_numeric(labeled_eng["total_secs"].to_numpy()))
        print_numeric_stats(
            "average daily total_secs (labeled)",
            describe_numeric(labeled_eng["avg_daily_total_secs"].to_numpy()),
        )
        print_numeric_stats("total num_unq (labeled, summed)", describe_numeric(labeled_eng["total_num_unq"].to_numpy()))
        last_parsed = parse_kkbox_dates(labeled_eng["last_active_date"])
        print(f"Last active date among labeled users with logs: min={fmt_date(last_parsed.min())} max={fmt_date(last_parsed.max())}")
        print("These summaries cover the available log window (typically a single month in this extract).")

    half_split_note = None
    first_half_mean = second_half_mean = None
    if date_min is not None and date_max is not None:
        span = (pd.Timestamp(date_max) - pd.Timestamp(date_min)).days
        half_split_note = span
        if span >= 2 and secs_by_date_n:
            midpoint_int = int(
                (
                    pd.Timestamp(date_min) + (pd.Timestamp(date_max) - pd.Timestamp(date_min)) / 2
                ).strftime("%Y%m%d")
            )
            first_sum = first_n = second_sum = second_n = 0.0
            for d, n in secs_by_date_n.items():
                if d <= midpoint_int:
                    first_sum += secs_by_date_sum.get(d, 0.0)
                    first_n += n
                else:
                    second_sum += secs_by_date_sum.get(d, 0.0)
                    second_n += n
            first_half_mean = (first_sum / first_n) if first_n else None
            second_half_mean = (second_sum / second_n) if second_n else None
            print_subheading("within-window activity split (not multi-month decline)")
            print(f"Log window span: {span} days. Date midpoint (YYYYMMDD): {midpoint_int}.")
            print(f"Mean total_secs, first half of window: {fmt_num(first_half_mean)}")
            print(f"Mean total_secs, second half of window: {fmt_num(second_half_mean)}")
            print(
                "INFERENCE AID ONLY: this compares two halves of the same short log window. "
                "It is not a measured month-over-month engagement decline."
            )

    return {
        "total_rows": total_rows,
        "unique_users": len(unique_user_hashes),
        "date_min": date_min,
        "date_max": date_max,
        "n_dates": len(daily_unique),
        "mean_dau": float(np.mean(dau)) if dau.size else None,
        "median_dau": float(np.median(dau)) if dau.size else None,
        "active_days_stats": describe_numeric(active_days_arr),
        "mean_secs": mean_secs,
        "secs_stats": secs_stats,
        "mean_unq": mean_unq,
        "unq_stats": unq_stats,
        "labeled_eng": labeled_eng,
        "window_span_days": half_split_note,
        "first_half_mean": first_half_mean,
        "second_half_mean": second_half_mean,
        "daily_unique": daily_unique,
    }


def load_train(path: Path, chunksize: int) -> pd.DataFrame:
    encoding = choose_encoding(path)
    parts: list[pd.DataFrame] = []
    for chunk in chunk_reader(path, chunksize=chunksize, encoding=encoding, usecols=TRAIN_COLS):
        parts.append(chunk)
    if not parts:
        return pd.DataFrame(columns=TRAIN_COLS)
    train = pd.concat(parts, ignore_index=True)
    train["is_churn"] = pd.to_numeric(train["is_churn"], errors="coerce")
    return train


def print_group_compare(joined: pd.DataFrame, column: str, churn_col: str = "is_churn") -> None:
    if column not in joined.columns:
        print(f"{column}: not available")
        return
    grouped = joined.groupby(churn_col)[column]
    rows = []
    for label, series in grouped:
        stats = describe_numeric(series.to_numpy(dtype=np.float64))
        name = "churn=1" if label == 1 else ("churn=0" if label == 0 else str(label))
        rows.append(
            {
                "group": name,
                "count": int(stats["count"]),
                "mean": round(stats["mean"], 4) if np.isfinite(stats["mean"]) else None,
                "median": round(stats["median"], 4) if np.isfinite(stats["median"]) else None,
                "p25": round(stats["p25"], 4) if np.isfinite(stats["p25"]) else None,
                "p75": round(stats["p75"], 4) if np.isfinite(stats["p75"]) else None,
            }
        )
    if rows:
        print(pd.DataFrame(rows).to_string(index=False))
    else:
        print(f"{column}: no grouped values")


def churn_rate_by_bins(joined: pd.DataFrame, column: str, bins: int = 4) -> None:
    if column not in joined.columns or joined[column].notna().sum() == 0:
        print(f"Churn rate by {column}: n/a")
        return
    try:
        q = pd.qcut(joined[column], q=bins, duplicates="drop")
    except ValueError:
        print(f"Churn rate by {column}: could not form quantile bins.")
        return
    tab = joined.groupby(q, observed=False)["is_churn"].agg(["count", "sum", "mean"])
    tab = tab.rename(columns={"sum": "churn_count", "mean": "churn_rate"})
    tab["churn_rate_pct"] = (tab["churn_rate"] * 100).round(4)
    print(tab[["count", "churn_count", "churn_rate_pct"]].to_string())
    print("Descriptive association only. Not a predictive model and not a causal effect.")


def analyze_churn(
    train: pd.DataFrame,
    txn: dict,
    logs: dict,
    members: dict,
) -> dict:
    print_heading("4. CHURN / RENEWAL")
    print("Source: train_v2.csv, joined to customer-level aggregates only (no raw log rows).")
    print("No predictive model is trained. No churn-probability model is fit.")

    total = len(train)
    unique = train["msno"].nunique(dropna=False) if "msno" in train.columns else 0
    churn_n = int((train["is_churn"] == 1).sum()) if "is_churn" in train.columns else 0
    non_churn_n = int((train["is_churn"] == 0).sum()) if "is_churn" in train.columns else 0
    other = total - churn_n - non_churn_n

    print()
    print(f"Total labeled rows: {total:,}")
    print(f"Unique labeled customers: {unique:,}")
    print(f"Churn count (is_churn=1): {churn_n:,}")
    print(f"Non-churn count (is_churn=0): {non_churn_n:,}")
    if other:
        print(f"Other / unparseable is_churn values: {other:,}")
    print(f"Churn percentage: {pct(churn_n, total)}")

    joined = train.drop_duplicates(subset=["msno"], keep="first").copy()
    customer_agg = txn.get("customer_agg")
    if customer_agg is not None:
        joined = joined.merge(
            customer_agg.reset_index(),
            on="msno",
            how="left",
        )
    labeled_eng = logs.get("labeled_eng")
    if labeled_eng is not None and not labeled_eng.empty:
        joined = joined.merge(
            labeled_eng.reset_index(),
            on="msno",
            how="left",
        )

    labeled_reg = members.get("labeled_registration") or {}
    if labeled_reg:
        joined["registration_init_time"] = joined["msno"].map(labeled_reg)
        joined["registration_date"] = parse_kkbox_dates(joined["registration_init_time"])
        ref = logs.get("date_max") or txn.get("txn_max")
        if ref is not None:
            joined["tenure_days"] = (pd.Timestamp(ref) - joined["registration_date"]).dt.days

    has_txn = joined["txn_count"].notna() if "txn_count" in joined.columns else pd.Series(False, index=joined.index)
    has_eng = joined["active_days"].notna() if "active_days" in joined.columns else pd.Series(False, index=joined.index)
    print()
    print(f"Labeled customers matched to transaction aggregates: {int(has_txn.sum()):,} ({pct(int(has_txn.sum()), len(joined))})")
    print(f"Labeled customers matched to engagement aggregates: {int(has_eng.sum()):,} ({pct(int(has_eng.sum()), len(joined))})")
    print("Unmatched engagement is expected if a labeled user has no rows in user_logs_v2.")

    print_subheading("descriptive stats by is_churn")
    for col in (
        "txn_count",
        "auto_renew_rate",
        "cancel_rate",
        "avg_amount_paid",
        "active_days",
        "total_secs",
        "avg_daily_total_secs",
        "total_num_unq",
        "tenure_days",
    ):
        print()
        print(col)
        print_group_compare(joined, col)

    print_subheading("churn rate by quantile bins (descriptive)")
    for col in ("txn_count", "avg_amount_paid", "active_days", "total_secs", "auto_renew_rate"):
        print()
        print(col)
        churn_rate_by_bins(joined, col)

    if "auto_renew_rate" in joined.columns:
        ever_auto = joined["auto_renew_sum"] > 0 if "auto_renew_sum" in joined.columns else None
        if ever_auto is not None:
            print_subheading("churn rate by any auto-renew transaction (descriptive)")
            tmp = joined.loc[joined["auto_renew_sum"].notna()].copy()
            tmp["any_auto_renew"] = tmp["auto_renew_sum"] > 0
            tab = tmp.groupby("any_auto_renew")["is_churn"].agg(["count", "sum", "mean"])
            tab["churn_rate_pct"] = (tab["mean"] * 100).round(4)
            print(tab[["count", "sum", "churn_rate_pct"]].to_string())
            print("Descriptive only. Auto-renew is not interpreted as causing retention.")

    if "cancel_sum" in joined.columns:
        print_subheading("churn rate by any cancellation transaction (descriptive)")
        tmp = joined.loc[joined["cancel_sum"].notna()].copy()
        tmp["any_cancel"] = tmp["cancel_sum"] > 0
        tab = tmp.groupby("any_cancel")["is_churn"].agg(["count", "sum", "mean"])
        tab["churn_rate_pct"] = (tab["mean"] * 100).round(4)
        print(tab[["count", "sum", "churn_rate_pct"]].to_string())

    if "active_days" in joined.columns:
        print_subheading("churn rate by any activity in the log window (descriptive)")
        tmp = joined.copy()
        tmp["any_activity"] = tmp["active_days"].fillna(0) > 0
        tab = tmp.groupby("any_activity")["is_churn"].agg(["count", "sum", "mean"])
        tab["churn_rate_pct"] = (tab["mean"] * 100).round(4)
        print(tab[["count", "sum", "churn_rate_pct"]].to_string())

    return {
        "labeled_rows": total,
        "unique_labeled": unique,
        "churn_n": churn_n,
        "non_churn_n": non_churn_n,
        "churn_pct": (100.0 * churn_n / total) if total else None,
        "joined": joined,
    }


def analyze_temporal(members: dict, txn: dict, logs: dict, churn: dict) -> None:
    print_heading("5. TEMPORAL STRUCTURE")
    print("Ranges below are measured from the files. KKBOX competition semantics are noted only as context.")

    print()
    print(f"Member registration period: {fmt_date(members.get('reg_min'))} to {fmt_date(members.get('reg_max'))}")
    print(f"Transaction observation period: {fmt_date(txn.get('txn_min'))} to {fmt_date(txn.get('txn_max'))}")
    print(f"Membership expiry dates present: {fmt_date(txn.get('exp_min'))} to {fmt_date(txn.get('exp_max'))}")
    print(f"Engagement observation period: {fmt_date(logs.get('date_min'))} to {fmt_date(logs.get('date_max'))}")
    print(
        f"Churn-label availability: train_v2.csv has {churn.get('labeled_rows', 0):,} rows "
        f"({churn.get('unique_labeled', 0):,} unique msno) with is_churn in {{0,1}} "
        f"(plus any unparseable values reported above)."
    )
    print("The label file has no timestamp column; the decision/label month is not stored in train_v2 itself.")

    log_min, log_max = logs.get("date_min"), logs.get("date_max")
    txn_min, txn_max = txn.get("txn_min"), txn.get("txn_max")
    exp_max = txn.get("exp_max")

    print_subheading("engagement vs transaction window")
    if log_min is not None and txn_min is not None:
        if pd.Timestamp(log_min) > pd.Timestamp(txn_min):
            print(
                f"FLAG: engagement starts ({fmt_date(log_min)}) after the earliest transactions "
                f"({fmt_date(txn_min)}). Logs do not cover the full transaction history."
            )
        if pd.Timestamp(log_max) < pd.Timestamp(txn_max):
            print(
                f"FLAG: engagement ends ({fmt_date(log_max)}) before the latest transactions "
                f"({fmt_date(txn_max)}). Later billing events have no matching activity trail in this extract."
            )
        if pd.Timestamp(log_min) >= pd.Timestamp(txn_min) and pd.Timestamp(log_max) <= pd.Timestamp(txn_max):
            print(
                "Measured: the engagement window sits inside the transaction date range. "
                "Activity is a short panel relative to billing history."
            )
    else:
        print("Could not compare engagement and transaction windows (missing dates).")

    print_subheading("churn decision period and leakage flags")
    print(
        "Context (not measured from a timestamp in train_v2): the public KKBOX WSDM v2 task "
        "typically treats is_churn as whether membership is renewed after an expiration in the "
        "month following a March 2017 observation window. That mapping is an inference unless "
        "confirmed by an official data dictionary in this repo."
    )
    if log_min is not None and log_max is not None:
        span = (pd.Timestamp(log_max) - pd.Timestamp(log_min)).days
        print(f"Measured engagement span: {span} days.")
        if span <= 40:
            print(
                "FLAG: engagement is a short window (about one month). "
                "It cannot support a long pre-churn activity history, and it is too short to "
                "measure multi-month engagement decline directly."
            )
        print(
            "FLAG (possible leakage / alignment risk): because train_v2 has no label date, "
            "joining March (or other) logs to is_churn is only valid if those logs are known "
            "to fall strictly before the renewal/churn outcome being labeled. If logs overlap "
            "or follow the expiration that defines is_churn, activity could leak post-decision information."
        )
        if exp_max is not None and pd.Timestamp(log_max) > pd.Timestamp(exp_max):
            print(
                f"FLAG: some log dates ({fmt_date(log_max)}) are after the latest membership_expire_date "
                f"({fmt_date(exp_max)}). Treat post-expiry activity as a leakage risk for any future model."
            )
        elif exp_max is not None:
            print(
                f"Latest log date {fmt_date(log_max)} vs latest membership_expire_date {fmt_date(exp_max)}: "
                "compare these before using logs as pre-decision features."
            )
    print(
        "FLAG: membership_expire_date can extend far beyond the transaction_date window "
        "(prepaid / long plans). Using future expiry values as if they were known at an earlier "
        "decision date would leak future subscription length."
    )
    print(
        "Safe calibration use: treat these files as sources of marginal distributions "
        "(prices, plan lengths, auto-renew rates, activity intensity, overall churn rate), "
        "not as a time-aligned panel ready for supervised training without an explicit cutoff."
    )


def print_calibration(members: dict, txn: dict, logs: dict, churn: dict) -> None:
    print_heading("6. REVEN CALIBRATION RECOMMENDATIONS")
    print()
    print("REVEN CALIBRATION INPUTS")
    print(THIN)
    print(
        "Recommendations below use measured statistics only. "
        "Anything not directly measured is labeled INFERENCE. "
        "No values are invented where the extract cannot support them."
    )

    price = txn.get("paid_stats") or {}
    list_price = txn.get("list_price_stats") or {}
    freq = txn.get("freq_stats") or {}
    plan_days: Counter = txn.get("plan_day_counts") or Counter()
    total_plan = sum(plan_days.values()) if plan_days else 0

    print()
    print("Subscription price")
    print(
        f"  MEASURED actual_amount_paid: mean={fmt_num(price.get('mean'))}, "
        f"median={fmt_num(price.get('median'))}, p25={fmt_num(price.get('p25'))}, "
        f"p75={fmt_num(price.get('p75'))}, min={fmt_num(price.get('min'))}, "
        f"max={fmt_num(price.get('max'))}"
    )
    print(
        f"  MEASURED plan_list_price: mean={fmt_num(list_price.get('mean'))}, "
        f"median={fmt_num(list_price.get('median'))}, p25={fmt_num(list_price.get('p25'))}, "
        f"p75={fmt_num(list_price.get('p75'))}"
    )
    if txn.get("mismatch_pct") is not None:
        print(f"  MEASURED share where paid != list price: {txn['mismatch_pct']:.4f}%")
    if txn.get("paid_zero_pct") is not None:
        print(f"  MEASURED share where paid == 0: {txn['paid_zero_pct']:.4f}%")
    print("  INFERENCE: units are KKBOX list/paid amounts (not USD). Map to Streamflix currency separately.")
    print(
        "  Simulator input to consider later: a discrete price schedule around the measured "
        "median/p25/p75 paid amounts, plus a small mass of zero-paid and discounted (paid < list) txns "
        "if those shares are material."
    )

    print()
    print("Subscription duration")
    if plan_days and total_plan:
        top = plan_days.most_common(8)
        desc = ", ".join(f"{k} days ({100.0 * v / total_plan:.2f}%)" for k, v in top)
        print(f"  MEASURED payment_plan_days (top): {desc}")
        print(
            "  Simulator input to consider later: mix of plan lengths using this empirical distribution "
            "(commonly 30-day cycles if that dominates)."
        )
    else:
        print("  NOT MEASURED: payment_plan_days distribution was empty.")

    print()
    print("Transaction frequency")
    print(
        f"  MEASURED txns per customer: mean={fmt_num(freq.get('mean'))}, "
        f"median={fmt_num(freq.get('median'))}, p25={fmt_num(freq.get('p25'))}, "
        f"p75={fmt_num(freq.get('p75'))}, max={fmt_num(freq.get('max'))}"
    )
    uniq = txn.get("unique_customers") or 0
    print(
        f"  MEASURED customers with >=2 txns: {txn.get('at_least_2', 0):,} "
        f"({pct(txn.get('at_least_2', 0), uniq)}); "
        f">=3 txns: {txn.get('at_least_3', 0):,} ({pct(txn.get('at_least_3', 0), uniq)})"
    )
    print(
        "  INFERENCE: this extract's transaction file may be a truncated window, so frequency is "
        "frequency-in-file, not lifetime billing frequency."
    )

    print()
    print("Auto-renew probability")
    if txn.get("auto_renew_pct") is not None:
        print(f"  MEASURED P(is_auto_renew=1) at transaction level: {txn['auto_renew_pct']:.4f}%")
        print("  Simulator input to consider later: initialize auto-renew near this transaction-level rate.")
    else:
        print("  NOT MEASURED: auto-renew rate unavailable.")

    print()
    print("Cancellation probability")
    if txn.get("cancel_pct") is not None:
        print(f"  MEASURED P(is_cancel=1) at transaction level: {txn['cancel_pct']:.4f}%")
    if txn.get("auto_cancel_pct") is not None:
        print(f"  MEASURED cancel | auto-renew: {txn['auto_cancel_pct']:.4f}%")
    if txn.get("non_auto_cancel_pct") is not None:
        print(f"  MEASURED cancel | not auto-renew: {txn['non_auto_cancel_pct']:.4f}%")
    print("  These are descriptive rates on transactions, not per-customer hazard rates.")

    print()
    print("Engagement / activity")
    ad = logs.get("active_days_stats") or {}
    print(
        f"  MEASURED log window: {fmt_date(logs.get('date_min'))} to {fmt_date(logs.get('date_max'))} "
        f"({logs.get('n_dates', 0)} distinct dates)"
    )
    print(f"  MEASURED mean DAU: {fmt_num(logs.get('mean_dau'))}; median DAU: {fmt_num(logs.get('median_dau'))}")
    print(
        f"  MEASURED active days/user in window: mean={fmt_num(ad.get('mean'))}, "
        f"median={fmt_num(ad.get('median'))}, p25={fmt_num(ad.get('p25'))}, p75={fmt_num(ad.get('p75'))}"
    )
    print(f"  MEASURED mean total_secs per user-day: {fmt_num(logs.get('mean_secs'))}")
    secs = logs.get("secs_stats") or {}
    print(
        f"  MEASURED total_secs percentiles (reservoir): "
        f"p25={fmt_num(secs.get('p25'))}, median={fmt_num(secs.get('median'))}, p75={fmt_num(secs.get('p75'))}"
    )
    print(f"  MEASURED mean num_unq per user-day: {fmt_num(logs.get('mean_unq'))}")
    unq = logs.get("unq_stats") or {}
    print(
        f"  MEASURED num_unq percentiles (reservoir): "
        f"p25={fmt_num(unq.get('p25'))}, median={fmt_num(unq.get('median'))}, p75={fmt_num(unq.get('p75'))}"
    )
    print(
        "  Simulator input to consider later: daily activity probability ≈ median active days / "
        "window length, with session length drawn from the total_secs distribution (clipping negatives "
        "and >86400 as data errors)."
    )
    span = logs.get("window_span_days")
    if span:
        print(f"  Window length used for that ratio: {span} days (MEASURED).")

    print()
    print("Engagement decline")
    print(
        "  NOT DIRECTLY MEASURED: user_logs_v2 in this extract is a short window, so month-over-month "
        "decline cannot be estimated from a second month of logs."
    )
    print(
        "  INFERENCE only: a future Streamflix simulator may still include an optional decline process "
        "for retention scenarios, but its slope should be treated as a free parameter, not a KKBOX fit."
    )
    if logs.get("first_half_mean") is not None and logs.get("second_half_mean") is not None:
        print(
            f"  MEASURED within the same window only: mean total_secs first half="
            f"{fmt_num(logs.get('first_half_mean'))}, second half="
            f"{fmt_num(logs.get('second_half_mean'))} (not a month-over-month decline)."
        )
    print(
        "  Related MEASURED association (not decline): churn vs active_days / total_secs is reported in "
        "section 4 as a cross-section, not as a within-user trajectory."
    )

    print()
    print("Customer tenure")
    print(
        f"  MEASURED member registration range: {fmt_date(members.get('reg_min'))} to "
        f"{fmt_date(members.get('reg_max'))}"
    )
    joined = churn.get("joined")
    if joined is not None and "tenure_days" in joined.columns and joined["tenure_days"].notna().any():
        tstats = describe_numeric(joined["tenure_days"].to_numpy(dtype=np.float64))
        print(
            f"  MEASURED tenure_days for labeled customers with a registration date, "
            f"using reference date = engagement max or else transaction max: "
            f"mean={fmt_num(tstats['mean'])}, median={fmt_num(tstats['median'])}, "
            f"p25={fmt_num(tstats['p25'])}, p75={fmt_num(tstats['p75'])}"
        )
        print(
            "  Simulator input to consider later: draw tenure from this labeled-customer distribution "
            "(not from all 6.7M members, many of whom are not in the churn file)."
        )
    else:
        print(
            "  NOT MEASURED at customer level: could not compute tenure for labeled users "
            "(missing registration join or reference date)."
        )

    print()
    print("Churn / renewal behavior")
    if churn.get("churn_pct") is not None:
        print(f"  MEASURED is_churn rate: {churn['churn_pct']:.4f}%")
        print(f"  MEASURED churn count: {churn.get('churn_n', 0):,}; non-churn: {churn.get('non_churn_n', 0):,}")
        print(
            "  Simulator input to consider later: baseline monthly (or cycle) churn near this labeled rate, "
            "with descriptive lifts from auto-renew / cancel / activity as reported in section 4 — "
            "those lifts are associations, not intervention effects."
        )
    else:
        print("  NOT MEASURED: churn rate unavailable.")
    print(
        "  INFERENCE: KKBOX is_churn is a competition label around membership expiration/renewal, "
        "not a REVEN-style payment-failure event. Do not copy it as dunning risk."
    )

    print()
    print("Not supported by this extract (do not fabricate)")
    print("  - Payment failure reasons, retries, card expiry (not in these CSVs)")
    print("  - Intervention history, contact fatigue, incentives (not in these CSVs)")
    print("  - Multi-month engagement trajectories (logs are a short window)")
    print("  - USD OTT list prices (amounts are KKBOX plan units)")
    print("  - Causal effect of auto-renew or cancellation on churn")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only KKBOX statistical calibration analysis (no writes, no model)."
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
        default=150_000,
        help="Rows per chunk for members, transactions, and train (default: 150000)",
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

    print_heading("REVEN — KKBOX calibration analysis")
    print(f"Repository root: {REPO_ROOT}")
    print(f"Data directory: {data_dir}")
    print("Read-only. Raw files are not modified. No processed datasets are written.")
    print("No ML model is trained.")

    if args.chunksize < 1 or args.user_logs_chunksize < 1:
        print("ERROR: chunksize must be >= 1")
        return 1
    if not data_dir.exists():
        print(f"ERROR: data directory does not exist: {data_dir}")
        return 1

    errors: list[str] = []
    members: dict = {}
    txn: dict = {}
    logs: dict = {}
    churn: dict = {}
    train = pd.DataFrame(columns=TRAIN_COLS)
    labeled_ids: set[str] = set()

    try:
        train_path = resolve_csv_path(data_dir, TRAIN_FILE)
        print()
        print(f"Loading labels first (chunked): {train_path.relative_to(REPO_ROOT).as_posix()}")
        train = load_train(train_path, args.chunksize)
        labeled_ids = set(train["msno"].dropna())
        print(f"Labeled msno loaded for memory-conscious joins: {len(labeled_ids):,}")
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        errors.append(str(exc))
    except Exception as exc:
        print(f"ERROR: failed reading {TRAIN_FILE}: {exc}")
        traceback.print_exc()
        errors.append(str(exc))

    try:
        path = resolve_csv_path(data_dir, MEMBERS_FILE)
        members = analyze_members(path, args.chunksize, labeled_ids)
    except FileNotFoundError as exc:
        print_heading("1. CUSTOMER / MEMBERSHIP")
        print(f"ERROR: {exc}")
        errors.append(str(exc))
    except MemoryError:
        msg = f"ERROR: insufficient memory while analyzing {MEMBERS_FILE}. Re-run with a smaller --chunksize."
        print(msg)
        errors.append(msg)
    except Exception as exc:
        print(f"ERROR: unexpected failure in members analysis: {exc}")
        traceback.print_exc()
        errors.append(str(exc))

    try:
        path = resolve_csv_path(data_dir, TRANSACTIONS_FILE)
        txn = analyze_transactions(path, args.chunksize)
    except FileNotFoundError as exc:
        print_heading("2. TRANSACTIONS / PAYMENT")
        print(f"ERROR: {exc}")
        errors.append(str(exc))
    except MemoryError:
        msg = f"ERROR: insufficient memory while analyzing {TRANSACTIONS_FILE}. Re-run with a smaller --chunksize."
        print(msg)
        errors.append(msg)
    except Exception as exc:
        print(f"ERROR: unexpected failure in transactions analysis: {exc}")
        traceback.print_exc()
        errors.append(str(exc))

    try:
        path = resolve_csv_path(data_dir, USER_LOGS_FILE)
        logs = analyze_user_logs(path, args.user_logs_chunksize, labeled_ids)
    except FileNotFoundError as exc:
        print_heading("3. ENGAGEMENT / USER LOGS")
        print(f"ERROR: {exc}")
        errors.append(str(exc))
    except MemoryError:
        msg = (
            f"ERROR: insufficient memory while analyzing {USER_LOGS_FILE}. "
            "Re-run with a smaller --user-logs-chunksize."
        )
        print(msg)
        errors.append(msg)
    except Exception as exc:
        print(f"ERROR: unexpected failure in user-logs analysis: {exc}")
        traceback.print_exc()
        errors.append(str(exc))

    try:
        if not train.empty:
            churn = analyze_churn(train, txn, logs, members)
        else:
            print_heading("4. CHURN / RENEWAL")
            print("ERROR: train_v2.csv was not loaded; churn section skipped.")
            errors.append("train_v2.csv not loaded")
    except MemoryError:
        msg = "ERROR: insufficient memory while joining churn aggregates."
        print(msg)
        errors.append(msg)
    except Exception as exc:
        print(f"ERROR: unexpected failure in churn analysis: {exc}")
        traceback.print_exc()
        errors.append(str(exc))

    try:
        analyze_temporal(members, txn, logs, churn)
    except Exception as exc:
        print(f"ERROR: unexpected failure in temporal section: {exc}")
        traceback.print_exc()
        errors.append(str(exc))

    try:
        print_calibration(members, txn, logs, churn)
    except Exception as exc:
        print(f"ERROR: unexpected failure in calibration section: {exc}")
        traceback.print_exc()
        errors.append(str(exc))

    print_heading("Analysis complete")
    if errors:
        print(f"Finished with {len(errors)} error(s). See messages above.")
        return 1
    print("Finished successfully. No raw files were changed. No datasets were written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
