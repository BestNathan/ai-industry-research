"""Data-quality warning and source-freshness contracts."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from quality import quality_report, markdown_report


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.as_of="2026-10-26T10:00:00+00:00"
        self.sources={"feeds":[{"id":"feed","mode":"feed"}],
                      "apis":[{"id":"repo","mode":"api"}],
                      "financials":[{"id":"sec","mode":"financial"}],
                      "datasets":[],"research":[]}

    def record(self,source_id,status,at=None,**extras):
        return {"source_id":source_id,"status":status,"checked_at":self.as_of,
                "last_success_at":at,**extras}

    def test_config_missing_not_a_failed_fetch_or_zero(self):
        state={"generated_at":self.as_of,"sources":[
            self.record("feed","ok",self.as_of,records=0),
            self.record("repo","ok",self.as_of,records=4),
            self.record("sec","skipped_config",None,reason="Real contact required")
        ]}
        q=quality_report(state,[],[],[],[],self.sources,as_of=self.as_of)
        self.assertEqual(q["sources"]["registered"],3)
        self.assertEqual(q["sources"]["ok"],2)
        self.assertEqual(q["sources"]["failed"],0)
        self.assertEqual(q["sources"]["waiting_for_configuration"],1)
        self.assertEqual(q["records"]["sec_financial"],0)
        self.assertEqual(q["sources"]["empty_feeds"],1)
        self.assertTrue(any(w["severity"]=="configuration" for w in q["warnings"]))
        self.assertIn("contact required",markdown_report(q).lower())

    def test_failed_and_stale_are_distinct_warnings(self):
        state={"generated_at":self.as_of,"sources":[
            self.record("feed","failed","2026-10-15T00:00:00+00:00",error="HTTP 503"),
            self.record("repo","ok",self.as_of,records=3),
            self.record("sec","skipped_config",None)
        ]}
        q=quality_report(state,[],[],[],[],self.sources,as_of=self.as_of)
        self.assertEqual(q["sources"]["failed"],1)
        self.assertEqual(q["sources"]["stale"],1)
        self.assertTrue(any(w["type"]=="collection_failed" for w in q["warnings"]))
        self.assertTrue(any(w["type"]=="stale_source" for w in q["warnings"]))

    def test_no_false_intraday_growth_warning(self):
        d="2026-10-26"
        rows=[{"source_id":"repo","entity_id":"github:org/a","metric_id":"github.stars",
               "unit":"count","period":d,"observed_at":d+f"T0{i}:00:00+00:00",
               "value":v} for i,v in [(1,180),(2,110)]]
        q=quality_report({"generated_at":self.as_of},rows,[],[],[],{"apis":[{"id":"repo","mode":"api"}]},as_of=self.as_of)
        self.assertEqual(q["anomalies"],[])

    def test_large_cross_day_cumulative_drop_is_warning_only(self):
        rows=[{"source_id":"repo","entity_id":"github:org/a","metric_id":"github.stars",
               "unit":"count","period":day,"observed_at":day+"T00:00:00+00:00",
               "value":v} for day,v in [("2026-10-25",1000),("2026-10-26",600)]]
        q=quality_report({"generated_at":self.as_of},rows,[],[],[],{"apis":[{"id":"repo","mode":"api"}]},as_of=self.as_of)
        self.assertEqual(len(q["anomalies"]),1)
        self.assertEqual(q["anomalies"][0]["type"],"large_cumulative_drop")
        self.assertEqual(rows[1]["value"],600)


if __name__=="__main__":
    unittest.main()
