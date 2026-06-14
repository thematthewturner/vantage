from vantage.index.investors import (
    TOP_HEALTHCARE_INVESTOR_COUNT,
    by_slug,
    filter_by_focus,
    firms,
    slugs,
)


def test_curated_investor_watchlist_has_exactly_top_25_unique_ranked_firms():
    records = firms()

    assert len(records) == TOP_HEALTHCARE_INVESTOR_COUNT
    expected_ranks = list(range(1, TOP_HEALTHCARE_INVESTOR_COUNT + 1))
    assert [record["rank"] for record in records] == expected_ranks
    assert len({record["slug"] for record in records}) == TOP_HEALTHCARE_INVESTOR_COUNT
    assert slugs()[0] == "orbimed"


def test_each_investor_record_has_tail_metadata_and_sources():
    for record in firms():
        assert record["name"]
        assert record["website"].startswith("https://")
        assert record["why_top_25"]
        assert len(record["focus"]) >= 3
        assert len(record["tail_signals"]) >= 5
        assert len(record["sources"]) >= 3


def test_lookup_and_focus_filtering():
    assert by_slug("define-ventures")["name"] == "Define Ventures"

    ai_firms = filter_by_focus(["AI"])
    assert {firm["slug"] for firm in ai_firms} >= {
        "andreessen-horowitz-bio-health",
        "general-catalyst",
        "gv",
    }
