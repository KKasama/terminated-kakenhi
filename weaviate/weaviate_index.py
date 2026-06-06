"""
KAKEN データを Weaviate にインデックスするスクリプト
====================================================
前提:
    docker compose up -d  で Weaviate を起動済みであること

インストール:
    pip install weaviate-client

使い方:
    python3 weaviate_index.py               # kaken_failed_detailed.json を使用
    python3 weaviate_index.py --basic       # kaken_failed.json（詳細なしの場合）
    python3 weaviate_index.py --reset       # コレクションを削除して再作成
"""

import argparse, json, os, time, sys
import weaviate
from weaviate.classes.config import Configure, Property, DataType, Tokenization
from weaviate.util import generate_uuid5

DATA_DIR    = "/Volumes/HDD2/Kazuki Kasama/Claude/kaken_output"
DETAIL_JSON = os.path.join(DATA_DIR, "kaken_failed_detailed.json")
BASIC_JSON  = os.path.join(DATA_DIR, "kaken_failed.json")
COLLECTION  = "KakenProject"
BATCH_SIZE  = 100


def create_collection(client: weaviate.WeaviateClient):
    """コレクション（スキーマ）を作成"""
    client.collections.create(
        name=COLLECTION,
        description="KAKENの中途終了・採択後辞退・中断プロジェクト",

        # ベクトル化の対象フィールドを指定
        # text2vec-transformers（multilingual-e5-large）を使用
        vectorizer_config=Configure.Vectorizer.text2vec_transformers(
            vectorize_collection_name=False,
        ),

        properties=[
            # ── 検索対象（ベクトル化あり）────────────────────────────
            Property(
                name="title_ja",
                data_type=DataType.TEXT,
                description="研究課題名（日本語）",
                skip_vectorization=False,
            ),
            Property(
                name="outline_start_ja",
                data_type=DataType.TEXT,
                description="研究開始時の研究概要",
                skip_vectorization=False,
            ),
            Property(
                name="outline_achievements_ja",
                data_type=DataType.TEXT,
                description="研究実績の概要（中断理由を含む）",
                skip_vectorization=False,
            ),
            # ── メタデータ（ベクトル化なし）─────────────────────────
            Property(
                name="award_number",
                data_type=DataType.TEXT,
                description="課題番号",
                skip_vectorization=True,
                tokenization=Tokenization.FIELD,
            ),
            Property(
                name="title_en",
                data_type=DataType.TEXT,
                description="研究課題名（英語）",
                skip_vectorization=True,
            ),
            Property(
                name="status_code",
                data_type=DataType.TEXT,
                description="ステータスコード",
                skip_vectorization=True,
                tokenization=Tokenization.FIELD,
            ),
            Property(
                name="start_fiscal_year",
                data_type=DataType.TEXT,
                description="開始年度",
                skip_vectorization=True,
            ),
            Property(
                name="end_fiscal_year",
                data_type=DataType.TEXT,
                description="終了年度",
                skip_vectorization=True,
            ),
            Property(
                name="category",
                data_type=DataType.TEXT,
                description="研究種目",
                skip_vectorization=True,
            ),
            Property(
                name="institution",
                data_type=DataType.TEXT,
                description="研究機関",
                skip_vectorization=True,
            ),
            Property(
                name="allocation",
                data_type=DataType.TEXT,
                description="配分区分",
                skip_vectorization=True,
            ),
            Property(
                name="total_cost_jpy",
                data_type=DataType.TEXT,
                description="総配分額（円）",
                skip_vectorization=True,
            ),
            Property(
                name="keywords_ja",
                data_type=DataType.TEXT_ARRAY,
                description="キーワード",
                skip_vectorization=True,
            ),
            Property(
                name="url",
                data_type=DataType.TEXT,
                description="KAKENページURL",
                skip_vectorization=True,
            ),
        ],
    )
    print(f"✓ コレクション '{COLLECTION}' を作成しました")


def prepare_obj(proj: dict) -> dict:
    """プロジェクトデータをWeaviateオブジェクト形式に変換"""
    # ベクトル化テキストの結合（空白を除去して連結）
    parts = [
        proj.get("title_ja") or "",
        proj.get("outline_start_ja") or "",
        proj.get("outline_achievements_ja") or "",
    ]
    combined = " ".join(p for p in parts if p)

    return {
        "award_number":             proj.get("award_number") or "",
        "title_ja":                 proj.get("title_ja") or "",
        "title_en":                 proj.get("title_en") or "",
        "outline_start_ja":         proj.get("outline_start_ja") or "",
        "outline_achievements_ja":  proj.get("outline_achievements_ja") or "",
        "status_code":              proj.get("status_code") or "",
        "start_fiscal_year":        str(proj.get("start_fiscal_year") or ""),
        "end_fiscal_year":          str(proj.get("end_fiscal_year") or ""),
        "category":                 proj.get("category") or "",
        "institution":              proj.get("institution") or "",
        "allocation":               proj.get("allocation") or "",
        "total_cost_jpy":           str(proj.get("total_cost_jpy") or ""),
        "keywords_ja":              proj.get("keywords_ja") or [],
        "url":                      proj.get("url") or "",
    }


def index_data(client: weaviate.WeaviateClient, projects: list):
    """データをバッチでインデックス"""
    collection = client.collections.get(COLLECTION)
    total = len(projects)
    indexed = 0
    errors  = 0

    print(f"\nインデックス開始: {total:,}件")
    print(f"バッチサイズ: {BATCH_SIZE}件\n")

    with collection.batch.fixed_size(batch_size=BATCH_SIZE) as batch:
        for i, proj in enumerate(projects, 1):
            award_number = proj.get("award_number", "")
            if not award_number:
                continue

            obj = prepare_obj(proj)

            # award_number から UUID を生成（冪等性を確保）
            uuid = generate_uuid5(award_number)

            batch.add_object(properties=obj, uuid=uuid)

            if i % 500 == 0:
                failed = batch.number_errors
                print(f"  [{i:,}/{total:,}] インデックス中... "
                      f"(エラー: {failed}件)")

    # 結果確認
    count = collection.aggregate.over_all(total_count=True).total_count
    print(f"\n✓ インデックス完了")
    print(f"  登録件数: {count:,}件 / 対象: {total:,}件")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--basic", action="store_true",
                        help="詳細データなしの kaken_failed.json を使用")
    parser.add_argument("--reset", action="store_true",
                        help="既存コレクションを削除して再作成")
    parser.add_argument("--host", default="localhost",
                        help="Weaviate ホスト（デフォルト: localhost）")
    args = parser.parse_args()

    # データ読み込み
    json_path = BASIC_JSON if args.basic else DETAIL_JSON
    if not os.path.exists(json_path):
        # フォールバック
        json_path = BASIC_JSON if not args.basic else DETAIL_JSON
        if not os.path.exists(json_path):
            print(f"エラー: データファイルが見つかりません: {json_path}")
            sys.exit(1)
    print(f"データ読み込み: {json_path}")
    with open(json_path, encoding="utf-8") as f:
        projects = json.load(f)
    print(f"  件数: {len(projects):,}件")

    # Weaviate 接続
    print(f"\nWeaviate 接続中: {args.host}:8080 ...")
    client = weaviate.connect_to_local(host=args.host)
    print(f"✓ 接続成功")

    try:
        # コレクション管理
        exists = client.collections.exists(COLLECTION)
        if args.reset and exists:
            client.collections.delete(COLLECTION)
            print(f"✓ 既存コレクション '{COLLECTION}' を削除しました")
            exists = False

        if not exists:
            create_collection(client)
        else:
            count = client.collections.get(COLLECTION).aggregate.over_all(
                total_count=True).total_count
            print(f"✓ 既存コレクション '{COLLECTION}' を使用 ({count:,}件登録済み)")
            if count > 0 and not args.reset:
                ans = input("  追加インデックスしますか？ [y/N]: ").strip().lower()
                if ans != "y":
                    print("中止しました。--reset オプションで再作成できます。")
                    return

        # インデックス実行
        index_data(client, projects)

    finally:
        client.close()

    print(f"\n完了！ Weaviate に {len(projects):,}件のデータがインデックスされました。")
    print(f"次は weaviate_search.py で検索できます。")


if __name__ == "__main__":
    main()
