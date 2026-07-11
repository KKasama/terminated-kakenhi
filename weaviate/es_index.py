"""
KAKEN データを Elasticsearch にインデックスするスクリプト
=========================================================
前提:
    Elasticsearch 8.x が localhost:9200 で起動済み
    analysis-kuromoji プラグインがインストール済み

インストール:
    pip install elasticsearch sentence-transformers

使い方:
    python3 es_index.py               # kaken_failed_detailed.json を使用
    python3 es_index.py --reset       # インデックスを削除して再作成
    python3 es_index.py --no-vector   # ベクター埋め込みなし（高速）
"""

import argparse
import json
import os
import sys
import time

from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer

DATA_DIR    = "/Volumes/HDD2/Kazuki Kasama/Claude/Projects/terminated-kakenhi/data"
DETAIL_JSON = os.path.join(DATA_DIR, "kaken_failed_detailed.json")
INDEX_NAME  = "kaken_projects"
MODEL_NAME  = "paraphrase-multilingual-mpnet-base-v2"
BATCH_SIZE  = 200
VECTOR_DIM  = 768


INDEX_SETTINGS = {
    "settings": {
        "analysis": {
            "analyzer": {
                "japanese": {
                    "type": "custom",
                    "tokenizer": "kuromoji_tokenizer",
                    "filter": [
                        "kuromoji_baseform",
                        "kuromoji_part_of_speech",
                        "ja_stop",
                        "kuromoji_stemmer",
                        "lowercase",
                    ],
                }
            }
        },
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "award_number":      {"type": "keyword"},
            "title_ja":          {"type": "text", "analyzer": "japanese"},
            "title_en":          {"type": "text", "analyzer": "english"},
            "status_code":       {"type": "keyword"},
            "start_fiscal_year": {"type": "keyword"},
            "end_fiscal_year":   {"type": "keyword"},
            "allocation":        {"type": "keyword"},
            "category":          {"type": "keyword"},
            "institution":       {"type": "text", "analyzer": "japanese", "fields": {"keyword": {"type": "keyword"}}},
            "total_cost_jpy":    {"type": "long"},
            "url":               {"type": "keyword", "index": False},
            "outline_start_ja":       {"type": "text", "analyzer": "japanese"},
            "outline_start_en":       {"type": "text", "analyzer": "english"},
            "outline_achievements_ja": {"type": "text", "analyzer": "japanese"},
            "outline_achievements_en": {"type": "text", "analyzer": "english"},
            "keywords_ja":       {"type": "keyword"},
            "keywords_en":       {"type": "keyword"},
            "doi":               {"type": "keyword"},
            "pdf_url":           {"type": "keyword", "index": False},
            "embedding":         {"type": "dense_vector", "dims": VECTOR_DIM, "index": True, "similarity": "cosine"},
        }
    },
}


def build_text_for_embedding(proj: dict) -> str:
    parts = [
        proj.get("title_ja") or "",
        proj.get("outline_start_ja") or "",
        proj.get("outline_achievements_ja") or "",
    ]
    kw = proj.get("keywords_ja") or []
    if isinstance(kw, list):
        parts.append(" ".join(kw))
    return " ".join(p for p in parts if p).strip()


def main(reset: bool, no_vector: bool):
    es = Elasticsearch("http://localhost:9200")
    if not es.ping():
        print("エラー: Elasticsearch に接続できません (localhost:9200)")
        sys.exit(1)
    print("✓ Elasticsearch 接続成功")

    if reset and es.indices.exists(index=INDEX_NAME):
        es.indices.delete(index=INDEX_NAME)
        print(f"✓ インデックス '{INDEX_NAME}' を削除しました")

    if not es.indices.exists(index=INDEX_NAME):
        settings = INDEX_SETTINGS
        if no_vector:
            props = dict(settings["mappings"]["properties"])
            del props["embedding"]
            settings = {**settings, "mappings": {"properties": props}}
        es.indices.create(index=INDEX_NAME, body=settings)
        print(f"✓ インデックス '{INDEX_NAME}' を作成しました")
    else:
        print(f"✓ インデックス '{INDEX_NAME}' は既に存在します（追加インポート）")

    print(f"\nデータ読み込み: {DETAIL_JSON}")
    with open(DETAIL_JSON, encoding="utf-8") as f:
        projects = json.load(f)
    print(f"  件数: {len(projects):,}件\n")

    model = None
    if not no_vector:
        print(f"Embedding モデル読み込み: {MODEL_NAME}")
        model = SentenceTransformer(MODEL_NAME)
        print("✓ モデル準備完了\n")

    print(f"インデックス開始: {len(projects):,}件")
    total_ok = 0
    total_err = 0

    for batch_start in range(0, len(projects), BATCH_SIZE):
        batch = projects[batch_start: batch_start + BATCH_SIZE]

        if model:
            texts = [build_text_for_embedding(p) for p in batch]
            embeddings = model.encode(texts, show_progress_bar=False).tolist()
        else:
            embeddings = [None] * len(batch)

        actions = []
        for proj, emb in zip(batch, embeddings):
            cost = proj.get("total_cost_jpy")
            try:
                cost_int = int(cost) if cost else None
            except (ValueError, TypeError):
                cost_int = None

            doc = {
                "_index": INDEX_NAME,
                "_id": proj.get("award_number"),
                "_source": {
                    "award_number":           proj.get("award_number"),
                    "title_ja":               proj.get("title_ja"),
                    "title_en":               proj.get("title_en"),
                    "status_code":            proj.get("status_code"),
                    "start_fiscal_year":      proj.get("start_fiscal_year"),
                    "end_fiscal_year":        proj.get("end_fiscal_year"),
                    "allocation":             proj.get("allocation"),
                    "category":               proj.get("category"),
                    "institution":            proj.get("institution"),
                    "total_cost_jpy":         cost_int,
                    "url":                    proj.get("url"),
                    "outline_start_ja":       proj.get("outline_start_ja"),
                    "outline_start_en":       proj.get("outline_start_en"),
                    "outline_achievements_ja": proj.get("outline_achievements_ja"),
                    "outline_achievements_en": proj.get("outline_achievements_en"),
                    "keywords_ja":            proj.get("keywords_ja") or [],
                    "keywords_en":            proj.get("keywords_en") or [],
                    "doi":                    proj.get("doi"),
                    "pdf_url":                proj.get("pdf_url"),
                },
            }
            if emb is not None:
                doc["_source"]["embedding"] = emb
            actions.append(doc)

        ok, errors = helpers.bulk(es, actions, raise_on_error=False)
        total_ok  += ok
        total_err += len(errors)

        print(f"  [{total_ok:,}/{len(projects):,}] インデックス中... (エラー: {total_err}件)")

    print(f"\n✓ インデックス完了")
    print(f"  登録件数: {total_ok:,}件 / 対象: {len(projects):,}件")
    if total_err:
        print(f"  エラー:   {total_err:,}件")

    count = es.count(index=INDEX_NAME)["count"]
    print(f"\nElasticsearch インデックス '{INDEX_NAME}' の総件数: {count:,}件")
    print("\n次は es_app.py で検索UIを起動できます:")
    print("  streamlit run es_app.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset",     action="store_true", help="インデックスを削除して再作成")
    parser.add_argument("--no-vector", action="store_true", help="ベクター埋め込みをスキップ（高速）")
    args = parser.parse_args()
    main(args.reset, args.no_vector)
