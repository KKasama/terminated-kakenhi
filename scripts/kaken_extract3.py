"""
KAKEN 抽出スクリプト v3 (project_status + start_index 対応)
=============================================================
kaken_api の project_status パラメータで API 側フィルタリング、
start_index でページネーションして全件取得します。

出力:
    kaken_failed.json    中途終了・採択後辞退・中断・留保
    kaken_onetime.json   単年度（start == end year）
    kaken_status_survey.json  取得できた全ステータスコード分布

使い方:
    python3 kaken_extract3.py --appid YOUR_APP_ID [オプション]

オプション:
    --appid       CiNii AppID（必須）
    --out-dir     出力先ディレクトリ（デフォルト: カレント）
    --page-size   1ページ件数（20/50/100/200/500、デフォルト: 200）
    --delay       リクエスト間待機秒数（デフォルト: 1.0）
    --max-pages   最大ページ数（テスト用: --max-pages 2）
"""

import argparse
import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime

from kaken_api import KakenApiClient

# ------------------------------------------------------------------
# 失敗系として取得する statusCode 候補（APIに渡す値）
# → 診断で 'adopted' が英語コードと確認済み
# → 失敗系は terminated/withdrawn/suspended/reserved を試みる
# ------------------------------------------------------------------
FAILED_CODES_TO_QUERY = [
    "discontinued",  # 中途終了  （10,563件 確認済）
    "declined",      # 採択後辞退 （ 6,281件 確認済）
    "suspended",     # 中断       （   143件 確認済）
]

OUT_DIR = "."


# ------------------------------------------------------------------
# XML パーサー（診断で確定したフィールドパス使用）
# ------------------------------------------------------------------
def parse_xml(raw_bytes: bytes) -> dict:
    root = ET.fromstring(raw_bytes)

    title_ja = title_en = status_code = None
    start_fy = end_fy = allocation = category = institution = total_cost = None

    for summary in root.findall("summary"):
        lang = summary.get("{http://www.w3.org/XML/1998/namespace}lang", "")
        if lang == "ja":
            title_ja    = (summary.findtext("title") or "").strip() or None
            ps          = summary.find("projectStatus")
            status_code = ps.get("statusCode") if ps is not None else None
            poa         = summary.find("periodOfAward")
            if poa is not None:
                start_fy = poa.get("searchStartFiscalYear")
                end_fy   = poa.get("searchEndFiscalYear")
            al  = summary.find("allocation")
            allocation  = (al.text or "").strip() or None if al is not None else None
            ca  = summary.find("category")
            category    = (ca.text or "").strip() or None if ca is not None else None
            inst = summary.find("institution")
            institution = (inst.text or "").strip() or None if inst is not None else None
            oa  = summary.find("overallAwardAmount/totalCost")
            total_cost  = (oa.text or "").strip() or None if oa is not None else None
        elif lang == "en":
            title_en = (summary.findtext("title") or "").strip() or None

    url = (root.findtext("urlList/url") or "").strip() or None

    return {
        "award_number":      root.get("awardNumber"),
        "title_ja":          title_ja,
        "title_en":          title_en,
        "status_code":       status_code,
        "start_fiscal_year": start_fy,
        "end_fiscal_year":   end_fy,
        "allocation":        allocation,
        "category":          category,
        "institution":       institution,
        "total_cost_jpy":    total_cost,
        "url":               url,
    }


def is_onetime(info: dict) -> bool:
    sy, ey = info.get("start_fiscal_year"), info.get("end_fiscal_year")
    return bool(sy and ey and sy == ey)


def fetch_all(client, query_kwargs: dict, page_size: int,
              max_pages: int | None, delay: float, label: str) -> list[dict]:
    """start_index でページネーションして全件取得"""
    results = []
    start   = 1
    page    = 1
    total   = None

    while True:
        if max_pages and page > max_pages:
            break

        print(f"  [{label}] page {page} (start={start})...", end="", flush=True)
        try:
            resp = client.projects.search(
                start_index=start,
                results_per_page=page_size,
                **query_kwargs,
            )
        except Exception as e:
            print(f" エラー: {e} → 3秒後リトライ")
            time.sleep(3)
            try:
                resp = client.projects.search(
                    start_index=start,
                    results_per_page=page_size,
                    **query_kwargs,
                )
            except Exception as e2:
                print(f" リトライ失敗: {e2} → 終了")
                break

        if total is None:
            total = resp.total_results or 0
            print(f" 総件数={total:,}", end="")

        batch = resp.projects
        print(f" 取得={len(batch)}件")

        for proj in batch:
            if proj.raw_data:
                try:
                    results.append(parse_xml(proj.raw_data))
                except Exception:
                    pass

        if not batch or start + page_size > total:
            break
        start += page_size
        page  += 1
        time.sleep(delay)

    return results


def save_json(data: list, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  → 保存: {path}  ({len(data):,}件)")


def main(appid, out_dir, page_size, delay, max_pages):
    os.makedirs(out_dir, exist_ok=True)
    client = KakenApiClient(app_id=appid, use_cache=False)

    failed_projects  = []
    onetime_projects = []
    status_survey    = {}
    seen_failed      = set()
    seen_onetime     = set()

    print(f"\n{'='*60}")
    print(f"抽出開始: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"{'='*60}\n")

    # ─────────────────────────────────────────
    # PART 1: 失敗系（APIでステータスフィルタ）
    # ─────────────────────────────────────────
    print("【PART 1】 失敗系ステータスをAPIで直接フィルタ")
    print(f"  対象コード: {FAILED_CODES_TO_QUERY}\n")

    for code in FAILED_CODES_TO_QUERY:
        batch = fetch_all(
            client,
            query_kwargs={"project_status": code},
            page_size=page_size,
            max_pages=max_pages,
            delay=delay,
            label=code,
        )
        new = 0
        for info in batch:
            sc = info.get("status_code") or code
            status_survey[sc] = status_survey.get(sc, 0) + 1
            an = info.get("award_number")
            if an and an not in seen_failed:
                seen_failed.add(an)
                failed_projects.append(info)
                new += 1
        print(f"    → 新規追加: {new}件 (累計 {len(failed_projects):,}件)\n")

    # ─────────────────────────────────────────
    # 保存
    # ─────────────────────────────────────────
    print("【保存】")
    save_json(failed_projects,  os.path.join(out_dir, "kaken_failed.json"))
    save_json([status_survey],  os.path.join(out_dir, "kaken_status_survey.json"))

    print(f"\n★ 確認されたステータスコード分布:")
    for sc, cnt in sorted(status_survey.items(), key=lambda x: -x[1]):
        print(f"    {sc!r}: {cnt:,}件")

    print(f"\n{'='*60}")
    print(f"抽出完了: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  中途終了・採択後辞退等: {len(failed_projects):,}件")
    print(f"{'='*60}")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--appid",     required=True)
    parser.add_argument("--out-dir",   default=".")
    parser.add_argument("--page-size", type=int, default=200)
    parser.add_argument("--delay",     type=float, default=1.0)
    parser.add_argument("--max-pages", type=int, help="テスト用: ページ数上限")
    args = parser.parse_args()
    main(args.appid, args.out_dir, args.page_size, args.delay, args.max_pages)
