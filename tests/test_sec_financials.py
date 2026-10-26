"""SEC 10-K corporate-wide XBRL adapter tests; fixtures require no network."""
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sec_financials import annual_financials, annual_financials_adapter
from analytics import financial_aggregation, make_analysis, build_financial_directory


class SECAnnualTests(unittest.TestCase):
    def setUp(self):
        self.source={
            "id":"sec_msft_companyfacts", "ticker":"MSFT", "cik":"0000789019",
            "title":"Microsoft consolidated SEC financials"
        }
        self.now="2026-10-26T13:00:00+00:00"

    def fact(self, start, end, value, filed="2026-08-01", form="10-K",
             accn="0000789019-26-000123", fp="FY"):
        return dict(start=start,end=end,val=value,filed=filed,form=form,accn=accn,fp=fp,fy=2026)

    def payload(self, revenue, capex, op_cash=None):
        gaap={
          "RevenueFromContractWithCustomerExcludingAssessedTax":{"units":{"USD":revenue}},
          "PaymentsToAcquirePropertyPlantAndEquipment":{"units":{"USD":capex}}
        }
        if op_cash:
            gaap["NetCashProvidedByUsedInOperatingActivities"]={"units":{"USD":op_cash}}
        return json.dumps({"cik":789019,"entityName":"MICROSOFT CORPORATION","facts":{"us-gaap":gaap}}).encode()

    def test_true_annual_fiscal_periods_and_filing_provenance(self):
        rev=[
            self.fact("2024-07-01","2025-06-30",230_000_000_000, filed="2025-08-01"),
            self.fact("2025-07-01","2026-06-30",258_000_000_000),
            self.fact("2026-04-01","2026-06-30",70_000_000_000,form="10-Q"),
        ]
        cap=[
            self.fact("2024-07-01","2025-06-30",50_000_000_000,filed="2025-08-01"),
            self.fact("2025-07-01","2026-06-30",65_000_000_000),
        ]
        rows=annual_financials(self.payload(rev,cap),self.source,self.now,"data/raw/immutable/xxx.json.gz","checksum")
        self.assertEqual(len(rows),4)
        self.assertEqual({r["period"] for r in rows},{"2025-06-30","2026-06-30"})
        self.assertTrue(all(r["period_type"]=="fiscal_year_end" for r in rows))
        self.assertTrue(all(r["raw_sha256"]=="checksum" for r in rows))
        self.assertTrue(all(r["evidence_type"]=="sec_xbrl_filing" for r in rows))
        self.assertTrue(all(r["accession"].startswith("0000789019") for r in rows))
        self.assertFalse(any(r["value"]==70_000_000_000 for r in rows))

    def test_prefers_taxonomy_primary_and_latest_revision(self):
        r=self.fact("2025-01-01","2025-12-31",100_000_000_000,filed="2026-02-01")
        amend=self.fact("2025-01-01","2025-12-31",108_000_000_000,
                        filed="2026-03-01",form="10-K/A",accn="0000789019-26-000199")
        g={
          "RevenueFromContractWithCustomerExcludingAssessedTax":{"units":{"USD":[r,amend]}},
          "Revenues":{"units":{"USD":[self.fact("2025-01-01","2025-12-31",200_000_000_000)]}},
          "PaymentsToAcquirePropertyPlantAndEquipment":{"units":{"USD":[self.fact("2025-01-01","2025-12-31",30_000_000_000)]}}
        }
        data=json.dumps({"cik":789019,"facts":{"us-gaap":g}}).encode()
        rows=annual_financials(data,self.source,self.now,"raw","sha")
        revenue=next(x for x in rows if x["metric_id"]=="company.revenue_usd")
        self.assertEqual(revenue["value"],108_000_000_000)
        self.assertEqual(revenue["form"],"10-K/A")
        self.assertEqual(revenue["xbrl_tag"],"RevenueFromContractWithCustomerExcludingAssessedTax")
        self.assertEqual(revenue["accession"],"0000789019-26-000199")

    def test_rejects_quarterly_ytd_duration_and_cik_mismatch(self):
        cap=[self.fact("2025-01-01","2025-09-30",55_000_000_000),
             self.fact("2025-01-01","2025-03-31",20_000_000_000)]
        payload=self.payload([],cap)
        with self.assertRaisesRegex(ValueError,"No qualifying annual"):
            annual_financials(payload,self.source,self.now,"raw","sha")
        obj=json.loads(payload);obj["cik"]=1234
        with self.assertRaisesRegex(ValueError,"CIK mismatch"):
            annual_financials(json.dumps(obj).encode(),self.source,self.now,"raw","sha")

    def test_company_periods_not_blended_for_capex_ratio(self):
        def row(ticker,period,metric,value):
            return {"ticker":ticker,"period":period,"period_type":"fiscal_year_end",
                    "metric_id":metric,"value":value,"unit":"USD",
                    "filed_at":"2026-08-01","accession":"0000789019-26-000123",
                    "source_url":"https://www.sec.gov/Archives/edgar/data/789019/000078901926000123/"}
        data=[
            row("MSFT","2025-06-30","company.revenue_usd",100_000_000_000),
            row("MSFT","2025-06-30","company.capex_ppe_usd",20_000_000_000),
            row("MSFT","2026-06-30","company.revenue_usd",200_000_000_000),
            row("MSFT","2026-06-30","company.capex_ppe_usd",60_000_000_000),
            row("NVDA","2026-01-25","company.revenue_usd",100_000_000_000),
            row("NVDA","2025-01-26","company.capex_ppe_usd",30_000_000_000),
        ]
        charts,findings,growth=financial_aggregation(data,{})
        ratio=next(c for c in charts if c["id"]=="sec_company_capex_to_sales")
        self.assertEqual(len(ratio["points"]),1)
        self.assertEqual(ratio["points"][0]["value"],30)
        self.assertEqual(ratio["points"][0]["period"],"2026-06-30")
        self.assertEqual(growth[0]["capex_change_pct"],200)
        self.assertIn("not ai",charts[0]["caveat"].lower())

    def test_missing_capex_keeps_revenue_and_cashflow_visible(self):
        def row(ticker,metric,value):
            return {"ticker":ticker,"period":"2025-12-31","period_type":"fiscal_year_end",
                    "metric_id":metric,"value":value,"unit":"USD",
                    "filed_at":"2026-02-01","accession":"0001018724-26-000004",
                    "source_url":"https://www.sec.gov/Archives/edgar/data/1018724/000101872426000004/"}
        facts=[
            row("AMZN","company.revenue_usd",716_924_000_000),
            row("AMZN","company.operating_cashflow_usd",139_514_000_000),
            row("META","company.revenue_usd",200_966_000_000),
            row("META","company.operating_cashflow_usd",115_800_000_000),
            row("META","company.capex_ppe_usd",69_691_000_000),
        ]
        charts,findings,_=financial_aggregation(facts,{})
        revenue=next(c for c in charts if c["id"]=="sec_company_revenue")
        cashflow=next(c for c in charts if c["id"]=="sec_company_operating_cashflow")
        capex=next(c for c in charts if c["id"]=="sec_company_capex")
        ratio=next(c for c in charts if c["id"]=="sec_company_capex_to_sales")
        self.assertEqual(len(revenue["points"]),2)
        self.assertEqual(len(cashflow["points"]),2)
        self.assertEqual(len(capex["points"]),1)
        self.assertEqual(len(ratio["points"]),1)
        self.assertIn("AMZN",capex["omitted_issuers"])
        self.assertEqual(ratio["points"][0]["value"],34.68)
        self.assertTrue(any("coverage" in f["kind"] for f in findings))

    def test_fiscal_directory_includes_all_issuers_without_mixing_periods(self):
        registry={"financials":[
            {"id":"sec_amzn_companyfacts","ticker":"AMZN",
             "title":"Amazon consolidated SEC financials",
             "homepage":"https://www.sec.gov/edgar/browse/?CIK=1018724"},
            {"id":"sec_meta_companyfacts","ticker":"META",
             "title":"Meta Platforms consolidated SEC financials",
             "homepage":"https://www.sec.gov/edgar/browse/?CIK=1326801"}
        ]}
        def fact(ticker, period, metric, value, start):
            return {"ticker":ticker,"period":period,"period_type":"fiscal_year_end",
                "metric_id":metric,"value":value,"unit":"USD","filed_at":"2026-02-03",
                "accession":"0001018724-26-000004","xbrl_tag":"TestTag",
                "start":start,"source_url":"https://www.sec.gov/Archives/edgar/data/1018724/000101872426000004/"}
        rows=[
            fact("AMZN","2024-12-31","company.revenue_usd",638e9,"2024-01-01"),
            fact("AMZN","2025-12-31","company.revenue_usd",717e9,"2025-01-01"),
            fact("AMZN","2025-12-31","company.operating_cashflow_usd",139e9,"2025-01-01"),
            fact("META","2024-12-31","company.revenue_usd",165e9,"2024-01-01"),
            fact("META","2025-12-31","company.revenue_usd",201e9,"2025-01-01"),
            fact("META","2024-12-31","company.capex_ppe_usd",37e9,"2024-01-01")
        ]
        dashboard=build_financial_directory(rows,registry)
        self.assertEqual(dashboard["schema_version"],1)
        self.assertEqual(dashboard["coverage"]["companies_registered"],2)
        self.assertEqual(dashboard["coverage"]["with_revenue"],2)
        self.assertEqual(dashboard["coverage"]["with_cash_ppe"],0)
        amazon,meta=dashboard["companies"]
        self.assertEqual(amazon["fiscal_year_end"],"2025-12-31")
        self.assertNotIn("company.capex_ppe_usd",amazon["metrics"])
        self.assertNotIn("company.capex_ppe_usd",meta["metrics"])
        self.assertIn("Cash purchases of PPE",meta["missing_metrics"])
        self.assertEqual(len(meta["history"]),2)
        self.assertIn("company.capex_ppe_usd",meta["history"][0]["metrics"])
        self.assertEqual(amazon["metrics"]["company.revenue_usd"]["value_usd"],717e9)
        self.assertEqual(meta["metrics"]["company.revenue_usd"]["period"],"2025-12-31")

    def test_fiscal_directory_shows_registered_but_uncollected_issuer(self):
        registry={"financials":[{"id":"sec_unknown","ticker":"TEST",
            "title":"Test consolidated SEC financials","homepage":"https://www.sec.gov/"}]}
        result=build_financial_directory([],registry)
        self.assertEqual(result["companies"][0]["metrics"],{})
        self.assertEqual(result["companies"][0]["history"],[])
        self.assertIsNone(result["companies"][0]["fiscal_year_end"])
        self.assertEqual(result["coverage"]["with_revenue"],0)

    def test_missing_financials_preserve_coverage_gap(self):
        registry={"feeds":[],"apis":[],"datasets":[],"financials":[],"research":[]}
        report=make_analysis([],[],[],registry,{"generated_at":self.now,
            "successful_sources":0,"failed_sources":0,"sources":[]},financial_rows=[])
        self.assertFalse(any(x["id"].startswith("sec_") for x in report["charts"]))
        self.assertTrue(any("AI infrastructure" in g["title"] for g in report["coverage_gaps"]))


if __name__ == "__main__":
    unittest.main()
