import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from urllib.error import HTTPError

from src.workshop import (CATALOG_URLS, RAW_ROOT, SITE, WorkshopStore, atomic_write,
                          code_key, inspect_archive, json_bytes, validate_index)


def archive_bytes():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("team.json", json.dumps({"name": "Demo", "description": "test", "author": "tester",
                                                 "version": "1", "team": "A, B, C"}))
        for name in ("A", "B", "C"):
            archive.writestr(zipfile.ZipInfo(name + ".py", date_time=(2020, 1, 1, 0, 0, 0)), f"class {name}: pass\n")
    return output.getvalue()


def index_data():
    return {"teams": [{"team": "A, B, C", "members": ["A", "B", "C"], "codes": [
        {"filename": "demo.zip", "timestamp": 1, "downloadUrl": SITE + "/codes/demo.zip",
         "rawUrl": RAW_ROOT + "/main/codes/demo.zip"}]}]}


class Response(io.BytesIO):
    def __init__(self, content, url):
        super().__init__(content)
        self.url = url

    def geturl(self):
        return self.url


class TestWorkshopCache(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def store(self, opener):
        return WorkshopStore(self.root / "cache", self.root / "bundle", opener=opener)

    def test_online_refresh_then_offline_preserves_index_and_all_code(self):
        requests = []
        def online(request, **kwargs):
            requests.append(request.full_url)
            content = json_bytes(index_data()) if request.full_url.endswith("teams.json") else archive_bytes()
            return Response(content, request.full_url)
        store = self.store(online)
        catalog = store.refresh()
        self.assertFalse(catalog.offline)
        self.assertEqual(store.prefetch(catalog), [])
        saved = (store.cache_root / "index.json").read_bytes()
        def offline(*args, **kwargs):
            raise OSError("offline")
        store.opener = offline
        cached = store.refresh()
        self.assertTrue(cached.offline)
        self.assertEqual(cached.codes, catalog.codes)
        self.assertEqual((store.cache_root / "index.json").read_bytes(), saved)
        self.assertEqual(store.archive(cached.codes[0]), archive_bytes())
        self.assertEqual(len(requests), 2)

    def test_invalid_json_404_and_html_do_not_replace_good_cache(self):
        store = self.store(lambda request, **kwargs: Response(json_bytes(index_data()), request.full_url))
        store.refresh(prefetch=False)
        saved = (store.cache_root / "index.json").read_bytes()
        for content in (b"<html>challenge</html>", b"{}", b'{"teams": [null]}'):
            store.opener = lambda request, **kwargs: Response(content, request.full_url)
            self.assertTrue(store.refresh().offline)
            self.assertEqual((store.cache_root / "index.json").read_bytes(), saved)
        def missing(request, **kwargs):
            raise HTTPError(request.full_url, 404, "Not Found", {}, None)
        store.opener = missing
        self.assertTrue(store.refresh().offline)
        self.assertEqual((store.cache_root / "index.json").read_bytes(), saved)

    def test_archive_falls_back_to_raw_and_does_not_rewrite_old_site(self):
        requested = []
        code = index_data()["teams"][0]["codes"][0]
        def opener(request, **kwargs):
            requested.append(request.full_url)
            self.assertEqual(request.get_header("User-agent"), "AsterDesk")
            if request.full_url == code["downloadUrl"]:
                raise OSError("site unavailable")
            return Response(archive_bytes(), request.full_url)
        self.assertEqual(self.store(opener).archive(code), archive_bytes())
        self.assertEqual(requested, [code["downloadUrl"], code["rawUrl"]])

    def test_bundled_snapshot_is_available_on_first_offline_start(self):
        root = self.root / "bundle"
        code = index_data()["teams"][0]["codes"][0]
        digest = hashlib.sha256(archive_bytes()).hexdigest()
        atomic_write(root / "current.json", json_bytes({"index": index_data(), "fetched_at": "2026-11-05T00:00:00Z",
                                                         "archives": {code_key(code): digest}}))
        atomic_write(root / "archives" / f"{digest}.zip", archive_bytes())
        def offline(*args, **kwargs):
            raise OSError("offline")
        store = self.store(offline)
        catalog = store.refresh()
        self.assertTrue(catalog.offline)
        self.assertEqual(store.archive(catalog.codes[0]), archive_bytes())
        self.assertFalse(store.cache_root.exists())

    def test_bad_redirect_and_invalid_archives_are_not_cached(self):
        code = index_data()["teams"][0]["codes"][0]
        for content, final_url in ((archive_bytes(), "https://example.org/payload.zip"),
                                   (b"not a zip", code["downloadUrl"])):
            store = self.store(lambda request, **kwargs: Response(content, final_url))
            with self.assertRaises(OSError):
                store.archive(code)
            self.assertFalse((store.cache_root / "archives").exists())

    def test_every_bundled_configuration_has_a_verified_archive(self):
        store = WorkshopStore(cache_root=self.root / "cache")
        catalog = store.cached_catalog()
        self.assertIsNotNone(catalog)
        self.assertGreaterEqual(len(catalog.codes), 72)
        for code in catalog.codes:
            with self.subTest(filename=code["filename"]):
                self.assertIsNotNone(store._cached_archive(code))

    def test_incomplete_package_refresh_does_not_replace_last_complete_catalog(self):
        def online(request, **kwargs):
            content = json_bytes(index_data()) if request.full_url.endswith("teams.json") else archive_bytes()
            return Response(content, request.full_url)
        store = self.store(online)
        store.refresh()
        saved = (store.cache_root / "index.json").read_bytes()
        updated = index_data()
        updated["teams"][0]["codes"][0]["timestamp"] = 2
        def incomplete(request, **kwargs):
            if request.full_url.endswith("teams.json"):
                return Response(json_bytes(updated), request.full_url)
            raise OSError("package unavailable")
        store.opener = incomplete
        catalog = store.refresh()
        self.assertTrue(catalog.offline)
        self.assertEqual(catalog.codes[0]["timestamp"], 1)
        self.assertEqual((store.cache_root / "index.json").read_bytes(), saved)


if __name__ == "__main__":
    unittest.main()
