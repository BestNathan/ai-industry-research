"""Deterministic parser and normalization tests: no network access."""
import json
from pathlib import Path
import sys
import unittest
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import pipeline as p


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.taxonomy = p.read_json(ROOT / "config" / "taxonomy.json")["categories"]
        cls.feed = {
            "id": "test_feed", "title": "Test",
            "publisher": "Test Publisher", "mode": "feed",
            "official": True, "category": "models-research"
        }
        cls.checked_at = "2026-10-26T00:10:00+00:00"

    def test_url_normalization_and_stable_id(self):
        original = "https://example.org/ai/report/?utm_source=mail&x=1#intro"
        clean = "https://example.org/ai/report?x=1"
        self.assertEqual(p.canonical_url(original), clean)
        self.assertEqual(p.article_id(original), p.article_id(clean))
        self.assertEqual(p.canonical_url("javascript:alert(1)"), "")

    def test_rss_metadata_only(self):
        xml = b"""<rss version="2.0"><channel><item>
<title>AI agents improve deployment</title>
<link>https://example.org/story?utm_campaign=a</link>
<pubDate>Sun, 25 Oct 2026 22:00:00 GMT</pubDate>
<description><![CDATA[<b>Short</b> summary and deployment notes.]]></description>
</item></channel></rss>"""
        rows = p.parse_feed(xml, self.feed, self.checked_at, "data/raw/test.xml.gz", "checksum", self.taxonomy)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://example.org/story")
        self.assertEqual(rows[0]["summary"], "Short summary and deployment notes.")
        self.assertEqual(rows[0]["content_policy"], "metadata_and_short_feed_excerpt")
        self.assertEqual(rows[0]["published_at"], "2026-10-25T22:00:00+00:00")

    def test_atom_feed(self):
        xml = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title>New open-source model</title><link href="https://example.org/new"/>
<published>2026-10-26T00:00:00Z</published><summary>model evaluation</summary>
</entry></feed>"""
        rows = p.parse_feed(xml, self.feed, self.checked_at, "x", "h", self.taxonomy)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], p.article_id("https://example.org/new"))

    def test_stale_article_not_refreshed_as_new(self):
        xml = b"""<rss><channel><item>
<title>Old AI post</title><link>https://example.org/old</link>
<pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
</item></channel></rss>"""
        self.assertEqual(p.parse_feed(xml, self.feed, self.checked_at, "x", "h", self.taxonomy), [])

    def test_github_observations(self):
        src = {"id": "github_test", "kind": "github_repository", "repo": "openai/codex"}
        data = json.dumps({"full_name": "openai/codex", "stargazers_count": 123,
                           "forks_count": 12, "open_issues_count": 9}).encode()
        rows = p.parse_metrics(data, src, self.checked_at, "data/raw/xyz.gz", "hash")
        self.assertEqual(len(rows), 3)
        self.assertEqual(next(r for r in rows if r["metric_id"] == "github.stars")["value"], 123)
        self.assertTrue(all(r["period"] == "2026-10-26" for r in rows))

    def test_huggingface_model_metrics(self):
        src = {"id": "hf", "kind": "huggingface_models"}
        rows = p.parse_metrics(b'[{"id":"org/model","downloads":99,"likes":8}]',
                               src, self.checked_at, "raw", "hash")
        self.assertEqual({r["metric_id"] for r in rows}, {"huggingface.downloads", "huggingface.likes"})
        self.assertEqual(rows[0]["entity_id"], "huggingface:org/model")

    def test_openrouter_catalog_price_units(self):
        src = {"id": "router", "kind": "openrouter_prices"}
        body = json.dumps({"data": [
            {"id": "openai/example", "created": 1,
             "pricing": {"prompt": "0.000001", "completion": "0.000002"}},
            {"id": "unknown/example", "created": 1, "pricing": {"prompt": "0.01"}}
        ]}).encode()
        rows = p.parse_metrics(body, src, self.checked_at, "raw", "hash")
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["value"] for r in rows}, {1.0, 2.0})
        self.assertTrue(all(r["unit"] == "USD per 1M tokens" for r in rows))

    def test_invalid_number_is_missing_not_zero(self):
        src = {"id": "test"}
        r = p.observation(src, "entity", "metric", float("nan"), "count", "test", self.checked_at, "raw", "hash")
        self.assertIsNone(r)

    def test_content_addressed_raw_archive_deduplicates_across_days(self):
        xml = b"<rss><channel><item><title>AI research</title><link>https://example.org/p</link></item></channel></rss>"
        source = dict(self.feed)
        source["url"] = "https://example.org/rss.xml"
        with tempfile.TemporaryDirectory() as folder:
            fake_root = Path(folder)
            with patch.object(p, "DATA", fake_root / "data"), patch.object(p, "ROOT", fake_root), patch.object(p, "fetch", return_value=xml):
                a1, m1, s1 = p.process_source(source, "2026-10-26", self.checked_at, self.taxonomy)
                a2, m2, s2 = p.process_source(source, "2026-10-27", "2026-10-27T00:10:00+00:00", self.taxonomy)
                self.assertEqual(s1["raw_sha256"], s2["raw_sha256"])
                self.assertEqual(s1["raw_path"], s2["raw_path"])
                self.assertTrue(s1["raw_path"].startswith("data/raw/immutable/"))
                self.assertEqual(len(list((fake_root / "data" / "raw" / "immutable").glob("*"))), 1)
                self.assertEqual(s1["status"], "ok")
                self.assertEqual(len(a1), 1)

    def test_config_unique_source_ids(self):
        registry = p.read_json(ROOT / "config" / "sources.json")
        sources = registry["feeds"] + registry["apis"] + registry["research"]
        self.assertEqual(len(sources), len({s["id"] for s in sources}))
        self.assertGreater(len(registry["research"]), 20)


if __name__ == "__main__":
    unittest.main()
