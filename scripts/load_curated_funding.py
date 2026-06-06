"""Phase 0.5b: Curated private-company funding + Omada post-IPO updates.

Appends to:
- dbt_vantage/seeds/dim_source_seed.csv (new sources only)
- dbt_vantage/seeds/fact_funding_round_seed.csv
- dbt_vantage/seeds/fact_valuation_seed.csv
- dbt_vantage/seeds/fact_financials_seed.csv (Omada post-IPO actuals)
- dbt_vantage/seeds/fact_covered_lives_seed.csv (private lives count)

Also rewrites dbt_vantage/seeds/dim_company_seed.csv to flip Omada Health's
status from 'private' to 'public' and add ticker OMDA / exchange NASDAQ.

USD millions, DECIMAL. Run from repo root: python3 scripts/load_curated_funding.py
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEEDS = REPO_ROOT / "dbt_vantage" / "seeds"
RETRIEVED_AT = "2026-06-06 18:00:00"


# Funding rounds: company_id -> list[(announced_date, round_type, amount_usd,
# post_money_valuation, lead_investors_semicolon, source_url)]
ROUNDS: dict[str, list[tuple]] = {
    "aledade": [
        ("2023-06-21", "series_f", 260.0, 3500.0, "Lightspeed Venture Partners",
         "https://aledade.com/newsroom/aledade-news/aledade-secures-series-f/"),
        ("2025-12-01", "debt", 500.0, None, "",
         "https://www.cbinsights.com/company/aledade/financials"),
    ],
    "devoted_health": [
        ("2025-10-16", "series_e", 300.0, 12600.0, "Andreessen Horowitz;Uprising;SoftBank",
         "https://www.insurtechinsights.com/insurtech-devoted-health-raises-us175-million-in-series-e-round/"),
    ],
    "cityblock": [
        # The 2024 $400M Series E was reported at $5.7B by Fierce; CBInsights
        # carries $6.3B from a later mark. Use the announced post-money ($5.7B)
        # and tag the CBI mark separately as secondary_mkt in fact_valuation.
        ("2024-09-01", "series_e", 400.0, 5700.0, "",
         "https://www.fiercehealthcare.com/practices/cityblock-health-raises-another-mega-round-cash-banking-a-reported-400m"),
    ],
    "maven": [
        ("2024-10-08", "series_f", 125.0, 1700.0, "StepStone Group",
         "https://www.prnewswire.com/news-releases/maven-clinic-announces-125-million-series-f-round-of-funding-to-chart-the-next-decade-of-innovation-in-womens-and-family-health-302269566.html"),
    ],
    "headway": [
        ("2024-07-01", "series_d", 100.0, 2300.0, "Spark Capital",
         "https://www.prnewswire.com/news-releases/headway-raises-100-million-in-series-d-funding-plans-expansion-to-serve-people-with-medicare-advantage-and-medicaid-insurance-coverage-302203630.html"),
        ("2023-10-01", "series_c", 125.0, None, "Spark Capital",
         "https://www.mobihealthnews.com/news/headway-scores-100m-more-doubling-its-valuation-23b"),
    ],
    "spring_health": [
        ("2024-07-31", "series_e", 100.0, 3300.0, "Generation Investment Management",
         "https://www.springhealth.com/news/series-e-funding-accelerate-growth-expand-global-access"),
    ],
    "lyra": [
        ("2022-01-19", "series_f", 235.0, 5580.0, "Dragoneer",
         "https://www.lyrahealth.com/announcement/lyra-health-completes-235m-funding-round-led-by-dragoneer-to-fuel-international-expansion/"),
    ],
    "ro": [
        ("2022-02-01", "series_d", 150.0, 7000.0, "ShawSpring Partners",
         "https://en.wikipedia.org/wiki/Ro_(company)"),
    ],
    "talkiatry": [
        ("2024-06-18", "series_c", 130.0, None, "Andreessen Horowitz;Perceptive Advisors",
         "https://www.prnewswire.com/news-releases/talkiatry-secures-130m-series-c-funding-to-mainstream-value-based-behavioral-health-care-302175461.html"),
        ("2026-02-12", "series_d", 210.0, None, "Andreessen Horowitz",
         "https://bhbusiness.com/2026/02/12/talkiatry-raises-210m-to-expand-digital-ai-powered-psychiatry-practice/"),
    ],
    "color": [
        ("2021-11-01", "series_e", 100.0, 4600.0, "General Catalyst;T. Rowe Price",
         "https://www.fiercebiotech.com/medtech/color-triples-valuation-100m-funding-to-expand-population-level-testing-and-treatment"),
    ],
    "omada": [
        # IPO June 5 2025: $19/share, raised $150M. Tag as public_mktcap valuation event.
        ("2025-06-05", "growth", 150.0, None, "Morgan Stanley;Goldman Sachs;J.P. Morgan",
         "https://stockanalysis.com/stocks/omda/"),
    ],
}


# Independent valuation marks (where the announced post-money differs from a
# later observed/marked price). One row per (company, as_of_date, method).
VAL_MARKS: list[tuple] = [
    # company_id, as_of_date, valuation_usd, price_per_share, method, source_url
    ("cityblock", "2025-01-01", 6300.0, None, "secondary_npm",
     "https://www.cbinsights.com/company/cityblock-health/financials"),
    ("ro", "2024-12-31", 7000.0, None, "secondary_npm",
     "https://www.cbinsights.com/company/roman-health-ventures/financials"),
    ("lyra", "2024-12-31", 5580.0, None, "secondary_npm",
     "https://www.cbinsights.com/company/lyra-health/financials"),
]


# Private lives counts (when reported in funding press). Omada lives go through
# the financials loader since it's now public.
LIVES: list[tuple] = [
    # (company_id, fiscal_period, life_type, lives_count, url)
    ("maven", "2024FY", "eligible", 17_000_000,
     "https://www.prnewswire.com/news-releases/maven-clinic-announces-125-million-series-f-round-of-funding-to-chart-the-next-decade-of-innovation-in-womens-and-family-health-302269566.html"),
    ("spring_health", "2024FY", "eligible", 10_000_000,
     "https://www.springhealth.com/news/series-e-funding-accelerate-growth-expand-global-access"),
]


def url_to_source_id(url: str) -> tuple[str, str]:
    h = hashlib.sha1(url.encode()).hexdigest()[:8]
    if "sec.gov" in url:
        return f"src_sec_{h}", "8-K"
    return f"src_press_{h}", "press"


def url_reliability(url: str) -> str:
    if any(s in url for s in ["sec.gov", "investors.", "investor.", "businesswire", ".com/news/news-details", "prnewswire", "springhealth.com/news", "lyrahealth.com/announcement", "aledade.com/newsroom"]):
        return "primary"
    if any(s in url for s in ["cbinsights", "tracxn", "pitchbook", "getlatka", "wikipedia", "stockanalysis"]):
        return "estimate"
    return "secondary"


def main() -> None:
    # ----- Gather URLs -----
    urls: set[str] = set()
    for recs in ROUNDS.values():
        for r in recs:
            urls.add(r[-1])
    for v in VAL_MARKS:
        urls.add(v[-1])
    for L in LIVES:
        urls.add(L[-1])

    # Load existing dim_source rows, append new ones.
    src_path = SEEDS / "dim_source_seed.csv"
    existing_sources: list[dict] = []
    if src_path.exists():
        with src_path.open() as f:
            for r in csv.DictReader(f):
                existing_sources.append(r)
    existing_ids = {r["source_id"] for r in existing_sources}

    url_to_sid: dict[str, str] = {r["url"]: r["source_id"] for r in existing_sources if r.get("url")}
    new_sources: list[dict] = []
    for u in urls:
        if u in url_to_sid:
            continue
        sid, stype = url_to_source_id(u)
        if sid in existing_ids:
            url_to_sid[u] = sid
            continue
        url_to_sid[u] = sid
        existing_ids.add(sid)
        new_sources.append({
            "source_id": sid,
            "source_type": stype,
            "url": u,
            "retrieved_at": RETRIEVED_AT,
            "reliability": url_reliability(u),
        })
    final_sources = existing_sources + new_sources
    with src_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source_id", "source_type", "url", "retrieved_at", "reliability"])
        w.writeheader()
        for r in final_sources:
            w.writerow(r)

    # ----- fact_funding_round_seed -----
    fr_rows: list[dict] = []
    for cid, recs in ROUNDS.items():
        for r in recs:
            announced, round_type, amount, post_money, leads, url = r
            sid = url_to_sid[url]
            # Deterministic round_id from natural key.
            key = f"{cid}|{announced}|{round_type}|{amount}"
            rid = "rnd_" + hashlib.sha1(key.encode()).hexdigest()[:10]
            fr_rows.append({
                "round_id": rid,
                "company_id": cid,
                "announced_date": announced,
                "round_type": round_type,
                "amount_usd": amount if amount is not None else "",
                "post_money_valuation": post_money if post_money is not None else "",
                "lead_investors_raw": leads,
                "source_id": sid,
            })
    with (SEEDS / "fact_funding_round_seed.csv").open("w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["round_id", "company_id", "announced_date", "round_type",
                           "amount_usd", "post_money_valuation", "lead_investors_raw", "source_id"]
        )
        w.writeheader()
        for r in fr_rows:
            w.writerow(r)

    # ----- fact_valuation_seed: derived from rounds + independent marks -----
    val_rows: list[dict] = []
    for cid, recs in ROUNDS.items():
        for r in recs:
            announced, round_type, amount, post_money, leads, url = r
            if post_money is None:
                continue
            val_rows.append({
                "company_id": cid,
                "as_of_date": announced,
                "valuation_usd": post_money,
                "price_per_share": "",
                "method": "primary_round",
                "source_id": url_to_sid[url],
            })
    for v in VAL_MARKS:
        cid, as_of, val, pps, method, url = v
        val_rows.append({
            "company_id": cid,
            "as_of_date": as_of,
            "valuation_usd": val if val is not None else "",
            "price_per_share": pps if pps is not None else "",
            "method": method,
            "source_id": url_to_sid[url],
        })
    with (SEEDS / "fact_valuation_seed.csv").open("w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["company_id", "as_of_date", "valuation_usd",
                           "price_per_share", "method", "source_id"]
        )
        w.writeheader()
        for r in val_rows:
            w.writerow(r)

    # ----- fact_covered_lives_seed: append privates -----
    lives_path = SEEDS / "fact_covered_lives_seed.csv"
    existing_lives: list[dict] = []
    if lives_path.exists():
        with lives_path.open() as f:
            for r in csv.DictReader(f):
                existing_lives.append(r)
    existing_lives_keys = {(r["company_id"], r["fiscal_period"], r["life_type"]) for r in existing_lives}
    for L in LIVES:
        cid, period, ltype, count, url = L
        if (cid, period, ltype) in existing_lives_keys:
            continue
        existing_lives.append({
            "company_id": cid,
            "fiscal_period": period,
            "life_type": ltype,
            "lives_count": count,
            "source_id": url_to_sid[url],
        })
    with lives_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["company_id", "fiscal_period", "life_type", "lives_count", "source_id"])
        w.writeheader()
        for r in existing_lives:
            w.writerow(r)

    # ----- dim_company_seed: flip Omada to public, add ticker -----
    co_path = SEEDS / "dim_company_seed.csv"
    with co_path.open() as f:
        rdr = csv.DictReader(f)
        fieldnames_co = rdr.fieldnames
        co_rows = list(rdr)
    for r in co_rows:
        if r["company_id"] == "omada":
            r["status"] = "public"
            r["ticker"] = "OMDA"
            r["exchange"] = "NASDAQ"
    with co_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames_co)
        w.writeheader()
        for r in co_rows:
            w.writerow(r)

    print(f"Loaded {len(fr_rows)} funding rounds, {len(val_rows)} valuation marks")
    print(f"Sources: {len(new_sources)} new (total {len(final_sources)})")


if __name__ == "__main__":
    main()
