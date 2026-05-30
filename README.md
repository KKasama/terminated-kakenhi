# terminated-kakenhi

科学研究費助成事業（KAKEN）のうち、**中途終了・採択後辞退・単年度**のプロジェクトを
KAKEN API から抽出したデータセットです。

## データファイル

| ファイル | 内容 |
|---------|------|
| `data/kaken_failed.json` | 中途終了（discontinued）・採択後辞退（declined）・中断（suspended）のプロジェクト |
| `data/kaken_onetime.json` | 単年度（開始年度＝終了年度）のプロジェクト |
| `data/kaken_status_survey.json` | ステータスコード分布 |

## データ項目

```json
{
  "award_number":      "課題番号",
  "title_ja":          "研究課題名（日本語）",
  "title_en":          "研究課題名（英語）",
  "status_code":       "ステータスコード (discontinued / declined / suspended)",
  "start_fiscal_year": "開始年度",
  "end_fiscal_year":   "終了年度",
  "allocation":        "配分区分（基金・補助金等）",
  "category":          "研究種目",
  "institution":       "研究機関",
  "total_cost_jpy":    "総配分額（円）",
  "url":               "KAKENページURL"
}
```

## データソース

- [科学研究費助成事業データベース（KAKEN）](https://kaken.nii.ac.jp/)
- 国立情報学研究所（NII）提供
- 取得日: 2026-05-30

## 抽出スクリプト

`scripts/kaken_extract3.py` を参照してください。

```bash
# 仮想環境セットアップ
python3 -m venv kaken_venv
source kaken_venv/bin/activate
pip install kaken_api

# 実行
python3 scripts/kaken_extract3.py --appid YOUR_APPID --out-dir data/
```

## ライセンス

データはKAKENの[利用規程](https://support.nii.ac.jp/ja/kaken/about/terms)に従います。
