"""Analytical report contracts: no invented trends, separate denominators, reproducible facts."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from analytics import make_analysis, markdown_report


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.registry={"feeds":[{"id":"primary","title":"Primary","priority":"core","homepage":"https://primary.example"}],
          "apis":[{"id":"openrouter_models","title":"OpenRouter","homepage":"https://openrouter.ai/models"}],
          "datasets":[{"id":"eurostat_enterprise_ai_adoption","title":"Eurostat","homepage":"https://ec.europa.eu/eurostat"},
                      {"id":"owid_business_ai_adoption","title":"OWID Survey","homepage":"https://ourworldindata.org"}],
          "research":[]}
        self.status={"generated_at":"2026-10-26T10:30:00+00:00","successful_sources":4,"failed_sources":0,"sources":[]}

    def annual(self,source,entity,geo,year,value):
        return {"source_id":source,"entity_id":entity,"geography":geo,"period":str(year),
                "period_type":"calendar_year","metric_id":"enterprise.ai_adoption_share_pct",
                "observed_at":"2026-10-26T00:00:00+00:00","value":value,"unit":"percent"}

    def test_uses_survey_year_and_percentage_points_separately(self):
        annual=[
            self.annual("eurostat_enterprise_ai_adoption","eurostat:ai_adoption:EU27_2020","EU27",2024,13.48),
            self.annual("eurostat_enterprise_ai_adoption","eurostat:ai_adoption:EU27_2020","EU27",2025,19.95),
            self.annual("owid_business_ai_adoption","owid:ai_adoption:all_geographies","All geographies",2024,78),
            self.annual("owid_business_ai_adoption","owid:ai_adoption:all_geographies","All geographies",2025,88),
        ]
        report=make_analysis([],annual,[],self.registry,self.status)
        eu=next(x for x in report["charts"] if x["id"]=="eurostat_adoption")
        world=next(x for x in report["charts"] if x["id"]=="survey_adoption")
        self.assertEqual(eu["delta"]["change_pp"],6.47)
        self.assertEqual(world["delta"]["change_pp"],10)
        self.assertEqual([x["period"] for x in eu["series"][0]["points"]],["2024","2025"])
        self.assertNotEqual(eu["source_id"],world["source_id"])
        self.assertIn("not directly comparable",report["findings"][1]["text"])
        self.assertIn("2025",markdown_report(report,self.registry))

    def test_no_daily_growth_from_one_snapshot_date(self):
        snapshots=[{"source_id":"github_repo","entity_id":"github:org/a","metric_id":"github.stars",
                    "unit":"count","period":"2026-10-26","observed_at":"2026-10-26T08:00:00+00:00","value":100},
                   {"source_id":"github_repo","entity_id":"github:org/a","metric_id":"github.stars",
                    "unit":"count","period":"2026-10-26","observed_at":"2026-10-26T10:00:00+00:00","value":102}]
        report=make_analysis(snapshots,[],[],self.registry,self.status)
        self.assertFalse(report["daily_changes"])
        self.assertEqual(report["health"]["distinct_snapshot_days"],1)
        self.assertTrue(any(x["kind"]=="insufficient_history" for x in report["findings"]))

    def test_two_days_generate_exact_comparable_delta(self):
        snapshots=[{"source_id":"github_repo","entity_id":"github:org/a","metric_id":"github.stars",
                    "unit":"count","period":d,"observed_at":d+"T00:00:00+00:00","value":n}
                   for d,n in (("2026-10-25",100),("2026-10-26",120))]
        report=make_analysis(snapshots,[],[],self.registry,self.status)
        self.assertEqual(report["daily_changes"][0]["absolute_change"],20)
        self.assertEqual(report["daily_changes"][0]["relative_change_pct"],20)

    def test_catalog_pricing_is_not_volumetric_market_share(self):
        models=[]
        for vendor,prices in [("openai",[1.0,2.0,10.0]),("anthropic",[4.0,0.0])]:
            for i,price in enumerate(prices):
                models.append({"source_id":"openrouter_models",
                    "entity_id":f"openrouter:{vendor}/model-{i}",
                    "metric_id":"openrouter.list_price_input_usd_per_million",
                    "unit":"USD per 1M tokens","period":"2026-10-26",
                    "observed_at":"2026-10-26T00:10:00+00:00","value":price})
        report=make_analysis(models,[],[],self.registry,self.status)
        chart=next(x for x in report["charts"] if x["id"]=="price_input")
        by={x["label"]:x for x in chart["points"]}
        self.assertEqual(by["openai"]["value"],2)
        self.assertEqual(by["anthropic"]["value"],4)
        self.assertEqual(by["anthropic"]["n"],1)
        self.assertIn("neither realized transaction pricing nor market share",chart["caveat"].lower())

    def test_publication_counts_are_core_feed_only_and_labeled_proxy(self):
        self.registry["feeds"].append({"id":"arxiv_ai","priority":"supplemental","title":"arxiv"})
        articles=[{"source_id":"primary","primary_category":"infrastructure"}]*2+[
            {"source_id":"arxiv_ai","primary_category":"models-research"}]*50
        report=make_analysis([],[],articles,self.registry,self.status)
        chart=next(x for x in report["charts"] if x["id"]=="article_topics")
        self.assertEqual(chart["core_total"],2)
        self.assertEqual(chart["all_feed_total"],52)
        self.assertIn("not an industry",chart["caveat"])

    def test_missing_sources_do_not_generate_fictional_economics(self):
        report=make_analysis([],[],[],self.registry,self.status)
        self.assertFalse(any(c["source_id"]=="eurostat_enterprise_ai_adoption" for c in report["cards"]))
        self.assertEqual(len(report["coverage_gaps"]),4)
        self.assertNotIn("revenue",str(report["cards"]).lower())


if __name__=="__main__":
    unittest.main()
