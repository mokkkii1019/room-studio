# -*- coding: utf-8 -*-
"""GA4（roomstudio.jp）のアクセス状況を取得するツール。

やること:
  1) 期間サマリ（セッション・ユーザー・エンゲージメント）
  2) 流入の内訳（チャネル / 参照元・メディア / キャンペーン=UTM）
  3) ページ別（LP別・アプリの ref= 別が見える）
  4) イベント別（select_item = 商品クリックが最重要。docs/MEASUREMENT.md §2）

使い方（プロジェクト直下で）:
    python tools/ga4_report.py                # 直近28日
    python tools/ga4_report.py --days 7       # 期間を変える
    python tools/ga4_report.py --jp           # 国=日本のみ（★実ユーザーの数字はこちら）
    python tools/ga4_report.py --realtime     # 今この瞬間（過去30分）
    python tools/ga4_report.py --items        # select_item の内訳（要: G3 カスタムディメンション登録）

★ 素の数字は信用しないこと。全期間の**4割強が海外からの自動巡回**で、それらは
  collect_shop / place_item / select_item を1件も出していない（docs/GA4_ACCESS_REPORT.md §11）。
  実ユーザーを見るときは --jp を付ける。

必要:
  GA4_PROPERTY_ID … 数値のプロパティID（測定ID G-XXXX ではない）
  GA4_SA_KEY      … サービスアカウントJSONキーのパス（リポジトリ外に置くこと）
  どちらも .env か環境変数。事前に GA4 のプロパティのアクセス管理で、
  サービスアカウントのメールアドレスを「閲覧者」として追加しておく（未追加なら 403）。

    pip install google-analytics-data
"""
import os
import sys
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "api"))
from _provider_base import _load_dotenv  # noqa: E402  (.env の KEY=VALUE を読む)

_load_dotenv()

PROPERTY_ID = (os.environ.get("GA4_PROPERTY_ID", "") or "").strip()
SA_KEY = (os.environ.get("GA4_SA_KEY", "") or "").strip()


def _client():
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.oauth2 import service_account
    except ImportError:
        sys.exit("google-analytics-data が未インストール: pip install google-analytics-data")
    if not PROPERTY_ID:
        sys.exit("GA4_PROPERTY_ID が未設定（.env か環境変数に数値のプロパティIDを入れる）")
    if not SA_KEY or not os.path.exists(SA_KEY):
        sys.exit(f"GA4_SA_KEY のファイルが見つからない: {SA_KEY!r}")
    creds = service_account.Credentials.from_service_account_file(
        SA_KEY, scopes=["https://www.googleapis.com/auth/analytics.readonly"])
    return BetaAnalyticsDataClient(credentials=creds)


# ---- 表示 -------------------------------------------------------------------

def _table(title, header, rows, note=""):
    print(f"\n■ {title}")
    if note:
        print(f"  ({note})")
    if not rows:
        print("  （データなし）")
        return
    cols = list(zip(*([header] + rows)))
    # 1列目（ラベル）は左寄せ、数値列は右寄せ
    widths = [max(len(str(c)) for c in col) for col in cols]
    def fmt(cells):
        out = []
        for i, c in enumerate(cells):
            out.append(str(c).ljust(widths[i]) if i == 0 else str(c).rjust(widths[i]))
        return "  ".join(out)
    print("  " + fmt(header))
    print("  " + "-" * (sum(widths) + 2 * (len(widths) - 1)))
    for r in rows:
        print("  " + fmt(r))


def _num(v, metric=""):
    """GA4 の metric 値を読みやすく整形（率は%、時間は秒、それ以外はカンマ区切り）。"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    if metric.endswith("Rate"):
        return f"{f * 100:.1f}%"
    if "Duration" in metric:
        return f"{f:.0f}秒"
    return f"{int(f):,}" if f == int(f) else f"{f:.1f}"


# ---- レポート ---------------------------------------------------------------

def _run(client, dims, mets, days, limit=25, order_desc=True, dim_filter=None):
    from google.analytics.data_v1beta.types import (
        DateRange, Dimension, Metric, OrderBy, RunReportRequest)
    req = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[Dimension(name=d) for d in dims],
        metrics=[Metric(name=m) for m in mets],
        date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
        limit=limit,
    )
    if dim_filter is not None:
        req.dimension_filter = dim_filter
    if dims and order_desc:
        req.order_bys = [OrderBy(metric=OrderBy.MetricOrderBy(metric_name=mets[0]), desc=True)]
    elif dims and not order_desc:
        req.order_bys = [OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name=dims[0]))]
    resp = client.run_report(req)
    return [[dv.value for dv in row.dimension_values] + [mv.value for mv in row.metric_values]
            for row in resp.rows]


def _section(client, title, dims, mets, header, days, limit=25, order_desc=True, note="",
             dim_filter=None):
    """1セクション。失敗しても他を潰さない（未登録ディメンション等は起こりうる）。"""
    try:
        rows = _run(client, dims, mets, days, limit=limit, order_desc=order_desc,
                    dim_filter=dim_filter)
    except Exception as e:  # noqa: BLE001
        print(f"\n■ {title}\n  取得失敗: {type(e).__name__}: {str(e).splitlines()[0][:200]}")
        return
    body = [r[:len(dims)] + [_num(v, mets[i]) for i, v in enumerate(r[len(dims):])] for r in rows]
    _table(title, header, body, note)


def _jp_only():
    """国=日本 だけに絞るフィルタ（--jp）。

    なぜ要るか: 全期間の**4割強が海外からの自動巡回**で、しかもそのセッションは
    `collect_shop` / `place_item` / `select_item` を **1件も出していない**（＝アプリを
    触っていない）。素の数字を見ると、セッションも新規ユーザーもおよそ倍に水増しされ、
    エンゲージメント率は逆に半分近くまで下がる。実測は docs/GA4_ACCESS_REPORT.md §11。"""
    from google.analytics.data_v1beta.types import Filter, FilterExpression
    return FilterExpression(filter=Filter(
        field_name="country",
        string_filter=Filter.StringFilter(
            value="Japan", match_type=Filter.StringFilter.MatchType.EXACT)))


def report(days, jp=False):
    client = _client()
    flt = _jp_only() if jp else None
    print("=" * 64)
    print(f"GA4 レポート  property={PROPERTY_ID}  直近{days}日（今日を含む）"
          + ("  【国=日本のみ】" if jp else ""))
    print("=" * 64)

    # 1) 概要
    try:
        rows = _run(client, [], ["sessions", "totalUsers", "newUsers",
                                 "screenPageViews", "engagementRate", "averageSessionDuration"],
                    days, dim_filter=flt)
        if rows:
            s, u, nu, pv, er, dur = rows[0]
            print(f"\n■ 概要")
            print(f"  セッション         {_num(s)}")
            print(f"  ユーザー           {_num(u)}  （うち新規 {_num(nu)}）")
            print(f"  ページビュー       {_num(pv)}")
            print(f"  エンゲージメント率 {float(er) * 100:.1f}%")
            print(f"  平均セッション時間 {float(dur):.0f}秒")
        else:
            print("\n■ 概要\n  （データなし＝この期間のアクセスは0件）")
    except Exception as e:  # noqa: BLE001
        print(f"\n■ 概要\n  取得失敗: {type(e).__name__}: {str(e).splitlines()[0][:300]}")
        return

    _section(client, "日別", ["date"], ["sessions", "totalUsers"],
             ["日付", "セッション", "ユーザー"], days, limit=62, order_desc=False, dim_filter=flt)

    if not jp:
        _section(client, "国別", ["country"], ["sessions", "screenPageViews", "engagementRate"],
                 ["国", "セッション", "PV", "エンゲージ率"], days, limit=15,
                 note="★日本以外はほぼ全部が自動巡回（アプリのイベントを1件も出さない）。"
                      "実ユーザーの数字は --jp で見る。根拠は docs/GA4_ACCESS_REPORT.md §11")

    _section(client, "チャネル別", ["sessionDefaultChannelGroup"],
             ["sessions", "totalUsers", "engagementRate"],
             ["チャネル", "セッション", "ユーザー", "エンゲージ率"], days, dim_filter=flt,
             note="Unassigned が多い場合は utm_medium の付け方を疑う（docs/MEASUREMENT.md §6-2）")

    _section(client, "参照元 / メディア", ["sessionSource", "sessionMedium"], ["sessions", "totalUsers"],
             ["参照元", "メディア", "セッション", "ユーザー"], days, dim_filter=flt)

    _section(client, "キャンペーン（UTM）", ["sessionCampaignName"], ["sessions", "totalUsers"],
             ["キャンペーン", "セッション", "ユーザー"], days, dim_filter=flt,
             note="(not set) = UTMなしの流入。SNS投稿分がここに落ちていたらUTMの付け忘れ")

    _section(client, "ページ別", ["pagePath"], ["screenPageViews", "sessions"],
             ["パス", "PV", "セッション"], days, limit=20, dim_filter=flt,
             note="/lp/<slug> = LP、/?ref=lp-<slug> = LP経由のアプリ起動")

    _section(client, "着地ページ（クエリ付き）", ["landingPagePlusQueryString"], ["sessions", "totalUsers"],
             ["着地URL", "セッション", "ユーザー"], days, limit=20, dim_filter=flt,
             note="?ref=lp-<slug> や ?utm_* はここに出る。ページ別(pagePath)はクエリを落とすので見えない")

    _section(client, "イベント別", ["eventName"], ["eventCount"],
             ["イベント", "回数"], days, dim_filter=flt,
             note="select_item = 商品クリック（収益に最も近い先行指標）")

    print("\n" + "=" * 64)


def items_breakdown(days):
    """select_item の内訳。shop / link_type のカスタムディメンション登録が前提（G3）。"""
    client = _client()
    print(f"\n=== select_item の内訳（直近{days}日）===")
    for dim, label in [("customEvent:shop", "店舗 / メーカー"),
                       ("customEvent:link_type", "クリック箇所"),
                       ("customEvent:item_id", "商品ID")]:
        _section(client, label, [dim], ["eventCount"], [label, "回数"], days, limit=20)
    print("\n※ 空・エラーの場合は GA4 管理画面でイベントスコープのカスタムディメンション未登録"
          "（docs/MEASUREMENT.md §10 G3）。item_id は予約語と衝突する可能性あり。")


def realtime():
    """今この瞬間（過去30分）。疎通確認用。"""
    from google.analytics.data_v1beta.types import (
        Dimension, Metric, RunRealtimeReportRequest)
    client = _client()

    def rt(dims, mets, limit=20):
        resp = client.run_realtime_report(RunRealtimeReportRequest(
            property=f"properties/{PROPERTY_ID}",
            dimensions=[Dimension(name=d) for d in dims],
            metrics=[Metric(name=m) for m in mets],
            limit=limit))
        return [[dv.value for dv in r.dimension_values] + [mv.value for mv in r.metric_values]
                for r in resp.rows]

    print("=" * 64)
    print(f"GA4 リアルタイム（過去30分）  property={PROPERTY_ID}")
    print("=" * 64)
    try:
        rows = rt([], ["activeUsers"])
        print(f"\n■ アクティブユーザー: {rows[0][0] if rows else 0} 人")
    except Exception as e:  # noqa: BLE001
        print(f"\n取得失敗: {type(e).__name__}: {str(e).splitlines()[0][:300]}")
        return
    for dims, mets, title, header in [
        (["unifiedScreenName"], ["activeUsers"], "ページ別", ["ページ", "人"]),
        (["eventName"], ["eventCount"], "イベント", ["イベント", "回数"]),
        (["deviceCategory"], ["activeUsers"], "デバイス", ["デバイス", "人"]),
    ]:
        try:
            rows = rt(dims, mets)
            _table(title, header, [r[:1] + [_num(v) for v in r[1:]] for r in rows])
        except Exception as e:  # noqa: BLE001
            print(f"\n■ {title}\n  取得失敗: {type(e).__name__}")
    print("\n※ リアルタイムAPIはキャンペーン（UTM）を返さない。UTMの疎通確認は"
          "\n   GA4管理画面のリアルタイム画面で「セッションのキャンペーン」を見ること"
          "（docs/MEASUREMENT.md §9 手順2）。")
    print("=" * 64)


if __name__ == "__main__":
    # Windowsのコンソールは既定がcp932で、この出力（日本語＋記号）が化ける。
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="GA4のアクセス状況を取得する")
    ap.add_argument("--days", type=int, default=28, help="集計日数（既定28）")
    ap.add_argument("--realtime", action="store_true", help="過去30分のリアルタイム")
    ap.add_argument("--items", action="store_true", help="select_item の内訳（要 G3）")
    ap.add_argument("--jp", action="store_true",
                    help="国=日本のみ（海外からの自動巡回を外す。§11）")
    a = ap.parse_args()
    if a.realtime:
        realtime()
    elif a.items:
        items_breakdown(a.days)
    else:
        report(a.days, jp=a.jp)
