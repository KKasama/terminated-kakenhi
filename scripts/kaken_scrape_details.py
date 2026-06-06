"""
KAKEN ウェブスクレイピング版 詳細取得スクリプト
=================================================
kaken_failed.json の各プロジェクトページを直接スクレイピングして
以下のフルテキストを取得します：

  ・研究開始時の研究概要
  ・研究実績の概要（中断理由なども含む）
  ・キーワード
  ・研究者情報

出力先（HDD2）:
  /Volumes/HDD2/Kazuki Kasama/Claude/kaken_output/kaken_failed_detailed.json

特徴:
  ・200件ごとに中間保存（Ctrl+Cで中断しても再開可能）
  ・同じコマンドで再開（チェックポイント自動検出）

使い方:
    pip install beautifulsoup4
    python3 kaken_scrape_details.py --appid YOUR_APP_ID
"""

import argparse, json, os, time, sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ── パス設定 ─────────────────────────────────────────────
DATA_DIR     = "/Volumes/HDD2/Kazuki Kasama/Claude/kaken_output"
INPUT_JSON   = os.path.join(DATA_DIR, "kaken_failed.json")
OUTPUT_JSON  = os.path.join(DATA_DIR, "kaken_failed_detailed.json")
CHECKPOINT   = os.path.join(DATA_DIR, ".checkpoint_scrape.txt")
SAVE_EVERY   = 200
DELAY        = 1.2   # 1.2秒待機（サーバー負荷軽減）

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.9",
}

# 取得対象フィールドのラベル（日本語・英語両対応）
FIELD_LABELS = {
    "outline_start_ja": [
        "研究開始時の研究の概要", "研究開始時の研究概要", "研究目的",
    ],
    "outline_start_en": [
        "Outline of Research at the Start", "Research Objective",
    ],
    "outline_achievements_ja": [
        "研究実績の概要", "研究成果の概要",
    ],
    "outline_achievements_en": [
        "Outline of Annual Research Achievements",
        "Summary of Research Achievements",
    ],
    "keywords_ja": ["キーワード"],
    "keywords_en": ["Keywords"],
}


def scrape_project(url: str) -> dict:
    """プロジェクトページをスクレイピングして詳細情報を返す"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        return {"scrape_error": str(e)}

    soup = BeautifulSoup(resp.text, "html.parser")
    result = {
        "outline_start_ja":        None,
        "outline_start_en":        None,
        "outline_achievements_ja": None,
        "outline_achievements_en": None,
        "keywords_ja":             [],
        "keywords_en":             [],
        "researchers":             [],
        "scrape_error":            None,
    }

    # テーブルの全行を走査してラベルに対応するテキストを取得
    for row in soup.find_all("tr"):
        th = row.find("th") or row.find("td", class_=lambda c: c and "label" in c)
        td = row.find("td")
        if not th or not td:
            continue
        label = th.get_text(separator=" ", strip=True)
        text  = td.get_text(separator="\n", strip=True)

        for field, labels in FIELD_LABELS.items():
            if any(l in label for l in labels):
                if "keywords" in field:
                    # キーワードはスラッシュまたは改行区切り
                    kws = [k.strip() for k in text.replace("／", "/").split("/") if k.strip()]
                    result[field] = kws
                else:
                    result[field] = text if text else None

    # 研究者情報（Principal Investigator / Co-Investigator）
    for row in soup.find_all("tr"):
        th = row.find("th") or row.find("td")
        if not th:
            continue
        label = th.get_text(strip=True)
        if any(kw in label for kw in ("Investigator", "研究代表者", "研究分担者")):
            td = row.find("td")
            if td:
                researcher = td.get_text(separator=" ", strip=True)
                if researcher and len(researcher) > 2:
                    result["researchers"].append({
                        "role": label,
                        "name": researcher[:200],
                    })

    return result


def load_checkpoint() -> int:
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            return int(f.read().strip())
    return 0


def save_checkpoint(n: int):
    with open(CHECKPOINT, "w") as f:
        f.write(str(n))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--appid", required=False, help="（不要・互換性のため残しています）")
    args = parser.parse_args()

    # 入力読み込み
    with open(INPUT_JSON, encoding="utf-8") as f:
        projects = json.load(f)
    total = len(projects)
    print(f"対象: {total:,}件  ({INPUT_JSON})")

    # チェックポイント確認
    start_from = load_checkpoint()
    if start_from > 0:
        print(f"▶ チェックポイントから再開: {start_from:,}件目〜")

    # 既存出力を読み込む（再開時）
    if start_from > 0 and os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, encoding="utf-8") as f:
            detailed = json.load(f)
    else:
        detailed = []

    print(f"\n取得開始: {datetime.now():%Y-%m-%d %H:%M:%S}")
    est_min = int((total - start_from) * DELAY / 60)
    print(f"予想所要時間: 約{est_min // 60}時間{est_min % 60}分\n")

    for i, proj in enumerate(projects[start_from:], start=start_from + 1):
        url = proj.get("url")
        award = proj.get("award_number", "?")

        print(f"  [{i:,}/{total:,}] {award} ", end="", flush=True)

        if not url:
            print("URL なし → スキップ")
            detailed.append(proj)
            continue

        scraped = scrape_project(url)

        # 元データ＋スクレイピング結果をマージ
        merged = dict(proj)
        merged.update(scraped)

        has_outline = bool(scraped.get("outline_start_ja") or scraped.get("outline_start_en"))
        has_achieve = bool(scraped.get("outline_achievements_ja") or scraped.get("outline_achievements_en"))
        has_error   = bool(scraped.get("scrape_error"))

        if has_error:
            print(f"⚠ エラー: {scraped['scrape_error']}")
        else:
            print(f"✓ 概要={'あり' if has_outline else 'なし'} "
                  f"実績={'あり' if has_achieve else 'なし'} "
                  f"KW={len(scraped.get('keywords_ja', []))}件")

        detailed.append(merged)

        # 中間保存
        if i % SAVE_EVERY == 0:
            with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
                json.dump(detailed, f, ensure_ascii=False, indent=2)
            save_checkpoint(i)
            elapsed = (i - start_from) * DELAY
            remaining = (total - i) * DELAY
            print(f"\n  ── 中間保存: {i:,}件完了 "
                  f"(残り約{int(remaining // 60)}分) ──\n")

        time.sleep(DELAY)

    # 最終保存
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(detailed, f, ensure_ascii=False, indent=2)
    if os.path.exists(CHECKPOINT):
        os.remove(CHECKPOINT)

    has_o = sum(1 for p in detailed if p.get("outline_start_ja"))
    has_a = sum(1 for p in detailed if p.get("outline_achievements_ja"))
    print(f"\n{'='*60}")
    print(f"完了: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  保存先: {OUTPUT_JSON}")
    print(f"  総件数: {len(detailed):,}件")
    print(f"  研究概要あり: {has_o:,}件")
    print(f"  研究実績あり: {has_a:,}件")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
