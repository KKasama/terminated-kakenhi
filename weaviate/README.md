# KAKEN Vector検索 with Weaviate

## セットアップ手順

### 1. 前提条件確認
```bash
docker --version          # Docker インストール確認
docker compose version    # Docker Compose 確認
```

### 2. Weaviate 起動
```bash
cd weaviate/
docker compose up -d
```
初回は multilingual-e5-large モデル（約1.2GB）のダウンロードに数分かかります。

起動確認:
```bash
curl http://localhost:8080/v1/meta | python3 -m json.tool
```

### 3. Python パッケージインストール
```bash
source ~/kaken_venv/bin/activate
pip install weaviate-client
```

### 4. データのインデックス
```bash
# 詳細データ（抄録・概要付き）が完成している場合
python3 weaviate_index.py

# まだ詳細取得中の場合（基本データのみ）
python3 weaviate_index.py --basic
```

### 5. 検索
```bash
# Vector検索（意味検索）
python3 weaviate_search.py "予算不足で研究が続けられなくなった"

# ハイブリッド検索（意味+キーワード）
python3 weaviate_search.py "がん治療" --hybrid

# ステータスで絞り込み
python3 weaviate_search.py "人工知能" --filter-status discontinued

# 対話モード（連続検索）
python3 weaviate_search.py --interactive
```

## データ構成

| フィールド | Vector化 | 説明 |
|-----------|---------|------|
| title_ja | ✅ | 研究課題名（日本語） |
| outline_start_ja | ✅ | 研究開始時の研究概要 |
| outline_achievements_ja | ✅ | 研究実績の概要・中断理由 |
| award_number | ❌ | 課題番号 |
| status_code | ❌ | discontinued/declined/suspended/ceased |
| start/end_fiscal_year | ❌ | 研究期間 |
| institution | ❌ | 研究機関 |
| keywords_ja | ❌ | キーワード |

## Embedding モデル

- **multilingual-e5-large**（デフォルト・無料・ローカル）
  - 日本語・英語など多言語対応
  - CPU動作可能（GPUがあれば高速化可）

- OpenAI に切り替える場合は `docker-compose.yml` のコメントを参照
