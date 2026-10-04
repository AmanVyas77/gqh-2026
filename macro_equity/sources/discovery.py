"""Reproduce the Prompt 2 consensus-source coverage evidence (metadata only; no data values).

Queries the Internet Archive CDX API for captured report files and counts distinct report dates or
file versions per month or year. It never downloads report contents, so it opens no consensus,
actual-EPS or holdout values.

Usage (from the repository root):
  python -m macro_equity.sources.discovery            # writes data/manifests/coverage_evidence.json
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from macro_equity.paths import MANIFESTS

CDX = "https://web.archive.org/cdx/search/cdx"
FACTSET_OLD = "factset.com/websitefiles/PDFs/earningsinsight"
FACTSET_HUB = "advantage.factset.com/hubfs/Website/Resources%20Section/Research%20Desk/Earnings%20Insight/"
SPDJI_EPS_EST = [
    "www2.standardandpoors.com/spf/xls/index/SP500EPSEST.XLS",
    "us.spindices.com/documents/additional-material/sp-500-eps-est.xlsx",
    "www.spindices.com/documents/additional-material/sp-500-eps-est.xlsx",
    "www.spglobal.com/spdji/en/documents/additional-material/sp-500-eps-est.xlsx",
]
REFINITIV_SCORECARD = ["lipperalpha.financial.thomsonreuters.com/wp-content/uploads/",
                       "lipperalpha.refinitiv.com/wp-content/uploads/"]


def cdx(url: str, prefix: bool = False, pdf_only: bool = False, retries: int = 3) -> list[list[str]]:
    params = {"url": url, "output": "json", "fl": "timestamp,original,mimetype,digest",
              "filter": ["statuscode:200"], "limit": "50000"}
    if prefix:
        params["matchType"] = "prefix"
    if pdf_only:
        params["filter"].append("mimetype:application/pdf")
    for attempt in range(retries):
        try:
            r = requests.get(CDX, params=params, timeout=120)
            r.raise_for_status()
            rows = r.json()
            return rows[1:] if rows else []
        except (requests.RequestException, ValueError):
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"CDX query failed: {url}")


def _date_from_factset_name(url: str) -> dt.date | None:
    m = re.search(r"earningsinsight_?(\d{1,2})\.(\d{1,2})\.(\d{2,4})", url, re.I)
    if m:
        mo, d, y = map(int, m.groups())
        y = y + 2000 if y < 100 else y
    else:
        m = re.search(r"EarningsInsight_(\d{2})(\d{2})(\d{2})[A-Z]?\.pdf", url)
        if not m:
            return None
        mo, d, y = int(m.group(1)), int(m.group(2)), 2000 + int(m.group(3))
    try:
        return dt.date(y, mo, d)
    except ValueError:
        return None


def factset_report_dates() -> dict:
    """Distinct FactSet Earnings Insight report dates with a captured PDF, by month."""
    dates = set()
    for url, prefix in ((FACTSET_OLD, True), (FACTSET_HUB, True)):
        for ts, original, mime, _ in cdx(url, prefix=prefix):
            d = _date_from_factset_name(original)
            if d and "pdf" in mime:
                dates.add(d)
    ds = sorted(dates)
    by_month = collections.Counter(f"{d:%Y-%m}" for d in ds)
    return {"n_report_dates": len(ds), "first": str(ds[0]) if ds else None,
            "by_month": dict(sorted(by_month.items()))}


def spdji_versions() -> dict:
    out = {}
    for u in SPDJI_EPS_EST:
        first_seen = {}
        for ts, _, _, digest in cdx(u):
            first_seen.setdefault(digest, ts)
        years = collections.Counter(ts[:4] for ts in first_seen.values())
        out[u] = {"distinct_versions": len(first_seen), "by_year": dict(sorted(years.items()))}
    return out


def refinitiv_scorecards() -> dict:
    out = {}
    for u in REFINITIV_SCORECARD:
        rows = cdx(u, prefix=True, pdf_only=True)
        names = {r[1].split("://")[-1].replace("www.", "") for r in rows if re.search(r"TRPR", r[1])}
        years = collections.Counter(m.group(1) for n in names if (m := re.search(r"/uploads/(\d{4})/", n)))
        out[u] = {"distinct_scorecard_pdfs": len(names), "by_upload_year": dict(sorted(years.items()))}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(MANIFESTS / "coverage_evidence.json"))
    args = ap.parse_args()
    evidence = {
        "generated_et": datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds"),
        "method": "Internet Archive CDX metadata (capture timestamps, URLs, MIME types, digests); no file contents read",
        "factset_earnings_insight": factset_report_dates(),
        "spdji_sp500_eps_est_xlsx": spdji_versions(),
        "refinitiv_sp500_earnings_scorecard": refinitiv_scorecards(),
    }
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(evidence, f, indent=2)
    fs = evidence["factset_earnings_insight"]
    print(f"FactSet Earnings Insight: {fs['n_report_dates']} report dates with a PDF capture from {fs['first']}")
    print(f"written: {args.out}")


if __name__ == "__main__":
    main()
