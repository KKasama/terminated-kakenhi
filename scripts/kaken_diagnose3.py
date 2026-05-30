"""
KAKEN API 診断スクリプト v3
============================
raw_data XML を直接パースして全フィールドを確認する。
古い年度の案件を検索してステータスフィールドを特定する。

使い方（仮想環境をアクティブにしてから）:
    python3 kaken_diagnose3.py --appid YOUR_APP_ID
"""

import argparse
import json
import xml.etree.ElementTree as ET
from kaken_api import KakenApiClient


def xml_to_dict(element: ET.Element, depth: int = 0) -> dict:
    """XML要素を再帰的にdictに変換（全フィールド表示用）"""
    result = {}
    tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag
    text = (element.text or "").strip()
    attribs = dict(element.attrib)

    node = {}
    if attribs:
        node["@attribs"] = attribs
    if text:
        node["#text"] = text
    for child in element:
        child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        child_val = xml_to_dict(child, depth + 1)
        if child_tag in node:
            # 同名タグが複数あればリストにする
            if not isinstance(node[child_tag], list):
                node[child_tag] = [node[child_tag]]
            node[child_tag].append(child_val)
        else:
            node[child_tag] = child_val

    return node


def parse_raw(raw_bytes: bytes) -> dict:
    """kaken_api の raw_data bytes をパース"""
    root = ET.fromstring(raw_bytes)
    return xml_to_dict(root)


def find_all_leaves(d: dict, prefix: str = "") -> list[tuple[str, str]]:
    """dictのすべての末端(leaf)を (パス, 値) として返す"""
    results = []
    if isinstance(d, dict):
        for k, v in d.items():
            new_key = f"{prefix}.{k}" if prefix else k
            results.extend(find_all_leaves(v, new_key))
    elif isinstance(d, list):
        for i, item in enumerate(d):
            results.extend(find_all_leaves(item, f"{prefix}[{i}]"))
    else:
        results.append((prefix, str(d)[:100]))
    return results


def show_project_fields(proj, label: str = ""):
    """プロジェクトのXMLをパースして全フィールドを表示"""
    if label:
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")

    print(f"  award_number : {proj.award_number}")
    print(f"  title        : {proj.title}")

    if not proj.raw_data:
        print("  raw_data: なし")
        return

    parsed = parse_raw(proj.raw_data)
    leaves = find_all_leaves(parsed)

    # ステータス関連
    status_leaves = [(k, v) for k, v in leaves
                     if any(kw in k.lower() for kw in
                            ("status", "state", "situation", "condition", "result"))]
    print(f"\n  ★ ステータス関連フィールド:")
    if status_leaves:
        for k, v in status_leaves:
            print(f"      {k} = {v!r}")
    else:
        print("      (見つかりません)")

    # 期間関連
    period_leaves = [(k, v) for k, v in leaves
                     if any(kw in k.lower() for kw in
                            ("year", "period", "date", "start", "end", "fiscal", "from", "to"))]
    print(f"\n  ★ 期間関連フィールド:")
    if period_leaves:
        for k, v in period_leaves:
            print(f"      {k} = {v!r}")
    else:
        print("      (見つかりません)")

    # 全フィールド
    print(f"\n  --- 全フィールド ({len(leaves)}個) ---")
    for k, v in leaves:
        print(f"      {k} = {v!r}")


def main(appid: str):
    client = KakenApiClient(app_id=appid, use_cache=False)

    # ① まず最新案件1件の全XML構造を確認
    print("★ STEP 1: 最新案件（2026年）の全XMLフィールドを確認")
    r1 = client.projects.search(keyword="人工知能", results_per_page=1)
    if r1.projects:
        show_project_fields(r1.projects[0], "最新採択案件の全フィールド")

    # ② 古い年度の案件を検索してステータスを探す
    print("\n\n★ STEP 2: 2005〜2010年度の案件を検索（終了済みが多いはず）")
    r2 = client.projects.search(
        keyword="人工知能",
        grant_period_from=2005,
        grant_period_to=2010,
        results_per_page=5,
    )
    print(f"  総件数: {r2.total_results}")
    for i, proj in enumerate(r2.projects[:3]):
        show_project_fields(proj, f"古い案件 {i+1}/{min(3, len(r2.projects))}")

    # ③ ステータス値の集計（全20件）
    print("\n\n★ STEP 3: 古い案件20件のステータスフィールド集計")
    r3 = client.projects.search(
        keyword="",
        grant_period_from=2000,
        grant_period_to=2010,
        results_per_page=20,
    )
    status_counts = {}
    period_info = []
    for proj in r3.projects:
        if not proj.raw_data:
            continue
        parsed = parse_raw(proj.raw_data)
        leaves = find_all_leaves(parsed)
        # ステータス
        for k, v in leaves:
            if any(kw in k.lower() for kw in ("status", "state")):
                status_counts[f"{k}={v}"] = status_counts.get(f"{k}={v}", 0) + 1
        # 期間
        start_year = next((v for k, v in leaves if "startfiscal" in k.lower() or
                           ("start" in k.lower() and "year" in k.lower())), None)
        end_year   = next((v for k, v in leaves if "endfiscal" in k.lower() or
                           ("end" in k.lower() and "year" in k.lower())), None)
        if start_year and end_year:
            period_info.append((proj.award_number, start_year, end_year))

    print("  ステータスフィールド分布:")
    if status_counts:
        for k, v in sorted(status_counts.items()):
            print(f"    {k}: {v}件")
    else:
        print("    (ステータスフィールドが見つかりませんでした)")

    print("\n  期間情報サンプル (award_number, start, end):")
    for row in period_info[:10]:
        sy, ey = row[1], row[2]
        single = " ← 単年度" if sy == ey else ""
        print(f"    {row[0]}: {sy} 〜 {ey}{single}")

    client.close()
    print("\n\n診断完了。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--appid", required=True)
    args = parser.parse_args()
    main(args.appid)
