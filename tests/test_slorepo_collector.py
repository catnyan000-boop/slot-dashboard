from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.collectors.base_collector import CollectorError
from src.collectors.slorepo_collector import SlorepoCollector
from src.db.models import StoreDefinition


class _FakeResponse:
    def __init__(self, url: str, text: str, status_code: int = 200) -> None:
        self.url = url
        self.text = text
        self.status_code = status_code
        self.headers = {"Content-Type": "text/html; charset=utf-8"}
        self.content = text.encode("utf-8")


class _FakeSession:
    def __init__(self, responses: dict[str, _FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[str] = []
        self.headers: dict[str, str] = {}

    def get(self, url: str, timeout: int) -> _FakeResponse:
        del timeout
        self.calls.append(url)
        return self.responses[url]


def _store() -> StoreDefinition:
    return StoreDefinition(
        store_id="cosmo_obu",
        display_name="コスモジャパン大府",
        canonical_name="コスモジャパン大府店",
        aliases=["コスモジャパン大府"],
        event_days=["1"],
    )


def _build_collector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SlorepoCollector:
    monkeypatch.setattr(
        "src.collectors.base_collector.BaseCollector._load_robots_text",
        lambda _: None,
    )
    return SlorepoCollector(raw_root=tmp_path / "data" / "raw", request_delay_seconds=1.0)


def test_fetch_store_page_resolves_store_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector = _build_collector(tmp_path, monkeypatch)
    search_url = collector.build_store_search_url(_store())
    store_url = "https://www.slorepo.com/hole/test/"
    collector.session = _FakeSession(
        {
            search_url: _FakeResponse(search_url, '<a href="/hole/test/">店舗</a>'),
            store_url: _FakeResponse(
                store_url,
                '<html><body><a href="20260513">5/13</a></body></html>',
            ),
        }
    )

    page = collector.fetch_store_page(_store())

    assert page.record.url == store_url
    assert collector.session.calls == [search_url, store_url]
    assert page.record.raw_path.endswith("data/raw/slorepo/cosmo_obu/store_test.html")


def test_fetch_store_page_uses_slorepo_slug_without_search(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector = _build_collector(tmp_path, monkeypatch)
    store = StoreDefinition(
        store_id="kyoraku_toyoake",
        display_name="KYORAKU豊明",
        canonical_name="京楽会館豊明店",
        aliases=["KYORAKU豊明"],
        slorepo_slug="toy-slug",
        event_days=["9"],
    )
    store_url = "https://www.slorepo.com/hole/toy-slug/"
    collector.session = _FakeSession(
        {
            store_url: _FakeResponse(
                store_url,
                '<html><body><a href="20260513">5/13</a></body></html>',
            ),
        }
    )

    page = collector.fetch_store_page(store)

    assert page.record.url == store_url
    assert collector.session.calls == [store_url]
    assert page.record.raw_path.endswith("data/raw/slorepo/kyoraku_toyoake/store_toy-slug.html")


def test_raw_path_for_generates_store_day_machine_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector = _build_collector(tmp_path, monkeypatch)

    store_path = collector.raw_path_for(
        store_id="cosmo_obu",
        page_kind="store",
        source_url="https://www.slorepo.com/hole/test/",
    )
    day_path = collector.raw_path_for(
        store_id="cosmo_obu",
        page_kind="day",
        report_date=date(2026, 5, 13),
    )
    machine_path = collector.raw_path_for(
        store_id="cosmo_obu",
        page_kind="machine",
        report_date=date(2026, 5, 13),
        source_url="https://www.slorepo.com/hole/test/20260513/kishu/?kishu=myjuggler",
    )

    assert store_path == tmp_path / "data" / "raw" / "slorepo" / "cosmo_obu" / "store_test.html"
    assert day_path == tmp_path / "data" / "raw" / "slorepo" / "cosmo_obu" / "2026-05-13_day.html"
    assert (
        machine_path
        == tmp_path / "data" / "raw" / "slorepo" / "cosmo_obu" / "2026-05-13_machine_myjuggler.html"
    )


def test_fetch_store_page_uses_cached_html_without_refetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector = _build_collector(tmp_path, monkeypatch)
    cached_path = collector.save_raw_html(
        store_id="cosmo_obu",
        report_date=None,
        page_kind="store",
        html="<html><body>cached</body></html>",
        source_url="https://www.slorepo.com/hole/test/",
    )

    class _ExplodingSession:
        headers: dict[str, str] = {}

        def get(self, url: str, timeout: int) -> _FakeResponse:
            raise AssertionError(f"unexpected network call: {url} timeout={timeout}")

    collector.session = _ExplodingSession()

    page = collector.fetch_store_page(_store())

    assert Path(page.record.raw_path) == cached_path
    assert page.record.url == "https://www.slorepo.com/hole/test/"
    assert page.raw_html == "<html><body>cached</body></html>"


def test_fetch_store_page_rejects_empty_html(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector = _build_collector(tmp_path, monkeypatch)
    search_url = collector.build_store_search_url(_store())
    collector.session = _FakeSession({search_url: _FakeResponse(search_url, "")})

    with pytest.raises(CollectorError, match="Empty HTML returned"):
        collector.fetch_store_page(_store())


def test_collect_store_days_respects_sleep_and_max_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector = _build_collector(tmp_path, monkeypatch)
    collector.request_delay_seconds = 2.0

    sleep_calls: list[float] = []
    monkeypatch.setattr("src.collectors.base_collector.time.monotonic", lambda: 10.0)
    monkeypatch.setattr("src.collectors.base_collector.time.sleep", sleep_calls.append)

    search_url = collector.build_store_search_url(_store())
    store_url = "https://www.slorepo.com/hole/test/"
    day1_url = "https://www.slorepo.com/hole/test/20260513/"
    day2_url = "https://www.slorepo.com/hole/test/20260512/"
    machine1_url = "https://www.slorepo.com/hole/test/20260513/kishu/?kishu=alpha"
    machine2_url = "https://www.slorepo.com/hole/test/20260513/kishu/?kishu=beta"
    machine3_url = "https://www.slorepo.com/hole/test/20260512/kishu/?kishu=gamma"
    machine4_url = "https://www.slorepo.com/hole/test/20260512/kishu/?kishu=delta"

    collector.session = _FakeSession(
        {
            search_url: _FakeResponse(search_url, '<a href="/hole/test/">店舗</a>'),
            store_url: _FakeResponse(
                store_url,
                '<a href="20260513">5/13</a><a href="20260512">5/12</a><a href="20260511">5/11</a>',
            ),
            day1_url: _FakeResponse(
                day1_url,
                """
                <html><body>
                  <h1>2026/05/13(水) テスト店</h1>
                  <a href="kishu/?kishu=alpha">A</a>
                  <a href="kishu/?kishu=beta">B</a>
                </body></html>
                """,
            ),
            day2_url: _FakeResponse(
                day2_url,
                """
                <html><body>
                  <h1>2026/05/12(火) テスト店</h1>
                  <a href="kishu/?kishu=gamma">C</a>
                  <a href="kishu/?kishu=delta">D</a>
                </body></html>
                """,
            ),
            machine1_url: _FakeResponse(machine1_url, "<html><body>machine-a</body></html>"),
            machine2_url: _FakeResponse(machine2_url, "<html><body>machine-b</body></html>"),
            machine3_url: _FakeResponse(machine3_url, "<html><body>machine-c</body></html>"),
            machine4_url: _FakeResponse(machine4_url, "<html><body>machine-d</body></html>"),
        }
    )

    pages = collector.collect_store_days(_store(), days=2, max_machine_pages_per_day=1)

    assert [page.record.url for page in pages] == [
        store_url,
        day1_url,
        day2_url,
        machine1_url,
        machine3_url,
    ]
    assert collector.session.calls == [
        search_url,
        store_url,
        day1_url,
        day2_url,
        machine1_url,
        machine3_url,
    ]
    assert sleep_calls == [2.0, 2.0, 2.0, 2.0, 2.0]


def test_collect_store_days_result_keeps_partial_machine_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector = _build_collector(tmp_path, monkeypatch)
    search_url = collector.build_store_search_url(_store())
    store_url = "https://www.slorepo.com/hole/test/"
    day_url = "https://www.slorepo.com/hole/test/20260513/"
    ok_machine_url = "https://www.slorepo.com/hole/test/20260513/kishu/?kishu=alpha"
    failed_machine_url = "https://www.slorepo.com/hole/test/20260513/kishu/?kishu=beta"

    collector.session = _FakeSession(
        {
            search_url: _FakeResponse(search_url, '<a href="/hole/test/">店舗</a>'),
            store_url: _FakeResponse(
                store_url,
                '<a href="20260513">5/13</a>',
            ),
            day_url: _FakeResponse(
                day_url,
                """
                <html><body>
                  <h1>2026/05/13(水) テスト店</h1>
                  <a href="kishu/?kishu=alpha">A</a>
                  <a href="kishu/?kishu=beta">B</a>
                </body></html>
                """,
            ),
            ok_machine_url: _FakeResponse(ok_machine_url, "<html><body>machine-a</body></html>"),
            failed_machine_url: _FakeResponse(failed_machine_url, "", status_code=403),
        }
    )

    result = collector.collect_store_days_result(_store(), days=1)

    assert result.status == "partial_success"
    assert [page.record.url for page in result.pages] == [
        store_url,
        day_url,
        ok_machine_url,
    ]
    assert result.total_machine_pages == 2
    assert result.saved_machine_pages == 1
    assert len(result.failed_machine_pages) == 1
    assert result.failed_machine_pages[0].url == failed_machine_url
    assert "HTTP 403" in result.failed_machine_pages[0].error
