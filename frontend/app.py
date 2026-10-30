
import os

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = os.getenv("CRICKET_API_URL", "http://127.0.0.1:8000")
QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")

st.set_page_config(
    page_title="Cricket Intelligence",
    page_icon="🏏",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp {
        background-color: #f6f8f7;
    }
    [data-testid="stMetric"] {
        background: white;
        padding: 16px;
        border-radius: 12px;
        border: 1px solid #e1e8e4;
    }
    .main-title {
        color: #174c3c;
        font-size: 2.35rem;
        font-weight: 750;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-title">🏏 Cricket Intelligence</div>',
            unsafe_allow_html=True)
st.caption("Cricket Log Semantic Search · RAG Chat · Match Records")
st.divider()


def get_service_status(url):
    try:
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


# Sidebar: service status and settings
with st.sidebar:
    st.header("⚙️ System Status")

    api_ok = get_service_status(
        f"{API_BASE_URL}/api/search/?event=LBW%20given&limit=1"
    )

    try:
        qdrant_response = requests.get(QDRANT_URL, timeout=5)
        qdrant_ok = qdrant_response.status_code == 200
    except requests.RequestException:
        qdrant_ok = False

    st.write("Django API:", "🟢 Online" if api_ok else "🔴 Offline")
    st.write("Qdrant:", "🟢 Online" if qdrant_ok else "🔴 Offline")
    st.caption("Ollama is checked when you send a chat question.")

    st.divider()
    st.subheader("Search settings")
    result_limit = st.slider("Maximum results", min_value=1, max_value=20, value=5)
    st.caption("Semantic search uses meaning. Exact-event search filters by event name.")


# Summary metrics
metric1, metric2, metric3 = st.columns(3)

metric1.metric("Indexed records", "500", help="Expected dataset size; see the statistics tab for live Qdrant data.")
metric2.metric("Vector database", "Qdrant")
metric3.metric("AI model", "Llama 3.2")

st.divider()

search_tab, chat_tab, stats_tab = st.tabs(
    ["🔎 Semantic Search", "💬 AI Chat", "📊 Dataset Statistics"]
)


with search_tab:
    st.subheader("Search cricket records")
    st.write("Describe a cricket event or use an exact event filter.")

    search_mode = st.radio(
        "Search method",
        ["Semantic search", "Exact event"],
        horizontal=True,
    )

    if search_mode == "Semantic search":
        query = st.text_input(
            "Your search query",
            placeholder="e.g. Show me players who were given out LBW",
            key="semantic_query",
        )
        search_event = None
    else:
        search_event = st.text_input(
            "Exact event",
            placeholder="e.g. LBW given",
            key="exact_event",
        )
        query = None

    if st.button("Search records", type="primary", key="search_button"):
        search_value = query if query is not None else search_event

        if not search_value or not search_value.strip():
            st.warning("Please enter a search query or event.")
        elif not api_ok:
            st.error("The Django API is offline. Start the API container and try again.")
        else:
            try:
                params = {"limit": result_limit}
                if query is not None:
                    params["query"] = query.strip()
                else:
                    params["event"] = search_event.strip()

                with st.spinner("Searching cricket records..."):
                    response = requests.get(
                        f"{API_BASE_URL}/api/search/",
                        params=params,
                        timeout=60,
                    )
                    response.raise_for_status()
                    data = response.json()

                results = data.get("results", [])
                st.session_state["search_data"] = data

            except requests.RequestException as exc:
                st.error(f"Search request failed: {exc}")
            except ValueError:
                st.error("The API returned an invalid response.")

    if "search_data" in st.session_state:
        data = st.session_state["search_data"]
        results = data.get("results", [])

        st.success(f"Returned {len(results)} records")
        st.caption(
            f"Matching filter: {data.get('event', data.get('query', 'semantic search'))}"
        )

        if results:
            df = pd.DataFrame(results)
            preferred_columns = [
                "match", "team", "player", "event", "runs",
                "over", "status", "commentary",
            ]
            columns = [c for c in preferred_columns if c in df.columns]
            st.dataframe(
                df[columns],
                use_container_width=True,
                hide_index=True,
            )

            st.caption(
                "These are the records returned for this request. "
                "Semantic results are ranked by relevance."
            )
            st.download_button(
                "Download results as CSV",
                data=df[columns].to_csv(index=False).encode("utf-8"),
                file_name="cricket_search_results.csv",
                mime="text/csv",
            )
        else:
            st.info("No matching records were returned.")


with chat_tab:
    st.subheader("Ask the cricket log")
    st.write("Ask a question and receive an answer grounded in retrieved records.")

    question = st.text_area(
        "Your question",
        placeholder="e.g. Summarize the records involving LBW decisions.",
        height=100,
    )

    if st.button("Ask AI", type="primary"):
        if not question.strip():
            st.warning("Please enter a question.")
        elif not api_ok:
            st.error("The Django API is offline. Start the API container and try again.")
        else:
            try:
                with st.spinner("Retrieving records and generating an answer..."):
                    response = requests.post(
                        f"{API_BASE_URL}/api/chat/",
                        json={"question": question.strip()},
                        timeout=240,
                    )
                    response.raise_for_status()
                    answer_data = response.json()

                st.session_state["chat_data"] = answer_data

            except requests.Timeout:
                st.error("The AI took too long to respond. Please try again.")
            except requests.RequestException as exc:
                st.error(f"Chat request failed: {exc}")
            except ValueError:
                st.error("The API returned an invalid response.")

    if "chat_data" in st.session_state:
        answer_data = st.session_state["chat_data"]
        st.markdown("### Answer")
        st.write(answer_data.get("answer", "No answer was returned."))

        sources = answer_data.get("sources", [])
        st.markdown("### Retrieved source records")

        if sources:
            st.dataframe(pd.DataFrame(sources), use_container_width=True, hide_index=True)
        else:
            st.info("No source records were returned.")


with stats_tab:
    st.subheader("Vector database statistics")
    st.write("These figures are fetched from Qdrant when you refresh the statistics.")

    if st.button("Refresh statistics"):
        try:
            response = requests.get(
                f"{QDRANT_URL}/collections/cricket_logs",
                timeout=10,
            )
            response.raise_for_status()
            collection = response.json().get("result", {})

            stat1, stat2, stat3 = st.columns(3)
            stat1.metric("Points", collection.get("points_count", "Unknown"))
            stat2.metric("Indexed vectors", collection.get("indexed_vectors_count", "Unknown"))
            stat3.metric("Collection status", collection.get("status", "Unknown"))

            st.caption(
                "Qdrant's indexed_vectors_count may be zero when a separate "
                "vector index has not been built. It does not by itself mean "
                "that stored embeddings are missing."
            )
        except requests.RequestException as exc:
            st.error(f"Could not retrieve Qdrant statistics: {exc}")

st.divider()
st.caption("Cricket Log Semantic Search · Django REST · Qdrant · Ollama · MCP")
