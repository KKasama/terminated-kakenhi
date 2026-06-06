"""
KAKEN Vector検索スクリプト
===========================
Weaviate を使ってKAKENの中途終了・採択後辞退プロジェクトを
意味検索（Vector検索）・ハイブリッド検索します。

使い方:
    python3 weaviate_search.py "予算不足で研究継続が困難"
    python3 weaviate_search.py "研究者が転職したため中断" --limit 10
    python3 weaviate_search.py "がん治療" --hybrid
    python3 weaviate_search.py "機械学習" --filter-status discontinued
    python3 weaviate_search.py --interactive   # 対話モード
"""

import argparse, json, sys
import weaviate
from weaviate.classes.query import MetadataQuery, Filter, HybridFusion

COLLECTION = "KakenProject"

STATUS_LABELS = {
    "discontinued": "中途終了",
    "declined":     "採択後辞退",
    "suspended":    "中断",
    "ceased":       "廃止",
}


def search(client: weaviate.WeaviateClient,
           query: str,
           limit: int = 5,
           hybrid: bool = False,
           filter_status: str | None = None,
           filter_year_from: int | None = None,
           filter_year_to: int | None = None) -> list:

    collection = client.collections.get(COLLECTION)
    filters = None

    # ステータスフィルタ
    if filter_status:
        filters = Filter.by_property("status_code").equal(filter_status)

    # 年度フィルタ
    if filter_year_from:
        f = Filter.by_property("start_fiscal_year").greater_or_equal(str(filter_year_from))
        filters = filters & f if filters else f
    if filter_year_to:
        f = Filter.by_property("end_fiscal_year").less_or_equal(str(filter_year_to))
        filters = filters & f if filters else f

    if hybrid:
        # ハイブリッド検索（Vector + BM25キーワード）
        results = collection.query.hybrid(
            query=query,
            limit=limit,
            filters=filters,
            fusion_type=HybridFusion.RELATIVE_SCORE,
            return_metadata=MetadataQuery(score=True, explain_score=True),
        )
    else:
        # Vector検索（意味検索）
        results = collection.query.near_text(
            query=query,
            limit=limit,
            filters=filters,
            return_metadata=MetadataQuery(distance=True, certainty=True),
        )

    return results.objects


def print_results(objects: list, hybrid: bool = False):
    if not objects:
        print("  検索結果が見つかりませんでした。")
        return

    for i, obj in enumerate(objects, 1):
        p = obj.properties
        m = obj.metadata

        # スコア表示
        if hybrid and m.score is not None:
            score_str = f"スコア={m.score:.4f}"
        elif m.certainty is not None:
            score_str = f"類似度={m.certainty:.2%}"
        elif m.distance is not None:
            score_str = f"距離={m.distance:.4f}"
        else:
            score_str = ""

        status_label = STATUS_LABELS.get(p.get("status_code", ""), p.get("status_code", ""))

        print(f"\n{'─'*60}")
        print(f"[{i}] {p.get('award_number', '')}  {score_str}")
        print(f"    タイトル: {p.get('title_ja', '')[:60]}...")
        print(f"    ステータス: {status_label}  "
              f"期間: {p.get('start_fiscal_year', '')}〜{p.get('end_fiscal_year', '')}年度")
        print(f"    機関: {p.get('institution', '')}  種目: {p.get('category', '')}")

        kw = p.get("keywords_ja", [])
        if kw:
            print(f"    KW: {' / '.join(kw[:5])}")

        outline = p.get("outline_start_ja", "")
        if outline:
            print(f"\n    【研究概要】")
            print(f"    {outline[:200]}...")

        achieve = p.get("outline_achievements_ja", "")
        if achieve:
            print(f"\n    【研究実績・中断理由】")
            print(f"    {achieve[:300]}...")

        print(f"\n    URL: {p.get('url', '')}")


def interactive_mode(client: weaviate.WeaviateClient):
    """対話的検索モード"""
    collection = client.collections.get(COLLECTION)
    count = collection.aggregate.over_all(total_count=True).total_count

    print(f"\n{'='*60}")
    print(f"  KAKEN Vector検索  （{count:,}件インデックス済み）")
    print(f"  コマンド: q=終了, h=ハイブリッド切替, l=件数変更")
    print(f"{'='*60}\n")

    limit  = 5
    hybrid = False

    while True:
        mode_str = "ハイブリッド" if hybrid else "Vector"
        try:
            query = input(f"[{mode_str}/{limit}件] 検索クエリ > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n終了します。")
            break

        if query.lower() in ("q", "quit", "exit"):
            break
        elif query.lower() == "h":
            hybrid = not hybrid
            print(f"  → {'ハイブリッド' if hybrid else 'Vector'}検索に切り替えました")
            continue
        elif query.lower().startswith("l "):
            try:
                limit = int(query[2:])
                print(f"  → 表示件数を {limit} に変更しました")
            except ValueError:
                print("  数値を入力してください")
            continue
        elif not query:
            continue

        results = search(client, query, limit=limit, hybrid=hybrid)
        print_results(results, hybrid=hybrid)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", help="検索クエリ")
    parser.add_argument("--limit", type=int, default=5, help="表示件数")
    parser.add_argument("--hybrid", action="store_true",
                        help="ハイブリッド検索（Vector+キーワード）")
    parser.add_argument("--filter-status", help="ステータスで絞込（discontinued/declined等）")
    parser.add_argument("--year-from", type=int, help="開始年度フィルタ")
    parser.add_argument("--year-to",   type=int, help="終了年度フィルタ")
    parser.add_argument("--interactive", action="store_true",
                        help="対話モード")
    parser.add_argument("--host", default="localhost")
    args = parser.parse_args()

    client = weaviate.connect_to_local(host=args.host)

    try:
        if args.interactive or not args.query:
            interactive_mode(client)
        else:
            print(f"\n検索: 「{args.query}」\n")
            results = search(
                client, args.query,
                limit=args.limit,
                hybrid=args.hybrid,
                filter_status=args.filter_status,
                filter_year_from=args.year_from,
                filter_year_to=args.year_to,
            )
            print_results(results, hybrid=args.hybrid)
    finally:
        client.close()


if __name__ == "__main__":
    main()
