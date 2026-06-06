"""
KAKEN Vector検索 Streamlit アプリ（日本語・英語対応）
======================================================
起動方法:
    pip install streamlit
    streamlit run app.py
"""

import streamlit as st
import weaviate
from weaviate.classes.query import MetadataQuery, Filter, HybridFusion

COLLECTION = "KakenProject"

# ── 翻訳辞書 ─────────────────────────────────────────
T = {
    "page_title": {
        "ja": "KAKEN 失敗プロジェクト検索",
        "en": "KAKEN Terminated Projects Search",
    },
    "app_title": {
        "ja": "🔬 KAKEN 失敗プロジェクト Vector検索",
        "en": "🔬 KAKEN Terminated Projects Vector Search",
    },
    "app_caption": {
        "ja": "中途終了・採択後辞退・中断プロジェクトを意味検索します",
        "en": "Semantic search for discontinued, declined, and suspended projects",
    },
    "search_options": {"ja": "🔧 検索オプション", "en": "🔧 Search Options"},
    "search_mode": {"ja": "検索モード", "en": "Search Mode"},
    "vector": {"ja": "Vector（意味検索）", "en": "Vector (Semantic)"},
    "hybrid": {"ja": "ハイブリッド（意味＋キーワード）", "en": "Hybrid (Semantic + Keyword)"},
    "vector_help": {
        "ja": "Vector: 意味が近い順 / ハイブリッド: 意味＋キーワードの複合スコア",
        "en": "Vector: ranked by semantic similarity / Hybrid: combined score",
    },
    "filters": {"ja": "フィルタ", "en": "Filters"},
    "status": {"ja": "ステータス", "en": "Status"},
    "all": {"ja": "すべて", "en": "All"},
    "discontinued": {"ja": "中途終了", "en": "Discontinued"},
    "declined": {"ja": "採択後辞退", "en": "Declined"},
    "suspended": {"ja": "中断", "en": "Suspended"},
    "ceased": {"ja": "廃止", "en": "Ceased"},
    "year_from": {"ja": "開始年度（以降）", "en": "Start Year (from)"},
    "year_to": {"ja": "終了年度（以前）", "en": "End Year (to)"},
    "year_placeholder_from": {"ja": "例: 2010", "en": "e.g. 2010"},
    "year_placeholder_to": {"ja": "例: 2024", "en": "e.g. 2024"},
    "results_count": {"ja": "表示件数", "en": "Results Limit"},
    "index_count": {"ja": "インデックス件数", "en": "Indexed Projects"},
    "not_connected": {"ja": "Weaviate未接続", "en": "Weaviate not connected"},
    "search_box": {"ja": "🔍 検索クエリ", "en": "🔍 Search Query"},
    "search_placeholder": {
        "ja": "例: 研究者が転職したため継続不能　/ 資金不足　/ がん治療新薬",
        "en": "e.g. researcher resigned and could not continue / insufficient funding",
    },
    "search_help": {
        "ja": "日本語または英語で自由に入力してください。",
        "en": "Enter any query in Japanese or English.",
    },
    "examples_label": {"ja": "検索例:", "en": "Examples:"},
    "examples": {
        "ja": [
            "研究者が異動・退職して継続できなくなった",
            "予算不足で機器購入が困難だった",
            "新型コロナウイルスの影響で中断",
            "がん治療の新しいアプローチ",
        ],
        "en": [
            "Researcher transferred and could not continue",
            "Equipment purchase was difficult due to budget shortage",
            "Suspended due to COVID-19 pandemic",
            "New approach to cancer treatment",
        ],
    },
    "found": {"ja": "件 見つかりました", "en": "results found"},
    "not_found": {"ja": "該当するプロジェクトが見つかりませんでした。", "en": "No matching projects found."},
    "search_error": {"ja": "検索エラー", "en": "Search error"},
    "searching": {"ja": "検索中...", "en": "Searching..."},
    "score": {"ja": "スコア", "en": "Score"},
    "similarity": {"ja": "類似度", "en": "Similarity"},
    "title_ja": {"ja": "タイトル（日本語）", "en": "Title (Japanese)"},
    "title_en": {"ja": "タイトル（英語）", "en": "Title (English)"},
    "status_label": {"ja": "ステータス", "en": "Status"},
    "period": {"ja": "研究期間", "en": "Project Period"},
    "year_suffix": {"ja": "年度", "en": "FY"},
    "category": {"ja": "研究種目", "en": "Research Category"},
    "institution": {"ja": "研究機関", "en": "Institution"},
    "amount": {"ja": "配分額", "en": "Budget"},
    "keywords": {"ja": "キーワード", "en": "Keywords"},
    "outline_start": {"ja": "📋 研究開始時の研究概要", "en": "📋 Research Outline at Start"},
    "outline_achievements": {"ja": "📊 研究実績の概要・中断理由", "en": "📊 Research Achievements / Reason for Termination"},
    "kaken_link": {"ja": "🔗 KAKENページを開く", "en": "🔗 Open KAKEN Page"},
    "intro": {
        "ja": "👆 上の検索ボックスにキーワードを入力するか、検索例ボタンをクリックしてください。",
        "en": "👆 Enter a keyword above or click an example button to search.",
    },
    "about_title": {"ja": "このツールについて", "en": "About This Tool"},
    "about_body": {
        "ja": """
KAKEN（科学研究費助成事業データベース）から抽出した
**中途終了・採択後辞退・中断** プロジェクト **17,301件** を Vector 検索できます。

| 検索モード | 説明 |
|-----------|------|
| Vector（意味検索） | 文章の意味が近いプロジェクトを検索。自然文で検索可能 |
| ハイブリッド | 意味＋キーワードの複合スコアで検索。より精度が高い |

**活用例**
- 「研究者が転職して継続できなくなった」→ 類似の中断理由を持つプロジェクトを発見
- 「新型コロナの影響」→ コロナ禍で中断したプロジェクトを横断検索
- 「機械学習 画像認識」→ 分野を指定して失敗事例を調査
""",
        "en": """
Search **17,301 terminated, declined, and suspended projects** extracted from
KAKEN (Japan's Grants-in-Aid for Scientific Research database).

| Mode | Description |
|------|-------------|
| Vector (Semantic) | Finds projects with similar meaning. Accepts natural language queries |
| Hybrid | Combines semantic similarity and keyword matching for higher precision |

**Use Cases**
- "Researcher resigned and could not continue" → Find similar termination reasons
- "Impact of COVID-19" → Cross-search projects suspended during the pandemic
- "Machine learning image recognition" → Explore failed cases in a specific field
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

STATUS_ICONS = {
    "discontinued": "🔴", "declined": "🟠",
    "suspended": "🟡", "ceased": "🟣",
}

STATUS_JP = {
    "discontinued": "中途終了", "declined": "採択後辞退",
    "suspended": "中断", "ceased": "廃止",
}

st.set_page_config(
    page_title="KAKEN Search",
    page_icon="🔬",
    layout="wide",
)


def t(key):
    lang = st.session_state.get("lang", "ja")
    return T[key][lang]


@st.cache_resource
def get_client():
    return weaviate.connect_to_local()


def search_projects(query, mode, status, year_from, year_to, limit, lang):
    client = get_client()
    collection = client.collections.get(COLLECTION)

    filters = None
    if status:
        filters = Filter.by_property("status_code").equal(status)
    if year_from:
        f = Filter.by_property("start_fiscal_year").greater_or_equal(str(year_from))
        filters = filters & f if filters else f
    if year_to:
        f = Filter.by_property("end_fiscal_year").less_or_equal(str(year_to))
        filters = filters & f if filters else f

    is_hybrid = "Hybrid" in mode or "ハイブリッド" in mode
    if is_hybrid:
        results = collection.query.hybrid(
            query=query, limit=limit, filters=filters,
            fusion_type=HybridFusion.RELATIVE_SCORE,
            return_metadata=MetadataQuery(score=True),
        )
    else:
        results = collection.query.near_text(
            query=query, limit=limit, filters=filters,
            return_metadata=MetadataQuery(distance=True, certainty=True),
        )
    return results.objects


# ── 言語選択 ─────────────────────────────────────────
if "lang" not in st.session_state:
    st.session_state.lang = "ja"

# ── サイドバー ───────────────────────────────────────
with st.sidebar:
    # 言語切り替え
    lang_choice = st.radio(t("language"), ["日本語", "English"],
                           horizontal=True,
                           index=0 if st.session_state.lang == "ja" else 1)
    st.session_state.lang = "ja" if lang_choice == "日本語" else "en"
    lang = st.session_state.lang

    st.divider()
    st.header(t("search_options"))

    mode_options = [t("vector"), t("hybrid")]
    mode = st.radio(t("search_mode"), mode_options, help=t("vector_help"))

    st.divider()
    st.subheader(t("filters"))

    # 凡例
    if lang == "ja":
        st.markdown(
            "🔴 中途終了　🟠 採択後辞退\n\n"
            "🟡 中断　　　🟣 廃止"
        )
    else:
        st.markdown(
            "🔴 Discontinued　🟠 Declined\n\n"
            "🟡 Suspended　　🟣 Ceased"
        )

    status_map = STATUS_CODES[lang]
    status_label = st.selectbox(t("status"), list(status_map.keys()))
    status = status_map[status_label]

    col1, col2 = st.columns(2)
    with col1:
        year_from = st.number_input(t("year_from"), min_value=1965,
                                     max_value=2030, value=None, step=1,
                                     placeholder=t("year_placeholder_from"))
    with col2:
        year_to = st.number_input(t("year_to"), min_value=1965,
                                   max_value=2030, value=None, step=1,
                                   placeholder=t("year_placeholder_to"))

    limit = st.slider(t("results_count"), min_value=1, max_value=30, value=5)

    st.divider()
    try:
        client = get_client()
        col = client.collections.get(COLLECTION)
        count = col.aggregate.over_all(total_count=True).total_count
        st.metric(t("index_count"), f"{count:,}")
    except Exception:
        st.warning(t("not_connected"))

# ── メインエリア ─────────────────────────────────────
st.title(t("app_title"))
st.caption(t("app_caption"))

query = st.text_input(
    t("search_box"),
    placeholder=t("search_placeholder"),
    help=t("search_help"),
)

# 検索例ボタン
st.caption(t("examples_label"))
example_list = t("examples")
ex_cols = st.columns(len(example_list))
for i, ex in enumerate(example_list):
    if ex_cols[i].button(ex, use_container_width=True, key=f"ex_{i}"):
        query = ex

st.divider()

# 検索実行
if query:
    with st.spinner(t("searching")):
        try:
            results = search_projects(query, mode, status, year_from, year_to, limit, lang)
        except Exception as e:
            st.error(f"{t('search_error')}: {e}")
            results = []

    if not results:
        st.warning(t("not_found"))
    else:
        st.success(f"**{len(results)}** {t('found')}")

        for i, obj in enumerate(results, 1):
            p = obj.properties
            m = obj.metadata
            sc = p.get("status_code", "")
            icon = STATUS_ICONS.get(sc, "⚪")
            sc_label = (t(sc) if sc in T else sc) or ""

            if m.score is not None:
                score_str = f"{t('score')}: {m.score:.4f}"
            elif m.certainty is not None:
                score_str = f"{t('similarity')}: {m.certainty:.1%}"
            else:
                score_str = ""

            display_title = (p.get("title_en") if lang == "en" and p.get("title_en")
                             else p.get("title_ja") or "")

            with st.expander(
                f"{icon} [{i}] {p.get('award_number','')}　"
                f"{display_title[:50]}...　　{score_str}",
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

                kw = p.get("keywords_ja", [])
                if kw:
                    st.markdown(f"**{t('keywords')}**: " + "　".join([f"`{k}`" for k in kw]))

                st.divider()

                if p.get("outline_start_ja"):
                    st.markdown(f"**{t('outline_start')}**")
                    st.info(p["outline_start_ja"])

                if p.get("outline_achievements_ja"):
                    st.markdown(f"**{t('outline_achievements')}**")
                    st.warning(p["outline_achievements_ja"])

                if p.get("url"):
                    st.markdown(f"[{t('kaken_link')}]({p['url']})")
else:
    st.info(t("intro"))
    st.markdown(f"### {t('about_title')}")
    st.markdown(t("about_body"))
