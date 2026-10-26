"""Fixture-backed annual AI adoption parsing without network requests."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from economic import owid_business_adoption, eurostat_business_adoption


class EconomicDatasetTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "id": "owid_business_ai_adoption",
            "homepage": "https://ourworldindata.org/grapher/share-companies-using-artificial-intelligence",
        }
        self.now = "2026-10-26T00:10:00+00:00"

    def test_owid_uses_survey_year_not_collection_date(self):
        csv = (
            "Entity,Code,Year,pct_of_respondents\n"
            "All geographies,OWID_WRL,2024,75\n"
            "All geographies,OWID_WRL,2025,88\n"
            "Greater China,,2025,88\n"
        ).encode()
        result = owid_business_adoption(csv, self.source, self.now, "data/raw/immutable/f.csv.gz", "abc")
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["period"], "2024")
        self.assertEqual(result[0]["reporting_period"], "2024")
        self.assertEqual(result[0]["period_type"], "calendar_year")
        self.assertEqual(result[0]["observed_at"], self.now)
        self.assertEqual(result[1]["value"], 88)
        self.assertEqual(result[1]["unit"], "percent")
        self.assertEqual(result[1]["evidence_type"], "survey_estimate")

    def test_owid_accepts_actual_lowercase_grapher_headers(self):
        csv = b"entity,code,year,pct_of_respondents\nAll geographies,,2025,88\n"
        result = owid_business_adoption(csv, self.source, self.now, "raw", "checksum")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["period"], "2025")
        self.assertEqual(result[0]["value"], 88)

    def test_owid_rejects_schema_drift(self):
        with self.assertRaises(ValueError):
            owid_business_adoption(b"Year,Value\n2025,88\n", self.source, self.now, "x", "sha")

    def test_eurostat_jsonstat_maps_indexes_and_filters(self):
        source = {"id":"eurostat_enterprise_ai_adoption", "homepage":"https://ec.europa.eu/eurostat/databrowser/view/isoc_eb_ai/default/table"}
        doc = {
            "id": ["freq", "unit", "indic_is", "size_emp", "nace_r2", "geo", "time"],
            "size": [1, 1, 2, 1, 1, 1, 2],
            "dimension": {
                "freq": {"category":{"index":{"A":0},"label":{"A":"Annual"}}},
                "unit": {"category":{"index":{"PC_ENT":0},"label":{"PC_ENT":"Percentage of enterprises"}}},
                "indic_is": {"category":{"index":{"E_AI_ANY":0,"E_AI_TAR":1},"label":{
                    "E_AI_ANY":"Enterprises using at least one of the AI technologies",
                    "E_AI_TAR":"Enterprises using a particular AI technology"}}},
                "size_emp":{"category":{"index":{"GE10":0},"label":{"GE10":"10 persons employed or more"}}},
                "nace_r2":{"category":{"index":{"C10_S951_X_K":0},"label":{
                    "C10_S951_X_K":"All activities (except agriculture and mining), without financial sector"}}},
                "geo":{"category":{"index":{"EU27_2020":0},"label":{"EU27_2020":"European Union - 27 countries"}}},
                "time":{"category":{"index":{"2024":0,"2025":1},"label":{"2024":"2024","2025":"2025"}}}
            },
            "value":{"0":13.5,"1":20.0,"2":41.2,"3":51.5}
        }
        result = eurostat_business_adoption(json.dumps(doc).encode(), source, self.now, "raw", "abc")
        self.assertEqual(len(result), 2)
        self.assertEqual([x["period"] for x in result], ["2024","2025"])
        self.assertEqual([x["value"] for x in result], [13.5,20.0])
        self.assertEqual(result[0]["evidence_type"], "official_statistic")

    def test_eurostat_rejects_schema_drift(self):
        with self.assertRaises(ValueError):
            eurostat_business_adoption(b'{"id":["time"],"size":[1]}',
                self.source, self.now, "raw", "abc")


if __name__ == "__main__":
    unittest.main()
