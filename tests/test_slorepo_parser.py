from datetime import date

from src.db.models import DailyStoreResultRecord, MachineResultRecord, UnitResultRecord
from src.parsers.slorepo_parser import SlorepoParser


def test_source_name_is_slorepo() -> None:
    parser = SlorepoParser()
    assert parser.source_name == "slorepo"


def test_peek_report_date_extracts_date() -> None:
    parser = SlorepoParser()
    html = """
    <html>
      <head><title>2026/05/13 テスト店 | SloRepo</title></head>
      <body>
        <h1>2026/05/13(水) テスト店</h1>
      </body>
    </html>
    """

    assert parser.peek_report_date(html) == date(2026, 5, 13)


def test_parse_detail_page_returns_daily_and_machine_records() -> None:
    parser = SlorepoParser()
    html = """
    <html>
      <head><title>2026/05/13 テスト店 日別データ</title></head>
      <body>
        <h1>2026/05/13(水) テスト店</h1>
        <div>総差枚 1,234</div>
        <div>平均差枚 -123</div>
        <div>平均G数 4,567</div>
        <div>勝率 3/5</div>
        <table>
          <tr>
            <th>機種</th>
            <th>平均差枚</th>
            <th>平均G数</th>
            <th>勝率</th>
            <th>台数</th>
          </tr>
          <tr>
            <td><a href="kishu/?kishu=tokyo-ghoul">L東京喰種</a></td>
            <td>-1,234</td>
            <td>8,765</td>
            <td>2/3</td>
            <td>3</td>
          </tr>
          <tr>
            <td><a href="/hole/test/20260513/kishu/?kishu=myjuggler">マイジャグラーV</a></td>
            <td>0</td>
            <td>7,000</td>
            <td>50%</td>
            <td>1</td>
          </tr>
        </table>
      </body>
    </html>
    """

    daily_record, machine_records = parser.parse_detail_page(
        html=html,
        store_id="cosmo_obu",
        source_url="https://www.slorepo.com/hole/test/20260513/",
    )

    assert isinstance(daily_record, DailyStoreResultRecord)
    assert daily_record.report_date == date(2026, 5, 13)
    assert daily_record.total_diff == 1234
    assert daily_record.avg_diff == -123
    assert daily_record.avg_game == 4567
    assert daily_record.win_rate == 0.6
    assert daily_record.total_units == 5

    assert len(machine_records) == 2
    assert all(isinstance(record, MachineResultRecord) for record in machine_records)
    assert machine_records[0].machine_name_raw == "L東京喰種"
    assert machine_records[0].machine_name_normalized == "L東京喰種"
    assert machine_records[0].machine_category == "smart_slot_at"
    assert machine_records[0].avg_diff == -1234
    assert machine_records[0].avg_game == 8765
    assert machine_records[0].win_rate == 2 / 3
    assert machine_records[0].unit_count == 3
    assert (
        machine_records[0].source_url
        == "https://www.slorepo.com/hole/test/20260513/kishu/?kishu=tokyo-ghoul"
    )
    assert machine_records[1].avg_diff == 0
    assert machine_records[1].win_rate == 0.5
    assert machine_records[1].unit_count == 1
    assert machine_records[1].machine_category == "variety"


def test_parse_unit_page_returns_unit_records() -> None:
    parser = SlorepoParser()
    html = """
    <html>
      <head><title>マイジャグラーV 2026/05/13 台データ</title></head>
      <body>
        <h1>マイジャグラーV 2026/05/13 台データ</h1>
        <table>
          <tr>
            <th>台番</th>
            <th>差枚</th>
            <th>G数</th>
            <th>出率</th>
            <th>BB</th>
            <th>RB</th>
            <th>合成</th>
          </tr>
          <tr>
            <td>101</td>
            <td>-1,234</td>
            <td>6,789</td>
            <td>98.7%</td>
            <td>20</td>
            <td>10</td>
            <td>1/226.3</td>
          </tr>
          <tr>
            <td>102</td>
            <td>0</td>
            <td>0</td>
            <td>100.0%</td>
            <td>0</td>
            <td>0</td>
            <td>-</td>
          </tr>
          <tr>
            <td>103</td>
            <td>-</td>
            <td></td>
            <td>-</td>
            <td>-</td>
            <td>-</td>
            <td>-</td>
          </tr>
        </table>
      </body>
    </html>
    """

    rows = parser.parse_unit_page(
        html=html,
        store_id="cosmo_obu",
        source_url="https://www.slorepo.com/hole/test/20260513/kishu/?kishu=myjuggler",
    )

    assert len(rows) == 3
    assert all(isinstance(record, UnitResultRecord) for record in rows)
    assert rows[0].report_date == date(2026, 5, 13)
    assert rows[0].unit_number == "101"
    assert rows[0].machine_name_raw == "マイジャグラーV"
    assert rows[0].machine_name_normalized == "マイジャグラーV"
    assert rows[0].machine_category == "jug_hana"
    assert rows[0].diff == -1234
    assert rows[0].games == 6789
    assert rows[0].payout_rate == 98.7
    assert rows[0].bb == 20
    assert rows[0].rb == 10
    assert rows[0].diff_source == "unit_list_page"
    assert rows[0].games_source == "unit_list_page"
    assert rows[0].payout_rate_source == "unit_list_page"
    assert rows[1].diff == 0
    assert rows[1].games == 0
    assert rows[1].payout_rate == 100.0
    assert rows[1].bb == 0
    assert rows[1].rb == 0
    assert rows[1].diff_source == "unit_list_page"
    assert rows[1].games_source == "unit_list_page"
    assert rows[1].payout_rate_source == "unit_list_page"
    assert rows[2].diff is None
    assert rows[2].games is None
    assert rows[2].payout_rate is None
    assert rows[2].bb is None
    assert rows[2].rb is None
    assert rows[2].diff_source is None
    assert rows[2].games_source is None
    assert rows[2].payout_rate_source is None


def test_parse_unit_page_supports_unicode_minus() -> None:
    parser = SlorepoParser()
    html = """
    <html>
      <body>
        <h1>L東京喰種 2026/05/13 台データ</h1>
        <table>
          <tr><th>台番</th><th>差枚</th><th>G数</th><th>出率</th><th>BB</th><th>RB</th></tr>
          <tr><td>201</td><td>−1,500</td><td>1,000</td><td>95.0%</td><td>5</td><td>2</td></tr>
        </table>
      </body>
    </html>
    """

    rows = parser.parse_unit_page(
        html=html,
        store_id="cosmo_obu",
        source_url="https://www.slorepo.com/hole/test/20260513/kishu/?kishu=tokyo-ghoul",
    )

    assert rows[0].diff == -1500
    assert rows[0].games == 1000
    assert rows[0].payout_rate == 95.0


def test_parse_unit_page_uses_source_url_when_html_has_no_date() -> None:
    parser = SlorepoParser()
    html = """
    <html>
      <body>
        <h1>マイジャグラーV 台データ</h1>
        <table>
          <tr><th>台番</th><th>差枚</th><th>G数</th><th>出率</th><th>BB</th><th>RB</th></tr>
          <tr><td>301</td><td>1,000</td><td>5,000</td><td>106.7%</td><td>18</td><td>12</td></tr>
        </table>
      </body>
    </html>
    """

    rows = parser.parse_unit_page(
        html=html,
        store_id="cosmo_obu",
        source_url="https://www.slorepo.com/hole/test/20260513/kishu/?kishu=myjuggler",
    )

    assert rows[0].report_date == date(2026, 5, 13)


def test_parse_unit_page_strips_store_suffix_from_machine_name() -> None:
    parser = SlorepoParser()
    html = """
    <html>
      <head><title>キングハナハナ-30 - KYORAKU東海店 - (水) -スロレポ</title></head>
      <body>
        <h1>キングハナハナ-30 - KYORAKU東海店 - (水) -スロレポ</h1>
        <table>
          <tr><th>台番</th><th>差枚</th><th>G数</th><th>出率</th><th>BB</th><th>RB</th></tr>
          <tr><td>301</td><td>1,000</td><td>5,000</td><td>106.7%</td><td>18</td><td>12</td></tr>
        </table>
      </body>
    </html>
    """

    rows = parser.parse_unit_page(
        html=html,
        store_id="kyoraku_tokai",
        source_url="https://www.slorepo.com/hole/test/20260513/kishu/?kishu=king-hanahana-30",
    )

    assert rows[0].machine_name_raw == "キングハナハナ-30"
    assert rows[0].machine_name_normalized == "キングハナハナ-30"
