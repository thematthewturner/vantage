"""Phase 0.5: Curated public-company financials seed loader.

Reads a structured `FINDINGS` dict in this file (numbers gathered manually from
SEC EDGAR 8-K/10-K filings and investor-relations press releases), and writes:
- dbt_vantage/seeds/dim_source_seed.csv  (appended, idempotent by source_id)
- dbt_vantage/seeds/fact_financials_seed.csv
- dbt_vantage/seeds/fact_valuation_seed.csv
- dbt_vantage/seeds/fact_covered_lives_seed.csv

Money is USD MILLIONS, DECIMAL. Provenance is the source URL (one row per URL
in dim_source). Re-running this script is a no-op (overwrites with same content).

Run from repo root: python3 scripts/load_curated_financials.py
"""

from __future__ import annotations

import csv
import hashlib
import re
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEEDS = REPO_ROOT / "dbt_vantage" / "seeds"
RETRIEVED_AT = "2026-06-06 18:00:00"

# Each entry: company_id -> list of records.
# Record types:
#   ("FY", period, period_end, revenue, gross_margin, opex, adj_ebitda,
#     net_income, free_cash_flow, cash_and_sti, url)
#   ("Q",  period, period_end, revenue, gross_margin, opex, adj_ebitda,
#     net_income, free_cash_flow, cash_and_sti, url)
#   ("MKTCAP", as_of_date, valuation_usd, price_per_share, url)
#   ("LIVES",  fiscal_period, life_type, lives_count, url)
# Use None for unknowns. Currency in USD millions.

FINDINGS: dict[str, list[tuple]] = {
    # ---- Omada Health: IPO'd June 2025; treat as public going forward.
    "omada": [
        ("FY", "2025FY", "2025-12-31", 260.21, None, None, None, None, None, None,
         "https://stockanalysis.com/stocks/omda/"),
        ("Q", "2026Q1", "2026-03-31", 78.0, None, None, None, -3.0, None, None,
         "https://www.mobihealthnews.com/news/omada-health-reports-42-revenue-growth-q1-2026-earnings"),
    ],
    "hims_hers": [
        ("FY", "2025FY", "2025-12-31", 2350.0, None, None, 318.0, 128.4, None, None,
         "https://investors.hims.com/news/news-details/2026/Hims--Hers-Health-Inc--Reports-Fourth-Quarter-and-Full-Year-2025-Financial-Results/default.aspx"),
        ("Q", "2026Q1", "2026-03-31", 608.0, 0.65, None, 44.3, -92.1, None, None,
         "https://investors.hims.com/news/news-details/2026/Hims--Hers-Health-Inc--Reports-First-Quarter-2026-Financial-Results/default.aspx"),
        ("LIVES", "2026Q1", "subscriber", 2_600_000,
         "https://investors.hims.com/news/news-details/2026/Hims--Hers-Health-Inc--Reports-First-Quarter-2026-Financial-Results/default.aspx"),
    ],
    "teladoc": [
        ("FY", "2025FY", "2025-12-31", 2530.0, None, None, 281.1, None, None, None,
         "https://www.sec.gov/Archives/edgar/data/0001477449/000147744926000010/tdoc-20251231xexx991.htm"),
        ("Q", "2026Q1", "2026-03-31", 613.8, None, None, 58.2, -63.8, None, None,
         "https://www.sec.gov/Archives/edgar/data/0001477449/000147744926000026/tdoc-20260331xexx991.htm"),
    ],
    "hinge_health": [
        # FY2025: revenue $587.9M (+51% YoY), GAAP gross margin 80%, non-GAAP op
        # income $119.5M (used as adj EBITDA proxy; Hinge does not publish a
        # separate adj EBITDA line). GAAP net loss large due to IPO-related SBC.
        ("FY", "2025FY", "2025-12-31", 587.9, 0.80, None, 119.5, -546.4, 179.6, None,
         "https://ir.hingehealth.com/news/news-details/2026/Hinge-Health-reports-fourth-quarter-and-full-year-2025-financial-results/default.aspx"),
        ("Q", "2026Q1", "2026-03-31", 182.3, 0.85, None, 46.2, None, 41.6, None,
         "https://www.businesswire.com/news/home/20260505775006/en/Hinge-Health-reports-record-first-quarter-2026-financial-results"),
    ],
    "oscar_health": [
        ("FY", "2025FY", "2025-12-31", 11700.0, None, None, None, -443.2, None, None,
         "https://ir.hioscar.com/news-events-presentations/news-press-releases/news-details/2026/Oscar-Health-Announces-Financial-Results-for-Fourth-Quarter-and-Full-Year-2025/default.aspx"),
        ("Q", "2026Q1", "2026-03-31", 4600.0, None, None, 727.1, 679.0, None, None,
         "https://www.stocktitan.net/sec-filings/OSCR/8-k-oscar-health-inc-reports-material-event-9ec1cfa1c1e3.html"),
        ("LIVES", "2025FY", "enrolled", 2_000_000,
         "https://ir.hioscar.com/news-events-presentations/news-press-releases/news-details/2026/Oscar-Health-Announces-Financial-Results-for-Fourth-Quarter-and-Full-Year-2025/default.aspx"),
        ("LIVES", "2026Q1", "enrolled", 3_170_000,
         "https://www.stocktitan.net/sec-filings/OSCR/8-k-oscar-health-inc-reports-material-event-9ec1cfa1c1e3.html"),
    ],
    "privia_health": [
        ("FY", "2025FY", "2025-12-31", 2120.0, None, None, 125.5, None, None, None,
         "https://ir.priviahealth.com/news-releases/news-release-details/privia-health-reports-fourth-quarter-and-full-year-2025/"),
        ("Q", "2026Q1", "2026-03-31", 603.85, None, None, 36.7, None, None, None,
         "https://www.stocktitan.net/news/PRVA/privia-health-reports-first-quarter-2026-financial-n4g05iyy1vb0.html"),
        ("LIVES", "2026Q1", "attributed", 1_606_000,
         "https://www.stocktitan.net/news/PRVA/privia-health-reports-first-quarter-2026-financial-n4g05iyy1vb0.html"),
    ],
    "doximity": [
        # Doximity's fiscal year ends March 31. FY2026 = year ended 2026-03-31.
        ("FY", "2026FY", "2026-03-31", 644.9, None, None, 354.7, None, 317.5, None,
         "https://investors.doximity.com/news/news-details/2026/Doximity-Announces-Fourth-Quarter-and-Fiscal-Year-2026-Financial-Results/default.aspx"),
        ("Q", "2026Q4", "2026-03-31", 145.0, None, None, 65.25, None, 107.0, None,
         "https://investors.doximity.com/news/news-details/2026/Doximity-Announces-Fourth-Quarter-and-Fiscal-Year-2026-Financial-Results/default.aspx"),
    ],
    "evolent": [
        ("FY", "2025FY", "2025-12-31", 1876.0, None, None, 151.2, None, None, None,
         "https://www.prnewswire.com/news-releases/evolent-announces-fourth-quarter-2025-results-and-full-year-2025-results-302696180.html"),
        ("Q", "2026Q1", "2026-03-31", 496.0, None, None, 22.0, None, None, None,
         "https://www.stocktitan.net/sec-filings/EVH/8-k-evolent-health-inc-reports-material-event"),
    ],
    "progyny": [
        ("FY", "2025FY", "2025-12-31", 1288.7, 0.236, None, 222.1, 58.5, None, 310.1,
         "https://investors.progyny.com/news-releases/news-release-details/progyny-inc-announces-fourth-quarter-2025-results"),
        ("Q", "2026Q1", "2026-03-31", 328.5, 0.253, None, 56.6, 24.2, None, None,
         "https://www.stocktitan.net/news/PGNY/progyny-inc-announces-first-quarter-2026-9ka6crkv28ye.html"),
        ("LIVES", "2026Q1", "eligible", 7_185_000,
         "https://www.stocktitan.net/news/PGNY/progyny-inc-announces-first-quarter-2026-9ka6crkv28ye.html"),
    ],
    "agilon": [
        # FY2025: revenue $5.93B (-2% YoY), adj EBITDA loss $296M, medical margin -$57M
        ("FY", "2025FY", "2025-12-31", 5930.0, None, None, -296.0, None, None, None,
         "https://investors.agilonhealth.com/news/news-details/2026/agilon-health-Reports-Fourth-Quarter-and-Full-Year-Fiscal-2025-Results/default.aspx"),
        ("Q", "2026Q1", "2026-03-31", 1420.0, None, None, None, None, None, None,
         "https://www.stocktitan.net/sec-filings/AGL/8-k-agilon-health-inc-reports-material-event-7c5d80a0fc71.html"),
        ("LIVES", "2026Q1", "at_risk", 426_000,
         "https://www.stocktitan.net/sec-filings/AGL/8-k-agilon-health-inc-reports-material-event-7c5d80a0fc71.html"),
    ],
    "health_catalyst": [
        ("FY", "2025FY", "2025-12-31", 311.1, None, None, 41.4, None, None, None,
         "https://www.globenewswire.com/news-release/2026/03/12/3255113/0/en/Health-Catalyst-Reports-Fourth-Quarter-and-Year-End-2025-Results.html"),
        ("Q", "2026Q1", "2026-03-31", 70.8, None, None, 9.1, None, None, None,
         "https://www.stocktitan.net/news/HCAT/health-catalyst-reports-first-quarter-2026-ytqywwf85a6y.html"),
    ],
    "phreesia": [
        # Phreesia fiscal year ends January 31. FY2026 = ended 2026-01-31.
        ("FY", "2026FY", "2026-01-31", 480.6, None, None, 101.5, 2.3, 50.0, None,
         "https://www.sec.gov/Archives/edgar/data/1412408/000141240826000074/phr-ex991q4fy26.htm"),
        ("Q", "2026Q4", "2026-01-31", 127.1, None, None, 29.4, None, None, None,
         "https://www.sec.gov/Archives/edgar/data/1412408/000141240826000074/phr-ex991q4fy26.htm"),
    ],
    "definitive_healthcare": [
        ("FY", "2025FY", "2025-12-31", 241.5, None, None, 70.4, None, None, None,
         "https://www.sec.gov/Archives/edgar/data/0001861795/000119312526076609/dh-ex99_1.htm"),
        ("Q", "2026Q1", "2026-03-31", 55.9, None, None, 15.3, None, None, None,
         "https://www.sec.gov/Archives/edgar/data/0001861795/000119312526211946/dh-ex99_1.htm"),
    ],
    "recursion": [
        ("FY", "2025FY", "2025-12-31", 74.7, None, None, None, -644.8, None, 753.9,
         "https://ir.recursion.com/news-releases/news-release-details/recursion-reports-fourth-quarter-and-full-year-2025-financial"),
        ("Q", "2026Q1", "2026-03-31", 6.5, None, None, None, -117.5, None, 665.2,
         "https://www.stocktitan.net/sec-filings/RXRX/8-k-recursion-pharmaceuticals-inc-reports-material-event-a90f55f5e2e5.html"),
    ],
    "schrodinger": [
        ("FY", "2025FY", "2025-12-31", 255.9, None, None, None, -103.3, None, None,
         "https://simplywall.st/stocks/us/healthcare/nasdaq-sdgr/schrodinger/past"),
        ("Q", "2026Q1", "2026-03-31", 58.6, None, None, None, -60.0, None, None,
         "https://www.stocktitan.net/sec-filings/SDGR/8-k-schrodinger-inc-reports-material-event-a2ba975da8ab.html"),
    ],
    "amwell": [
        ("FY", "2025FY", "2025-12-31", 249.3, None, None, -39.9, -95.0, None, 179.0,
         "https://investors.amwell.com/static-files/026f461c-5dcd-4415-beaf-80fee1c7d367"),
        ("Q", "2026Q1", "2026-03-31", 54.9, None, None, -3.1, None, None, 179.0,
         "https://investors.amwell.com/static-files/d5ad6b5f-0742-4969-b270-9f90584dc2e2"),
    ],
    "talkspace": [
        ("FY", "2025FY", "2025-12-31", 228.9, None, None, 15.8, 7.8, None, None,
         "https://www.sec.gov/Archives/edgar/data/0001803901/000095017025063986/talk-ex99_1.htm"),
        ("Q", "2026Q1", "2026-03-31", 61.7, None, None, None, -6.31, None, None,
         "https://www.sec.gov/Archives/edgar/data/0001803901/000119312526058146/talk-ex99_1.htm"),
    ],
    "lifestance": [
        ("FY", "2025FY", "2025-12-31", 1424.3, None, None, 157.7, 9.7, None, None,
         "https://www.sec.gov/Archives/edgar/data/0001845257/000095017025064745/lfst-ex99_1.htm"),
        ("Q", "2026Q1", "2026-03-31", 403.5, None, None, 51.1, 14.2, None, None,
         "https://www.sec.gov/Archives/edgar/data/0001845257/000119312526067858/lfst-ex99_1.htm"),
    ],
    "tempus_ai": [
        ("FY", "2025FY", "2025-12-31", 1265.0, None, None, -7.4, -245.0, None, None,
         "https://investors.tempus.com/news-releases/news-release-details/tempus-reports-fourth-quarter-and-full-year-2025-results"),
        ("Q", "2026Q1", "2026-03-31", 348.1, None, None, None, None, None, 643.8,
         "https://www.sec.gov/Archives/edgar/data/0001717115/000119312526206317/tem-ex99_1.htm"),
    ],
    "waystar": [
        ("FY", "2025FY", "2025-12-31", 1099.3, None, None, 462.1, 112.1, 365.0, None,
         "https://www.prnewswire.com/news-releases/waystar-reports-fourth-quarter-and-fiscal-year-2025-results-provides-2026-guidance-302689036.html"),
        ("Q", "2026Q1", "2026-03-31", 313.9, None, None, 135.4, 43.3, None, None,
         "https://www.sec.gov/Archives/edgar/data/0001990354/000199035426000024/way042926-8xkex991.htm"),
    ],
    "goodrx": [
        ("FY", "2025FY", "2025-12-31", 796.9, None, None, 270.5, 30.4, None, None,
         "https://www.sec.gov/Archives/edgar/data/0001809519/000180951926000028/gdrxq425-exx991pressrelease.htm"),
        ("Q", "2026Q1", "2026-03-31", 194.0, None, None, 58.3, 1.2, None, None,
         "https://www.sec.gov/Archives/edgar/data/0001809519/000180951926000110/gdrxq126-exx991pressrelease.htm"),
        ("LIVES", "2026Q1", "subscriber", 5_300_000,
         "https://www.sec.gov/Archives/edgar/data/0001809519/000180951926000110/gdrxq126-exx991pressrelease.htm"),
    ],
    "clover": [
        ("Q", "2026Q1", "2026-03-31", 749.2, None, None, 40.3, 27.3, None, None,
         "https://www.sec.gov/Archives/edgar/data/0001801170/000180117026000114/a1q26exx991xearningsrelease.htm"),
        ("LIVES", "2026Q1", "enrolled", 155_773,
         "https://www.sec.gov/Archives/edgar/data/0001801170/000180117026000114/a1q26exx991xearningsrelease.htm"),
    ],
    "astrana": [
        ("FY", "2025FY", "2025-12-31", 3180.0, None, None, 205.4, None, 104.5, None,
         "https://www.stocktitan.net/sec-filings/ASTH/8-k-astrana-health-inc-reports-material-event-15a932a72348.html"),
        ("Q", "2026Q1", "2026-03-31", 965.1, None, None, None, 14.4, None, 478.4,
         "https://www.stocktitan.net/sec-filings/ASTH/8-k-astrana-health-inc-reports-material-event-dc1904d79340.html"),
        ("LIVES", "2025FY", "attributed", 1_600_000,
         "https://www.stocktitan.net/sec-filings/ASTH/8-k-astrana-health-inc-reports-material-event-15a932a72348.html"),
    ],
}


def url_to_source_id(url: str) -> tuple[str, str]:
    """Return (source_id, source_type) for a URL. Deterministic, short, and human-readable."""
    h = hashlib.sha1(url.encode()).hexdigest()[:8]
    if "sec.gov" in url:
        if "10-Q" in url.upper() or "10q" in url.lower() or "10-q" in url:
            t = "10-Q"
        elif "10-K" in url.upper() or "10k" in url.lower() or "10-k" in url:
            t = "10-K"
        elif "8-K" in url.upper() or "8xk" in url.lower() or "exx991" in url.lower() or "ex99_1" in url.lower():
            t = "8-K"
        elif "S-1" in url.upper() or "s1" in url.lower():
            t = "S-1"
        else:
            t = "8-K"  # default for EDGAR exhibits
        return f"src_sec_{h}", t
    return f"src_press_{h}", "press"


def url_reliability(url: str) -> str:
    """SEC filings + company IR pages = primary; trade press summaries = secondary."""
    if "sec.gov" in url or "investors." in url or "investor." in url or "businesswire" in url or ".com/news/news-details" in url:
        return "primary"
    return "secondary"


def merge_sources(urls: set[str]) -> dict[str, dict]:
    """Return source_id -> dict for unique URLs."""
    out: dict[str, dict] = {}
    for u in urls:
        sid, stype = url_to_source_id(u)
        if sid not in out:
            out[sid] = {
                "source_id": sid,
                "source_type": stype,
                "url": u,
                "retrieved_at": RETRIEVED_AT,
                "reliability": url_reliability(u),
            }
    return out


def main() -> None:
    # Collect all unique URLs across all findings.
    urls: set[str] = set()
    for recs in FINDINGS.values():
        for r in recs:
            url = r[-1]
            urls.add(url)

    sources = merge_sources(urls)
    src_for = {row["url"]: row["source_id"] for row in sources.values()}

    # ----- dim_source_seed: union of existing rows + new -----
    existing: list[dict] = []
    src_path = SEEDS / "dim_source_seed.csv"
    if src_path.exists():
        with src_path.open() as f:
            for r in csv.DictReader(f):
                existing.append(r)
    existing_ids = {r["source_id"] for r in existing}
    new_sources = [s for sid, s in sources.items() if sid not in existing_ids]
    final_sources = existing + new_sources
    with src_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source_id", "source_type", "url", "retrieved_at", "reliability"])
        w.writeheader()
        for r in final_sources:
            w.writerow(r)

    # ----- fact_financials_seed -----
    fin_rows: list[dict] = []
    for cid, recs in FINDINGS.items():
        for r in recs:
            if r[0] in ("FY", "Q"):
                kind, period, end, rev, gm, opex, eb, ni, fcf, cash, url = r
                fin_rows.append({
                    "company_id": cid,
                    "fiscal_period": period,
                    "period_end": end,
                    "is_guidance": "false",
                    "revenue": rev if rev is not None else "",
                    "gross_profit": "",
                    "gross_margin": gm if gm is not None else "",
                    "opex": opex if opex is not None else "",
                    "adj_ebitda": eb if eb is not None else "",
                    "net_income": ni if ni is not None else "",
                    "free_cash_flow": fcf if fcf is not None else "",
                    "cash_and_sti": cash if cash is not None else "",
                    "source_id": src_for[url],
                })
    with (SEEDS / "fact_financials_seed.csv").open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "company_id", "fiscal_period", "period_end", "is_guidance",
                "revenue", "gross_profit", "gross_margin", "opex", "adj_ebitda",
                "net_income", "free_cash_flow", "cash_and_sti", "source_id",
            ],
        )
        w.writeheader()
        for r in fin_rows:
            w.writerow(r)

    # ----- fact_covered_lives_seed -----
    lives_rows: list[dict] = []
    for cid, recs in FINDINGS.items():
        for r in recs:
            if r[0] == "LIVES":
                _, period, life_type, count, url = r
                lives_rows.append({
                    "company_id": cid,
                    "fiscal_period": period,
                    "life_type": life_type,
                    "lives_count": count,
                    "source_id": src_for[url],
                })
    with (SEEDS / "fact_covered_lives_seed.csv").open("w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["company_id", "fiscal_period", "life_type", "lives_count", "source_id"]
        )
        w.writeheader()
        for r in lives_rows:
            w.writerow(r)

    print(f"Wrote {len(final_sources)} sources, {len(fin_rows)} financial rows, {len(lives_rows)} lives rows")


if __name__ == "__main__":
    main()
