"""
KAKEN API 診断スクリプト v2 (kaken_api ライブラリ使用)
=======================================================
使い方:
    pip install kaken_api
    python kaken_diagnose2.py --appid YOUR_APP_ID
"""

import argparse
import json
import sys

def check_library():
    try:
        import kaken_api
        print("✓ kaken_api ライブラリ: インストール済み")
        return True
    except ImportError:
        print("✗ kaken_api がインストールされていません")
        print("  → 以下を実行してインストールしてください:")
        print("    pip3 install kaken_api")
        return False

def diagnose(appid: str):
    from kaken_api import KakenApiClient

    print("=" * 60)
    print("STEP 1: KakenApiClient で1件取得")
    print("=" * 60)

    client = KakenApiClient(app_id=appid, use_cache=False)

    try:
        result = client.projects.search(keyword="人工知能", results_per_page=1)
        print(f"✓ 取得成功: 総件数 = {result.total_results}")
    except Exception as e:
        print(f"✗ 取得失敗: {e}")
        print("\n--- 生エラー詳細 ---")
        import traceback
        traceback.print_exc()
        return

    if not result.projects:
        print("プロジェクトが0件でした。")
        return

    p = result.projects[0]
    print(f"\n--- 取得したプロジェクト ---")
    print(f"  award_number : {p.award_number}")
    print(f"  title        : {p.title}")
    print(f"  project_type : {p.project_type}")
    print(f"  allocation_type: {p.allocation_type}")
    print(f"  project_status: {p.project_status}")
    if p.project_status:
        print(f"    status_code: {p.project_status.status_code!r}")
        print(f"    date       : {p.project_status.date}")
        print(f"    note       : {p.project_status.note!r}")
    if p.period_of_award:
        print(f"  period_of_award:")
        print(f"    start_fiscal_year: {p.period_of_award.start_fiscal_year}")
        print(f"    end_fiscal_year  : {p.period_of_award.end_fiscal_year}")
    print(f"  raw_data keys: {list(p.raw_data.keys()) if isinstance(p.raw_data, dict) else type(p.raw_data)}")

    print("\n" + "=" * 60)
    print("STEP 2: 20件取得してステータス値のばらつきを確認")
    print("=" * 60)

    result2 = client.projects.search(keyword="人工知能", results_per_page=20)
    status_values = {}
    period_patterns = set()

    for proj in result2.projects:
        # ステータス集計
        if proj.project_status:
            code = proj.project_status.status_code
            status_values[code] = status_values.get(code, 0) + 1
        else:
            status_values["(なし)"] = status_values.get("(なし)", 0) + 1

        # 単年度判定サンプル
        if proj.period_of_award:
            sy = proj.period_of_award.start_fiscal_year
            ey = proj.period_of_award.end_fiscal_year
            if sy and ey:
                pattern = "単年度" if sy == ey else f"{ey - sy}年間"
                period_patterns.add(pattern)

    print(f"\n  ステータス値の分布 ({len(result2.projects)}件中):")
    for code, cnt in sorted(status_values.items()):
        print(f"    {code!r}: {cnt}件")

    print(f"\n  研究期間パターン: {sorted(period_patterns)}")

    print("\n" + "=" * 60)
    print("STEP 3: raw_data の構造確認（ステータスフィールド名）")
    print("=" * 60)
    for proj in result2.projects[:3]:
        if proj.raw_data:
            print(f"\n--- {proj.award_number} の raw_data ---")
            if isinstance(proj.raw_data, dict):
                print(json.dumps(proj.raw_data, ensure_ascii=False, indent=2)[:1500])
            else:
                print(repr(proj.raw_data)[:1500])

    print("\n診断完了。上記の status_code 値を確認して kaken_extract2.py を設定してください。")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--appid", required=True)
    args = parser.parse_args()

    if not check_library():
        sys.exit(1)

    diagnose(args.appid)
