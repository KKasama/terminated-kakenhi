"""
KAKEN Elasticsearch 検索 Streamlit アプリ
==========================================
起動方法:
    streamlit run es_app.py
"""

import streamlit as st
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

INDEX_NAME = "kaken_projects"
MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"

T = {
    "page_title":   {"ja": "KAKEN ES検索",              "en": "KAKEN ES Search"},
    "app_title":    {"ja": "🔬 KAKEN 失敗プロジェクト検索（Elasticsearch）",
                     "en": "🔬 KAKEN Terminated Projects Search (Elasticsearch)"},
    "app_caption":  {"ja": "中途終了・採択後辞退・中断プロジェクトを全文検索＋意味検索",
                     "en": "Full-text + semantic search for terminated/declined/suspended projects"},
    "search_options": {"ja": "🔧 検索オプション", "en": "🔧 Search Options"},
    "search_mode":  {"ja": "検索モード", "en": "Search Mode"},
    "fulltext":     {"ja": "全文検索（キーワード）", "en": "Full-text (Keyword)"},
    "semantic":     {"ja": "意味検索（Vector）",    "en": "Semantic (Vector)"},
    "hybrid":       {"ja": "ハイブリッド（全文＋意味）", "en": "Hybrid (Full-text + Semantic)"},
    "filters":      {"ja": "フィルタ", "en": "Filters"},
    "status":       {"ja": "ステータス", "en": "Status"},
    "year_from":    {"ja": "開始年度（以降）", "en": "Start Year (from)"},
    "year_to":      {"ja": "終了年度（以前）", "en": "End Year (to)"},
    "year_ph_from": {"ja": "例: 2010", "en": "e.g. 2010"},
    "year_ph_to":   {"ja": "例: 2024", "en": "e.g. 2024"},
    "results_count":{"ja": "表示件数", "en": "Results Limit"},
    "index_count":  {"ja": "インデックス件数", "en": "Indexed Projects"},
    "not_connected":{"ja": "ES未接続", "en": "ES not connected"},
    "search_box":   {"ja": "🔍 検索クエリ", "en": "🔍 Search Query"},
    "search_ph":    {"ja": "例: 研究者が転職したため継続不能 / 資金不足 / がん治療新薬",
                     "en": "e.g. researcher resigned / insufficient funding / cancer treatment"},
    "examples_label":{"ja": "検索例:", "en": "Examples:"},
    "examples": {
        "ja": ["研究者が異動・退職して継続できなくなった", "予算不足で機器購入が困難",
               "新型コロナウイルスの影響で中断", "がん治療の新しいアプローチ"],
        "en": ["Researcher transferred and could not continue",
               "Equipment purchase difficult due to budget shortage",
               "Suspended due to COVID-19", "New approach to cancer treatment"],
    },
    "found":        {"ja": "件 見つかりました", "en": "results found"},
    "not_found":    {"ja": "該当するプロジェクトが見つかりませんでした。", "en": "No matching projects found."},
    "search_error": {"ja": "検索エラー", "en": "Search error"},
    "searching":    {"ja": "検索中...", "en": "Searching..."},
    "score":        {"ja": "スコア", "en": "Score"},
    "title_ja":     {"ja": "タイトル（日本語）", "en": "Title (Japanese)"},
    "title_en":     {"ja": "タイトル（英語）",   "en": "Title (English)"},
    "status_label": {"ja": "ステータス", "en": "Status"},
    "period":       {"ja": "研究期間",   "en": "Project Period"},
    "year_suffix":  {"ja": "年度",       "en": "FY"},
    "category":     {"ja": "研究種目",   "en": "Research Category"},
    "institution":  {"ja": "研究機関",   "en": "Institution"},
    "amount":       {"ja": "配分額",     "en": "Budget"},
    "keywords":     {"ja": "キーワード", "en": "Keywords"},
    "outline_start":        {"ja": "📋 研究開始時の研究概要",        "en": "📋 Research Outline at Start"},
    "outline_achievements": {"ja": "📊 研究実績の概要・中断理由",    "en": "📊 Achievements / Reason for Termination"},
    "kaken_link":   {"ja": "🔗 KAKENページを開く", "en": "🔗 Open KAKEN Page"},
    "doi_link":     {"ja": "📄 DOI リンク",         "en": "📄 DOI Link"},
    "pdf_link":     {"ja": "📥 PDF をダウンロード", "en": "📥 Download PDF"},
    "intro": {
        "ja": "👆 上の検索ボックスにキーワードを入力するか、検索例ボタンをクリックしてください。",
        "en": "👆 Enter a keyword above or click an example button to search.",
    },
    "about_title": {"ja": "このツールについて", "en": "About This Tool"},
    "about_body": {
        "ja": """
KAKEN（科学研究費助成事業データベース）から抽出した
**中途終了・採択後辞退・中断** プロジェクト **17,301件** を Elasticsearch で検索できます。

| 検索モード | 説明 |
|-----------|------|
| 全文検索 | kuromoji 形態素解析による日本語キーワード検索 |
| 意味検索 | 文章の意味が近いプロジェクトを Vector 検索 |
| ハイブリッド | 全文＋意味の複合スコアで検索（最も精度が高い） |

**将来対応予定**
- DOI リンクからの論文メタデータ取得
- PDF 本文のフルテキストインデックス（ingest-attachment）
""",
        "en": """
Search **17,301 terminated, declined, and suspended projects** from KAKEN using Elasticsearch.

| Mode | Description |
|------|-------------|
| Full-text | Japanese keyword search with kuromoji morphological analysis |
| Semantic | Vector search by meaning similarity |
| Hybrid | Combined score — highest precision |

**Planned features**
- DOI-based paper metadata retrieval
- Full-text PDF indexing via ingest-attachment
""",
    },
    "language": {"ja": "🌐 Language", "en": "🌐 Language"},
}

STATUS_CODES = {
    "ja": {"すべて": "", "中途終了": "discontinued", "採択後辞退": "declined",
           "中断": "suspended", "廃止": "ceased"},
    "en": {"All": "", "Discontinued": "discontinued", "Declined": "declined",
           "Suspended": "suspended", "Ceased": "ceased"},
}
STATUS_ICONS = {"discontinued": "🔴", "declined": "🟠", "suspended": "🟡", "ceased": "🟣"}
STATUS_JP    = {"discontinued": "中途終了", "declined": "採択後辞退",
                "suspended": "中断", "ceased": "廃止"}


def t(key):
    lang = st.session_state.get("lang", "ja")
    return T[key][lang]


@st.cache_resource
def get_es():
    return Elasticsearch("http://localhost:9200")


@st.cache_resource
def get_model():
    return SentenceTransformer(MODEL_NAME)


def build_query(query_text, mode, status, year_from, year_to, limit):
    filters = []
    if status:
        filters.append({"term": {"status_code": status}})
    if year_from:
        filters.append({"range": {"start_fiscal_year": {"gte": str(year_from)}}})
    if year_to:
        filters.append({"range": {"end_fiscal_year": {"lte": str(year_to)}}})

    filter_clause = {"bool": {"filter": filters}} if filters else {"match_all": {}}

    if "全文" in mode or "Full" in mode:
        query = {
            "bool": {
                "must": {
                    "multi_match": {
                        "query": query_text,
                        "fields": ["title_ja^3", "outline_start_ja^2",
                                   "outline_achievements_ja^2", "keywords_ja^2",
                                   "title_en", "outline_start_en"],
                        "analyzer": "japanese",
                        "type": "best_fields",
                    }
                },
                "filter": filters,
            }
        }
        return {"query": query, "size": limit}

    elif "意味" in mode or "Semantic" in mode:
        model = get_model()
        vec = model.encode(query_text).tolist()
        body = {
            "knn": {
                "field": "embedding",
                "query_vector": vec,
                "k": limit,
                "num_candidates": limit * 10,
                "filter": filter_clause,
            },
            "size": limit,
        }
        return body

    else:
        model = get_model()
        vec = model.encode(query_text).tolist()
        body = {
            "query": {
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": query_text,
                            "fields": ["title_ja^3", "outline_start_ja^2",
                                       "outline_achievements_ja^2", "keywords_ja^2",
                                       "title_en"],
                            "analyzer": "japanese",
                        }
                    },
                    "filter": filters,
                }
            },
            "knn": {
                "field": "embedding",
                "query_vector": vec,
                "k": limit,
                "num_candidates": limit * 10,
                "filter": filter_clause,
            },
            "rank": {"rrf": {}},
            "size": limit,
        }
        return body


def search_projects(query_text, mode, status, year_from, year_to, limit):
    es = get_es()
    body = build_query(query_text, mode, status, year_from, year_to, limit)
    resp = es.search(index=INDEX_NAME, body=body)
    total = resp["hits"]["total"]["value"]
    return resp["hits"]["hits"], total


# ── アプリ本体 ────────────────────────────────────────

st.set_page_config(page_title="KAKEN ES Search", page_icon="🔬", layout="wide")

if "lang" not in st.session_state:
    st.session_state.lang = "ja"

with st.sidebar:
    lang_choice = st.radio(t("language"), ["日本語", "English"], horizontal=True,
                           index=0 if st.session_state.lang == "ja" else 1)
    st.session_state.lang = "ja" if lang_choice == "日本語" else "en"
    lang = st.session_state.lang

    st.divider()
    st.header(t("search_options"))

    mode = st.radio(t("search_mode"),
                    [t("fulltext"), t("semantic"), t("hybrid")])

    st.divider()
    st.subheader(t("filters"))

    if lang == "ja":
        st.markdown("🔴 中途終了　🟠 採択後辞退\n\n🟡 中断　　　🟣 廃止")
    else:
        st.markdown("🔴 Discontinued　🟠 Declined\n\n🟡 Suspended　　🟣 Ceased")

    status_map   = STATUS_CODES[lang]
    status_label = st.selectbox(t("status"), list(status_map.keys()))
    status       = status_map[status_label]

    col1, col2 = st.columns(2)
    with col1:
        year_from = st.number_input(t("year_from"), min_value=1965, max_value=2030,
                                    value=None, step=1, placeholder=t("year_ph_from"))
    with col2:
        year_to = st.number_input(t("year_to"), min_value=1965, max_value=2030,
                                  value=None, step=1, placeholder=t("year_ph_to"))

    limit = st.slider(t("results_count"), min_value=1, max_value=50, value=10)

    st.divider()
    try:
        es    = get_es()
        count = es.count(index=INDEX_NAME)["count"]
        st.metric(t("index_count"), f"{count:,}")
    except Exception:
        st.warning(t("not_connected"))

# ── メインエリア ──────────────────────────────────────
st.title(t("app_title"))
st.caption(t("app_caption"))

query = st.text_input(t("search_box"), placeholder=t("search_ph"))

st.caption(t("examples_label"))
example_list = t("examples")
ex_cols = st.columns(len(example_list))
for i, ex in enumerate(example_list):
    if ex_cols[i].button(ex, use_container_width=True, key=f"ex_{i}"):
        query = ex

st.divider()

if query:
    with st.spinner(t("searching")):
        try:
            hits, total = search_projects(query, mode, status, year_from, year_to, limit)
        except Exception as e:
            st.error(f"{t('search_error')}: {e}")
            hits, total = [], 0

    if not hits:
        st.warning(t("not_found"))
    else:
        if total > len(hits):
            st.success(f"**{total:,}** {t('found')}　（上位 **{len(hits)}** 件を表示）")
        else:
            st.success(f"**{total:,}** {t('found')}")

        for i, hit in enumerate(hits, 1):
            p    = hit["_source"]
            score = hit.get("_score") or 0
            sc   = p.get("status_code", "")
            icon = STATUS_ICONS.get(sc, "⚪")
            sc_label = STATUS_JP.get(sc, sc) if lang == "ja" else sc

            display_title = (p.get("title_en") if lang == "en" and p.get("title_en")
                             else p.get("title_ja") or "")

            with st.expander(
                f"{icon} [{i}] {p.get('award_number','')}　"
                f"{display_title[:50]}　　{t('score')}: {score:.4f}",
                expanded=(i == 1),
            ):
                col_l, col_r = st.columns([2, 1])

                with col_l:
                    st.markdown(f"**{t('title_ja')}**: {p.get('title_ja','')}")
                    if p.get("title_en"):
                        st.markdown(f"**{t('title_en')}**: {p.get('title_en','')}")

                with col_r:
                    st.markdown(f"**{t('status_label')}**: {icon} {sc_label}")
                    fy = t("year_suffix")
                    st.markdown(f"**{t('period')}**: {p.get('start_fiscal_year','')}〜{p.get('end_fiscal_year','')} {fy}")
                    st.markdown(f"**{t('category')}**: {p.get('category','')}")
                    st.markdown(f"**{t('institution')}**: {p.get('institution','')}")
                    amt = p.get("total_cost_jpy")
                    st.markdown(f"**{t('amount')}**: ¥{int(amt):,}" if amt else f"**{t('amount')}**: -")

                kw = p.get("keywords_ja") or []
                if kw:
                    st.markdown(f"**{t('keywords')}**: " + "　".join([f"`{k}`" for k in kw]))

                st.divider()

                if p.get("outline_start_ja"):
                    st.markdown(f"**{t('outline_start')}**")
                    st.info(p["outline_start_ja"])

                if p.get("outline_achievements_ja"):
                    st.markdown(f"**{t('outline_achievements')}**")
                    st.warning(p["outline_achievements_ja"])

                links = []
                if p.get("doi"):
                    links.append(f"[{t('doi_link')}](https://doi.org/{p['doi']})")
                if p.get("pdf_url"):
                    links.append(f"[{t('pdf_link')}]({p['pdf_url']})")
                if p.get("url"):
                    links.append(f"[{t('kaken_link')}]({p['url']})")
                if links:
                    st.markdown("　｜　".join(links))
else:
    st.info(t("intro"))
    st.markdown(f"### {t('about_title')}")
    st.markdown(t("about_body"))
