#!/usr/bin/env python3
# analyze_gwstats.py
#
# Usage examples:
#   python3 analyze_gwstats.py --log-glob "gw*.log" --db-glob "run_*.db" --outdir results
#   python3 analyze_gwstats.py --log-glob "logs/gw*.log" --db-glob "db/run_*.db" --outdir results
#
# Notes:
# - GWSTAT lines are expected like:
#   GWSTAT up=12.0s rx=200.0 msg/s db=200.0 row/s kbps=123.4 avg_payload=148B avg_commit=1.2ms max_commit=4.5ms qlen=0 qmax=3 batch=50
# - The script tries to infer (batch, state_rate_hz) from filename patterns:
#   ...b50...r200... or ...batch50...rate200...
#   If it can't infer rate, it falls back to rounding mean rx as "rate".
#
# Outputs:
# - gwstat_samples.csv
# - runs_summary.csv
# - fig3_throughput.png
# - fig4_commit_box.png
# - fig5_storage.png

from __future__ import annotations

import argparse
import csv
import glob
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt


# -------------------------
# Parsing helpers
# -------------------------

_NUM_UNIT_RE = re.compile(r"^([+-]?\d+(?:\.\d+)?)([A-Za-z/]+)?$")


def parse_num_with_unit(s: str) -> Optional[float]:
    """
    Parse strings like:
      "12.0s" -> seconds
      "1.2ms" -> milliseconds
      "148B"  -> bytes
      "2.5KB" -> kilobytes
      "123.4" -> unitless

    Returns a float in a normalized unit depending on suffix:
      - time: returned in seconds for 's', milliseconds for 'ms' (we will convert later as needed)
      - bytes: returned in bytes (B) if suffix is B/KB/MB
      - unitless: float
    If cannot parse -> None
    """
    m = _NUM_UNIT_RE.match(s.strip())
    if not m:
        return None
    val = float(m.group(1))
    unit = (m.group(2) or "").strip()

    unit_l = unit.lower()

    # time
    if unit_l == "s":
        return val  # seconds
    if unit_l == "ms":
        return val / 1000.0  # convert ms -> seconds (normalize to seconds)

    # bytes
    if unit == "B":
        return val
    if unit.upper() == "KB":
        return val * 1024.0
    if unit.upper() == "MB":
        return val * 1024.0 * 1024.0

    # typical "kbps" is already a key, not a unit here
    return val


def parse_gwstat_line(line: str) -> Dict[str, float]:
    """
    Extract key=value tokens from a GWSTAT line.
    Returns numeric fields in:
      - up: seconds
      - avg_commit/max_commit: seconds (we'll convert to ms when writing CSV)
      - avg_payload: bytes
      - rx, db, kbps, qlen, qmax, batch: unitless numeric
    """
    # Keep only tokens that contain '='
    fields: Dict[str, float] = {}
    for tok in line.strip().split():
        if "=" not in tok:
            continue
        k, v = tok.split("=", 1)
        k = k.strip()
        v = v.strip().strip(",")
        parsed = parse_num_with_unit(v)
        if parsed is None:
            # Sometimes values may be like "200.0" followed by "msg/s" in next token (fine).
            # Or could be json-ish; ignore.
            continue
        fields[k] = parsed
    return fields


def infer_config_from_name(path: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Try to infer batch and rate from filename.
    Accepts patterns:
      b50_r200, batch50_rate200, b50-rate200, etc.
    Returns (batch, rate).
    """
    base = os.path.basename(path)

    batch = None
    rate = None

    # batch patterns
    m = re.search(r"(?:\b|_)(?:b|batch)(\d+)(?:\b|_)", base, re.IGNORECASE)
    if m:
        batch = int(m.group(1))

    # rate patterns
    m = re.search(r"(?:\b|_)(?:r|rate)(\d+)(?:\b|_)", base, re.IGNORECASE)
    if m:
        rate = int(m.group(1))

    return batch, rate


def run_id_from_name(path: str) -> str:
    """
    A stable-ish run_id derived from filename without extension.
    """
    base = os.path.basename(path)
    return os.path.splitext(base)[0]


# -------------------------
# Data structures
# -------------------------

@dataclass
class GwSample:
    run_id: str
    log_file: str
    up_s: float
    rx_msg_s: Optional[float]
    db_row_s: Optional[float]
    kbps: Optional[float]
    avg_payload_B: Optional[float]
    avg_commit_ms: Optional[float]
    max_commit_ms: Optional[float]
    qlen: Optional[float]
    qmax: Optional[float]
    batch: Optional[int]
    state_rate_hz: Optional[int]  # inferred


@dataclass
class DbStats:
    db_file: str
    rows: int
    file_bytes: int
    bytes_per_sample: Optional[float]


@dataclass
class RunSummary:
    run_id: str
    log_file: str
    db_file: Optional[str]
    batch: Optional[int]
    state_rate_hz: Optional[int]
    duration_s: Optional[float]
    mean_rx_msg_s: Optional[float]
    mean_db_row_s: Optional[float]
    mean_kbps: Optional[float]
    mean_payload_B: Optional[float]
    mean_commit_ms: Optional[float]
    max_commit_ms: Optional[float]
    max_qmax: Optional[float]
    db_rows: Optional[int]
    db_file_bytes: Optional[int]
    db_bytes_per_sample: Optional[float]


# -------------------------
# SQLite
# -------------------------

def read_db_stats(db_path: str) -> DbStats:
    rows = 0
    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM telemetry_state;")
        rows = int(cur.fetchone()[0])
        con.close()
    except Exception as e:
        print(f"[WARN] Failed reading DB rows from {db_path}: {e}")
        rows = 0

    file_bytes = int(os.path.getsize(db_path)) if os.path.exists(db_path) else 0
    bytes_per_sample = (file_bytes / rows) if rows > 0 else None
    return DbStats(db_file=db_path, rows=rows, file_bytes=file_bytes, bytes_per_sample=bytes_per_sample)


# -------------------------
# Matching log ↔ db
# -------------------------

def index_dbs(db_files: List[str]) -> Dict[Tuple[Optional[int], Optional[int], str], str]:
    """
    Build an index keyed by (batch, rate, run_id) and also by (batch, rate, stem variants).
    """
    idx: Dict[Tuple[Optional[int], Optional[int], str], str] = {}
    for db in db_files:
        rid = run_id_from_name(db)
        b, r = infer_config_from_name(db)
        idx[(b, r, rid)] = db
        # Also add a looser key: strip common prefixes
        rid2 = re.sub(r"^(run_|db_)", "", rid, flags=re.IGNORECASE)
        idx[(b, r, rid2)] = db
    return idx


def find_matching_db(log_path: str, db_index: Dict[Tuple[Optional[int], Optional[int], str], str]) -> Optional[str]:
    rid = run_id_from_name(log_path)
    b, r = infer_config_from_name(log_path)

    rid2 = re.sub(r"^(gw_|log_)", "", rid, flags=re.IGNORECASE)

    for key in [
        (b, r, rid),
        (b, r, rid2),
        (None, r, rid),
        (None, r, rid2),
        (b, None, rid),
        (b, None, rid2),
    ]:
        if key in db_index:
            return db_index[key]

    # Last resort: try by same stem substring match (weak)
    for (bb, rr, rrid), db in db_index.items():
        if rrid and (rrid in rid or rid in rrid):
            # If batch/rate are known, prefer consistent
            if b is not None and bb is not None and b != bb:
                continue
            if r is not None and rr is not None and r != rr:
                continue
            return db

    return None


# -------------------------
# Summarization
# -------------------------

def summarize_run(samples: List[GwSample], db_stats: Optional[DbStats]) -> RunSummary:
    if not samples:
        raise ValueError("No samples to summarize")

    # Decide "steady state" window: last 30 samples, or last 50% if shorter
    n = len(samples)
    win = 30 if n >= 30 else max(1, n // 2)
    steady = samples[-win:]

    def mean(vals: List[Optional[float]]) -> Optional[float]:
        v = [x for x in vals if x is not None]
        return (sum(v) / len(v)) if v else None

    def vmax(vals: List[Optional[float]]) -> Optional[float]:
        v = [x for x in vals if x is not None]
        return max(v) if v else None

    run_id = samples[0].run_id
    log_file = samples[0].log_file
    batch = samples[0].batch
    rate = samples[0].state_rate_hz

    duration_s = samples[-1].up_s if samples[-1].up_s is not None else None

    mean_rx = mean([s.rx_msg_s for s in steady])
    mean_db = mean([s.db_row_s for s in steady])
    mean_kbps = mean([s.kbps for s in steady])
    mean_payload = mean([s.avg_payload_B for s in steady])
    mean_commit = mean([s.avg_commit_ms for s in steady])
    max_commit = vmax([s.max_commit_ms for s in steady])
    max_qmax = vmax([s.qmax for s in steady])

    # If rate not inferred from name, infer from mean rx (rounded)
    inferred_rate = rate
    if inferred_rate is None and mean_rx is not None:
        inferred_rate = int(round(mean_rx))

    return RunSummary(
        run_id=run_id,
        log_file=log_file,
        db_file=db_stats.db_file if db_stats else None,
        batch=batch,
        state_rate_hz=inferred_rate,
        duration_s=duration_s,
        mean_rx_msg_s=mean_rx,
        mean_db_row_s=mean_db,
        mean_kbps=mean_kbps,
        mean_payload_B=mean_payload,
        mean_commit_ms=mean_commit,
        max_commit_ms=max_commit,
        max_qmax=max_qmax,
        db_rows=db_stats.rows if db_stats else None,
        db_file_bytes=db_stats.file_bytes if db_stats else None,
        db_bytes_per_sample=db_stats.bytes_per_sample if db_stats else None,
    )


# -------------------------
# Plotting
# -------------------------

def plot_fig3_throughput(summaries: List[RunSummary], outpath: str) -> None:
    """
    Fig.3: throughput vs publish rate, grouped by batch.
    Plots both rx and db on the same axes (lines).
    """
    # Filter only runs with rate and batch
    rows = [s for s in summaries if s.state_rate_hz is not None and s.batch is not None]
    if not rows:
        print("[WARN] Not enough data to plot Fig.3 (need state_rate_hz and batch).")
        return

    # group by batch
    batches = sorted(set(s.batch for s in rows if s.batch is not None))
    plt.figure()
    for b in batches:
        pts = [s for s in rows if s.batch == b]
        pts.sort(key=lambda x: x.state_rate_hz or 0)
        x = [p.state_rate_hz for p in pts]
        y_rx = [p.mean_rx_msg_s for p in pts]
        y_db = [p.mean_db_row_s for p in pts]
        # Plot rx and db as two lines per batch
        plt.plot(x, y_rx, marker="o", label=f"rx msg/s (batch={b})")
        plt.plot(x, y_db, marker="x", label=f"db row/s (batch={b})")

    plt.xlabel("Configured snapshot rate (Hz)")
    plt.ylabel("Throughput (per second)")
    plt.title("Fig. 3 — Gateway throughput vs snapshot publish rate")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(outpath, dpi=200)
    plt.close()


def plot_fig4_commit_box(summaries: List[RunSummary], samples_by_run: Dict[str, List[GwSample]], outpath: str) -> None:
    """
    Fig.4: commit time distribution (boxplot) by batch for the highest rate present.
    Uses per-sample avg_commit_ms values (steady or full run).
    """
    # pick max rate
    valid = [s for s in summaries if s.state_rate_hz is not None and s.batch is not None]
    if not valid:
        print("[WARN] Not enough data to plot Fig.4.")
        return
    max_rate = max(s.state_rate_hz for s in valid if s.state_rate_hz is not None)

    # collect commit_ms arrays per batch at max_rate
    batch_to_commits: Dict[int, List[float]] = {}
    for s in valid:
        if s.state_rate_hz != max_rate:
            continue
        arr = []
        for smp in samples_by_run.get(s.run_id, []):
            if smp.avg_commit_ms is not None:
                arr.append(float(smp.avg_commit_ms))
        if not arr:
            continue
        batch_to_commits.setdefault(int(s.batch), []).extend(arr)

    if not batch_to_commits:
        print("[WARN] No commit_ms samples available to plot Fig.4.")
        return

    batches = sorted(batch_to_commits.keys())
    data = [batch_to_commits[b] for b in batches]

    plt.figure()
    plt.boxplot(data, labels=[str(b) for b in batches], showfliers=True)
    plt.xlabel("SQLite batch size (rows/transaction)")
    plt.ylabel("Commit time (ms)")
    plt.title(f"Fig. 4 — SQLite commit time distribution at {max_rate} Hz")
    plt.grid(True, axis="y")
    plt.tight_layout()
    plt.savefig(outpath, dpi=200)
    plt.close()


def plot_fig5_storage(summaries: List[RunSummary], outpath: str) -> None:
    """
    Fig.5: bytes/sample vs rate grouped by batch.
    """
    rows = [s for s in summaries if s.state_rate_hz is not None and s.batch is not None and s.db_bytes_per_sample is not None]
    if not rows:
        print("[WARN] Not enough DB data to plot Fig.5 (need db_bytes_per_sample, rate, batch).")
        return

    batches = sorted(set(s.batch for s in rows if s.batch is not None))
    plt.figure()
    for b in batches:
        pts = [s for s in rows if s.batch == b]
        pts.sort(key=lambda x: x.state_rate_hz or 0)
        x = [p.state_rate_hz for p in pts]
        y = [p.db_bytes_per_sample for p in pts]
        plt.plot(x, y, marker="o", label=f"batch={b}")

    plt.xlabel("Configured snapshot rate (Hz)")
    plt.ylabel("DB bytes/sample")
    plt.title("Fig. 5 — Storage overhead (bytes per sample) vs publish rate")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(outpath, dpi=200)
    plt.close()


# -------------------------
# CSV writing
# -------------------------

def write_csv_samples(samples: List[GwSample], outpath: str) -> None:
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    with open(outpath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "run_id", "log_file",
            "up_s",
            "rx_msg_s", "db_row_s", "kbps",
            "avg_payload_B",
            "avg_commit_ms", "max_commit_ms",
            "qlen", "qmax",
            "batch",
            "state_rate_hz"
        ])
        for s in samples:
            w.writerow([
                s.run_id, s.log_file,
                f"{s.up_s:.6f}" if s.up_s is not None else "",
                s.rx_msg_s if s.rx_msg_s is not None else "",
                s.db_row_s if s.db_row_s is not None else "",
                s.kbps if s.kbps is not None else "",
                s.avg_payload_B if s.avg_payload_B is not None else "",
                s.avg_commit_ms if s.avg_commit_ms is not None else "",
                s.max_commit_ms if s.max_commit_ms is not None else "",
                s.qlen if s.qlen is not None else "",
                s.qmax if s.qmax is not None else "",
                s.batch if s.batch is not None else "",
                s.state_rate_hz if s.state_rate_hz is not None else "",
            ])


def write_csv_summaries(summaries: List[RunSummary], outpath: str) -> None:
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    with open(outpath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "run_id",
            "log_file",
            "db_file",
            "batch",
            "state_rate_hz",
            "duration_s",
            "mean_rx_msg_s",
            "mean_db_row_s",
            "mean_kbps",
            "mean_payload_B",
            "mean_commit_ms",
            "max_commit_ms",
            "max_qmax",
            "db_rows",
            "db_file_bytes",
            "db_bytes_per_sample",
        ])
        for s in summaries:
            w.writerow([
                s.run_id,
                s.log_file,
                s.db_file or "",
                s.batch if s.batch is not None else "",
                s.state_rate_hz if s.state_rate_hz is not None else "",
                s.duration_s if s.duration_s is not None else "",
                s.mean_rx_msg_s if s.mean_rx_msg_s is not None else "",
                s.mean_db_row_s if s.mean_db_row_s is not None else "",
                s.mean_kbps if s.mean_kbps is not None else "",
                s.mean_payload_B if s.mean_payload_B is not None else "",
                s.mean_commit_ms if s.mean_commit_ms is not None else "",
                s.max_commit_ms if s.max_commit_ms is not None else "",
                s.max_qmax if s.max_qmax is not None else "",
                s.db_rows if s.db_rows is not None else "",
                s.db_file_bytes if s.db_file_bytes is not None else "",
                s.db_bytes_per_sample if s.db_bytes_per_sample is not None else "",
            ])


# -------------------------
# Main
# -------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-glob", default="gw*.log", help='Glob for GWSTAT log files, e.g. "gw*.log"')
    ap.add_argument("--db-glob", default="run_*.db", help='Glob for SQLite DB files, e.g. "run_*.db"')
    ap.add_argument("--outdir", default="results", help="Output directory for CSV and plots")
    args = ap.parse_args()

    log_files = sorted(glob.glob(args.log_glob))
    db_files = sorted(glob.glob(args.db_glob))

    if not log_files:
        print(f"[ERROR] No log files matched: {args.log_glob}")
        print("Tip: run gateway with:  ./telemetry_gateway ... --stats 2> gw_b50_r200.log")
        return 2

    if not db_files:
        print(f"[WARN] No DB files matched: {args.db_glob} (plots Fig.5 will be skipped).")

    db_index = index_dbs(db_files)

    all_samples: List[GwSample] = []
    samples_by_run: Dict[str, List[GwSample]] = {}
    summaries: List[RunSummary] = []

    for lf in log_files:
        rid = run_id_from_name(lf)
        b_name, r_name = infer_config_from_name(lf)

        matched_db = find_matching_db(lf, db_index)
        db_stats = read_db_stats(matched_db) if matched_db else None

        samples: List[GwSample] = []
        with open(lf, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line.startswith("GWSTAT"):
                    continue
                fields = parse_gwstat_line(line)

                up_s = fields.get("up")
                if up_s is None:
                    # without up= it's hard to do steady-state; still accept
                    up_s = float(len(samples))

                rx = fields.get("rx")
                db = fields.get("db")
                kbps = fields.get("kbps")
                avg_payload_B = fields.get("avg_payload")

                # commit fields were parsed as seconds if 'ms' was present (we normalized to seconds)
                avg_commit_s = fields.get("avg_commit")
                max_commit_s = fields.get("max_commit")
                avg_commit_ms = (avg_commit_s * 1000.0) if avg_commit_s is not None else None
                max_commit_ms = (max_commit_s * 1000.0) if max_commit_s is not None else None

                qlen = fields.get("qlen")
                qmax = fields.get("qmax")

                batch_val = fields.get("batch")
                batch = int(batch_val) if batch_val is not None else b_name

                state_rate = r_name  # from filename, preferred
                # fallback if missing: later in summary we infer from mean rx

                smp = GwSample(
                    run_id=rid,
                    log_file=lf,
                    up_s=float(up_s),
                    rx_msg_s=float(rx) if rx is not None else None,
                    db_row_s=float(db) if db is not None else None,
                    kbps=float(kbps) if kbps is not None else None,
                    avg_payload_B=float(avg_payload_B) if avg_payload_B is not None else None,
                    avg_commit_ms=float(avg_commit_ms) if avg_commit_ms is not None else None,
                    max_commit_ms=float(max_commit_ms) if max_commit_ms is not None else None,
                    qlen=float(qlen) if qlen is not None else None,
                    qmax=float(qmax) if qmax is not None else None,
                    batch=batch,
                    state_rate_hz=state_rate,
                )
                samples.append(smp)

        if not samples:
            print(f"[WARN] No GWSTAT lines found in {lf}")
            continue

        samples_by_run[rid] = samples
        all_samples.extend(samples)

        # Summarize and attach DB stats
        summaries.append(summarize_run(samples, db_stats))

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    # CSVs
    write_csv_samples(all_samples, os.path.join(outdir, "gwstat_samples.csv"))
    write_csv_summaries(summaries, os.path.join(outdir, "runs_summary.csv"))

    # Figures
    plot_fig3_throughput(summaries, os.path.join(outdir, "fig3_throughput.png"))
    plot_fig4_commit_box(summaries, samples_by_run, os.path.join(outdir, "fig4_commit_box.png"))
    plot_fig5_storage(summaries, os.path.join(outdir, "fig5_storage.png"))

    print(f"[OK] Wrote outputs to: {outdir}/")
    print(f" - {outdir}/gwstat_samples.csv")
    print(f" - {outdir}/runs_summary.csv")
    print(f" - {outdir}/fig3_throughput.png")
    print(f" - {outdir}/fig4_commit_box.png")
    print(f" - {outdir}/fig5_storage.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())