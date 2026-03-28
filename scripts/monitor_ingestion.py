"""Live TUI monitor for background ingestion jobs on the deployed API."""

import argparse
import json
import os
import shutil
import sys
import time
import urllib.request

# Target total from ClinicalTrials.gov
TARGET_TOTAL = 578_109

# ANSI colors
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
BLUE = "\033[34m"
WHITE = "\033[37m"
BG_GREEN = "\033[42m"
BG_GRAY = "\033[100m"

STATUS_COLORS = {
    "running": YELLOW,
    "complete": GREEN,
    "failed": RED,
    "queued": DIM,
}

STATUS_ICONS = {
    "running": "▶",
    "complete": "✓",
    "failed": "✗",
    "queued": "◦",
}

# Expected trials per shard (from CT.gov API counts)
SHARD_EXPECTED = {
    "1999-2005": 24_821,
    "2006-2009": 58_037,
    "2010-2012": 54_621,
    "2013-2015": 67_840,
    "2016-2017": 56_960,
    "2018-2019": 63_454,
    "2020-2020": 36_720,
    "2021-2021": 37_013,
    "2022-2022": 38_022,
    "2023-2023": 39_704,
    "2024-2024": 43_671,
    "2025-2026": 57_246,
}


def fetch_status(base_url: str) -> dict | None:
    try:
        req = urllib.request.Request(f"{base_url}/ingest/status")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def progress_bar(current: int, total: int, width: int = 30) -> str:
    if total == 0:
        return f"{BG_GRAY}{' ' * width}{RESET}"
    pct = min(current / total, 1.0)
    filled = int(width * pct)
    empty = width - filled
    bar = f"{BG_GREEN}{' ' * filled}{RESET}{BG_GRAY}{' ' * empty}{RESET}"
    return bar


def extract_shard_label(job_id: str) -> str:
    """Extract '2020-2020' from 'ingest-2020-2020-1774695146'."""
    parts = job_id.split("-")
    if len(parts) >= 4:
        return f"{parts[1]}-{parts[2]}"
    return job_id


def render(data: dict, elapsed: float) -> str:
    cols = shutil.get_terminal_size().columns
    lines = []

    db_total = data.get("db_total", 0)
    jobs = data.get("jobs", [])

    # Header
    lines.append("")
    lines.append(f"  {BOLD}{CYAN}Clinical Trials Ingestion Monitor{RESET}")
    lines.append(f"  {DIM}{'─' * min(50, cols - 4)}{RESET}")

    # Overall progress
    pct = (db_total / TARGET_TOTAL * 100) if TARGET_TOTAL else 0
    bar = progress_bar(db_total, TARGET_TOTAL, width=40)
    lines.append("")
    lines.append(f"  {BOLD}Database:{RESET}  {db_total:>9,} / {TARGET_TOTAL:,}  ({pct:.1f}%)")
    lines.append(f"  {bar}")

    # Job summary
    running = sum(1 for j in jobs if j["status"] == "running")
    complete = sum(1 for j in jobs if j["status"] == "complete")
    queued = sum(1 for j in jobs if j["status"] == "queued")
    failed = sum(1 for j in jobs if j["status"] == "failed")
    total_loaded = sum(j["loaded"] for j in jobs)

    lines.append("")
    lines.append(f"  {BOLD}Jobs:{RESET}      {YELLOW}▶ {running} running{RESET}  "
                 f"{GREEN}✓ {complete} done{RESET}  "
                 f"{DIM}◦ {queued} queued{RESET}  "
                 f"{RED}{'✗ ' + str(failed) + ' failed' if failed else ''}{RESET}")
    lines.append(f"  {BOLD}Loaded:{RESET}   {total_loaded:>9,} across all jobs")

    # Per-shard detail
    lines.append("")
    lines.append(f"  {BOLD}{'Shard':<14} {'Status':<10} {'Pages':>6}  {'Loaded':>9}  {'Progress'}{RESET}")
    lines.append(f"  {DIM}{'─' * min(70, cols - 4)}{RESET}")

    for j in jobs:
        label = extract_shard_label(j["job_id"])
        st = j["status"]
        color = STATUS_COLORS.get(st, RESET)
        icon = STATUS_ICONS.get(st, "?")
        pages = j["pages_fetched"]
        loaded = j["loaded"]
        expected = SHARD_EXPECTED.get(label, 0)

        bar = progress_bar(loaded, expected, width=20)
        pct_str = f"{loaded / expected * 100:.0f}%" if expected else "—"

        err_str = ""
        if j.get("load_errors", 0) > 0 or j.get("parse_errors", 0) > 0:
            err_str = f"  {RED}({j['parse_errors']}p/{j['load_errors']}l err){RESET}"

        lines.append(
            f"  {color}{icon} {label:<12}{RESET} {color}{st:<10}{RESET} "
            f"{pages:>5}p  {loaded:>9,}  {bar} {pct_str}{err_str}"
        )

    # Footer
    mins, secs = divmod(int(elapsed), 60)
    lines.append("")
    lines.append(f"  {DIM}Elapsed: {mins}m {secs:02d}s  |  Refreshing every 5s  |  Ctrl+C to exit{RESET}")
    lines.append("")

    return "\n".join(lines)


def main(base_url: str) -> None:
    start = time.time()
    print(f"\033[2J\033[H", end="")  # Clear screen

    while True:
        data = fetch_status(base_url)
        elapsed = time.time() - start

        # Move cursor to top
        print(f"\033[H", end="")

        if data is None:
            print(f"\n  {RED}Cannot reach {base_url}/ingest/status{RESET}\n")
            print(f"  {DIM}Retrying in 5s...{RESET}")
        else:
            output = render(data, elapsed)
            # Clear screen and print (avoids flicker)
            term_height = shutil.get_terminal_size().lines
            output_lines = output.split("\n")
            # Pad with empty lines to clear old content
            while len(output_lines) < term_height:
                output_lines.append(" " * shutil.get_terminal_size().columns)
            print("\n".join(output_lines[:term_height]))

            # Check if all done
            jobs = data.get("jobs", [])
            if jobs and all(j["status"] in ("complete", "failed") for j in jobs):
                db_total = data.get("db_total", 0)
                print(f"\n  {BOLD}{GREEN}All jobs finished! DB total: {db_total:,}{RESET}\n")
                break

        time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor ingestion progress")
    parser.add_argument(
        "--url",
        default="https://clinical-trials-api-meoh.onrender.com",
        help="Base URL of the deployed API",
    )
    args = parser.parse_args()

    try:
        main(args.url)
    except KeyboardInterrupt:
        print(f"\n\033[0m  Stopped.\n")
