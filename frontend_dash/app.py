import os

import dash
from dash import Dash, Input, Output, State, callback, dash_table, dcc, html, no_update
import pandas as pd
import requests
import dash_bootstrap_components as dbc


# --------------------------------------------------
# Configuration
# --------------------------------------------------

API_BASE_URL = os.getenv("CRICKET_API_URL", "http://127.0.0.1:8000")
QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")

GREEN = "#174C3C"
DARK = "#102B24"
MUTED = "#718078"
BG = "#F4F7F5"

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="Cricket Intelligence",
    suppress_callback_exceptions=True,
)

server = app.server


# --------------------------------------------------
# Backend helpers
# --------------------------------------------------

def get_api_status():
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/search/",
            params={"event": "LBW given", "limit": 1},
            timeout=5,
        )
        return response.ok
    except requests.RequestException:
        return False


def get_qdrant_data():
    try:
        response = requests.get(
            f"{QDRANT_URL}/collections/cricket_logs",
            timeout=5,
        )
        response.raise_for_status()
        return response.json().get("result", {})
    except (requests.RequestException, ValueError):
        return {}


# --------------------------------------------------
# Reusable components
# --------------------------------------------------

def card(title, value, subtitle, color=GREEN):
    return dbc.Card(
        dbc.CardBody([
            html.Div(title, className="metric-label"),
            html.H3(str(value), className="metric-value",
                    style={"color": color}),
            html.Div(subtitle, className="metric-subtitle"),
        ]),
        className="metric-card h-100",
    )


def page_heading(title, description):
    return html.Div([
        html.H2(title, className="page-title"),
        html.P(description, className="page-description"),
    ])


def make_table(data, page_size=10):
    """Display records with readable validation information."""
    if not data:
        return dbc.Alert("No records returned.", color="light")

    display_data = []

    for item in data:
        row = item.copy()

        warnings = row.pop("validation_warnings", [])
        classification = row.pop("record_classification", {})

        if isinstance(classification, dict):
            row["data_quality"] = classification.get(
                "data_quality", "unknown"
            )
            row["review_status"] = classification.get(
                "review_status", row.get("status", "unknown")
            )
        else:
            row["data_quality"] = "unknown"
            row["review_status"] = row.get("status", "unknown")

        if isinstance(warnings, list):
            row["validation_warnings"] = " | ".join(
                warning.get("message", str(warning))
                if isinstance(warning, dict)
                else str(warning)
                for warning in warnings
            )

            row["warning_severity"] = ", ".join(sorted({
                warning.get("severity", "unknown")
                for warning in warnings
                if isinstance(warning, dict)
            }))
        else:
            row["validation_warnings"] = str(warnings)
            row["warning_severity"] = "unknown"

        display_data.append(row)

    df = pd.DataFrame(display_data)

    return dash_table.DataTable(
        data=df.to_dict("records"),
        columns=[
            {"name": col.replace("_", " ").title(), "id": col}
            for col in df.columns
        ],
        page_size=page_size,
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#E8F0EB",
            "fontWeight": "bold",
            "border": "none",
            "padding": "12px",
        },
        style_cell={
            "textAlign": "left",
            "padding": "10px",
            "minWidth": "100px",
            "maxWidth": "320px",
            "whiteSpace": "normal",
            "height": "auto",
            "fontFamily": "Arial",
            "fontSize": "13px",
            "border": "1px solid #EDF1EE",
        },
        style_data_conditional=[
            {
                "if": {"row_index": "odd"},
                "backgroundColor": "#FAFCFB",
            },
            {
                "if": {
                    "filter_query": '{data_quality} = "high_risk"',
                    "column_id": "data_quality",
                },
                "backgroundColor": "#FDE8E7",
                "color": "#B42318",
                "fontWeight": "bold",
            },
            {
                "if": {
                    "filter_query": '{warning_severity} contains "high"',
                    "column_id": "warning_severity",
                },
                "backgroundColor": "#FDE8E7",
                "color": "#B42318",
                "fontWeight": "bold",
            },
        ],
    )


def make_compact_chat_table(data, page_size=10):
    """Display only relevant fields in AI Chat source records."""

    if not data:
        return dbc.Alert("No records returned.", color="light")

    display_data = []

    for item in data:
        warnings = item.get("validation_warnings", [])

        if isinstance(warnings, list):
            warning_text = " | ".join(
                (
                    f"[{warning.get('severity', 'unknown').upper()}] "
                    f"{warning.get('message') or warning.get('code', 'Warning')}"
                )
                if isinstance(warning, dict)
                else str(warning)
                for warning in warnings
            )
        else:
            warning_text = str(warnings) if warnings else ""

        display_data.append({
            "match": item.get("match", "N/A"),
            "player": item.get("player", "N/A"),
            "event": item.get("event", "N/A"),
            "runs": item.get("runs", "N/A"),
            "validation_warnings": warning_text or "None",
        })

    df = pd.DataFrame(display_data)

    return dash_table.DataTable(
        data=df.to_dict("records"),
        columns=[
            {"name": "Match ID", "id": "match"},
            {"name": "Player", "id": "player"},
            {"name": "Event", "id": "event"},
            {"name": "Runs", "id": "runs"},
            {"name": "Validation Warnings", "id": "validation_warnings"},
        ],
        page_size=page_size,
        sort_action="native",
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#E8F0EB",
            "fontWeight": "bold",
            "border": "none",
            "padding": "12px",
        },
        style_cell={
            "textAlign": "left",
            "padding": "10px",
            "minWidth": "100px",
            "maxWidth": "320px",
            "whiteSpace": "normal",
            "height": "auto",
            "backgroundColor": "#FFFFFF",
            "color": "#26332B",
        },
    )


# --------------------------------------------------
# Sidebar and top bar
# --------------------------------------------------

sidebar = html.Div([
    html.Div([
        html.Div("🏏", className="brand-icon"),
        html.Div([
            html.Div("CRICKET", className="brand-overline"),
            html.Div("INTELLIGENCE", className="brand-name"),
        ]),
    ], className="brand"),

    html.Div("WORKSPACE", className="nav-heading"),

    dbc.Nav([
        dbc.NavLink("▦   Overview", href="/", active="exact"),
        dbc.NavLink("⌕   Semantic Search", href="/search", active="exact"),
        dbc.NavLink("✦   AI Chat", href="/chat", active="exact"),
        dbc.NavLink("▥   Dataset Statistics", href="/statistics",
                    active="exact"),
    ], vertical=True, pills=True, className="side-nav"),

    html.Div(className="sidebar-spacer"),

    html.Div([
        html.Div("SYSTEM STATUS", className="nav-heading"),
        html.Div("Checking Django API...", id="sidebar-api-status",
                 className="status-line"),
        html.Div("Checking Qdrant...", id="sidebar-qdrant-status",
                 className="status-line"),
        html.Div("Django · Qdrant · Ollama", className="sidebar-caption"),
    ], className="sidebar-status"),
], className="sidebar")


topbar = html.Div([
    html.Div([
        html.Div("CRICKET LOG / AI WORKSPACE", className="breadcrumb"),
        html.Div("Overview", id="topbar-title", className="topbar-title"),
    ]),
    dbc.Button(
        "↻  Refresh status",
        id="refresh-status",
        color="light",
        outline=True,
        size="sm",
    ),
], className="topbar")


# --------------------------------------------------
# Page 1: Overview
# --------------------------------------------------

overview_page = html.Div([
    html.Div([
        html.Div([
            html.Div("CRICKET DATA · SEMANTIC INTELLIGENCE",
                     className="hero-kicker"),
            html.H1("Every cricket record,\none intelligent search.",
                    className="hero-title"),
            html.P(
                "Explore match logs, discover relevant events using "
                "natural language, and ask questions grounded in retrieved "
                "records.",
                className="hero-description",
            ),
            dbc.Button("Start searching  →", href="/search",
                       color="light", className="hero-button"),
        ], className="hero-content"),
        html.Div("🏏", className="hero-ball"),
    ], className="hero"),

    dbc.Row([
        dbc.Col(card("INDEXED RECORDS", "500",
                     "Records in the prepared dataset"),
                 md=4, className="mb-3"),
        dbc.Col(card("VECTOR DATABASE", "Qdrant",
                     "Semantic retrieval"),
                 md=4, className="mb-3"),
        dbc.Col(card("LANGUAGE MODEL", "Llama 3.2",
                     "RAG answer generation"),
                 md=4, className="mb-3"),
    ], className="mt-4"),

    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("QUICK ACTION", className="section-kicker"),
            html.H4("Search cricket logs", className="section-title"),
            html.P(
                "Find records by meaning or filter using an exact event label.",
                className="section-copy",
            ),
            dbc.Button("Open semantic search", href="/search",
                       color="success"),
        ]), className="content-card h-100"), md=6, className="mb-3"),

        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("RETRIEVAL-AUGMENTED GENERATION",
                     className="section-kicker"),
            html.H4("Ask the cricket assistant", className="section-title"),
            html.P(
                "Ask a question and inspect the source records used for "
                "the answer.",
                className="section-copy",
            ),
            dbc.Button("Open AI chat", href="/chat", color="success"),
        ]), className="content-card h-100"), md=6, className="mb-3"),
    ], className="mt-2"),
], className="page-content")


# --------------------------------------------------
# Page 2: Semantic Search
# --------------------------------------------------

search_page = html.Div([
    page_heading(
        "Semantic Search",
        "Find relevant cricket records using natural language "
        "or exact event filters.",
    ),

    dbc.Card(dbc.CardBody([
        dbc.Label("Search method", className="form-label-custom"),
        dbc.RadioItems(
            id="search-mode",
            options=[
                {"label": "Semantic search", "value": "semantic"},
                {"label": "Exact event", "value": "exact"},
            ],
            value="semantic",
            inline=True,
            className="mb-3",
        ),

        dbc.Label("Your query", className="form-label-custom"),
        dbc.Input(
            id="search-query",
            placeholder="e.g. Show me players who were given out LBW",
            type="text",
            className="mb-3",
        ),

        dbc.Row([
            dbc.Col([
                dbc.Label("Maximum results", className="form-label-custom"),
                dcc.Dropdown(
                    id="search-limit",
                    options=[{"label": str(n), "value": n}
                             for n in [5, 10, 15, 20, 50, 100]],
                    value=5,
                    clearable=False,
                ),
            ], md=4),

            dbc.Col([
                html.Div(style={"height": "27px"}),
                dbc.Button(
                    "⌕  Search records",
                    id="search-button",
                    color="success",
                    className="w-100",
                ),
            ], md=4),
        ]),
    ]), className="content-card mb-4"),

    html.Div(id="search-message", className="mb-3"),
    html.Div(id="search-summary", className="mb-3"),
    html.Div(id="search-results"),
    html.Div(id="search-download-container", className="mt-3"),
], className="page-content")


# --------------------------------------------------
# Page 3: AI Chat
# --------------------------------------------------

chat_page = html.Div([
    page_heading(
        "AI Cricket Assistant",
        "Ask questions and review the records retrieved to support each answer.",
    ),

    dbc.Card(dbc.CardBody([
        html.Div("YOUR QUESTION", className="section-kicker"),
        dbc.Label("What would you like to know?",
                  className="form-label-custom"),
        dbc.Textarea(
            id="chat-question",
            placeholder="e.g. Summarize the records involving LBW decisions.",
            style={"minHeight": "120px"},
            className="mb-3",
        ),
        dbc.Button("✦  Generate answer", id="chat-button", color="success"),
        html.Div(id="chat-message", className="mt-3"),
    ]), className="content-card mb-4"),

    html.Div(id="chat-answer"),
    html.Div(id="chat-sources", className="mt-4"),
], className="page-content")


# --------------------------------------------------
# Page 4: Dataset Statistics
# --------------------------------------------------

stats_page = html.Div([
    page_heading(
        "Dataset Statistics",
        "Live statistics from the Qdrant vector collection.",
    ),

    dbc.Button("↻  Refresh statistics", id="stats-button",
               color="success", className="mb-4"),
    html.Div(id="stats-message", className="mb-3"),

    dbc.Row([
        dbc.Col(card("TOTAL POINTS", "—", "Stored records"),
                md=4, className="mb-3"),
        dbc.Col(card("INDEXED VECTORS", "—", "Qdrant index status"),
                md=4, className="mb-3"),
        dbc.Col(card("COLLECTION STATUS", "—", "Vector collection"),
                md=4, className="mb-3"),
    ], id="stats-metrics"),

    dbc.Card(dbc.CardBody([
        html.H4("About the collection", className="section-title"),
        html.P(
            "Qdrant stores the vectors and payloads used for semantic "
            "retrieval. The indexed vector count is not necessarily the "
            "same as the total number of stored points.",
            className="section-copy",
        ),
    ]), className="content-card mt-3"),
], className="page-content")


# --------------------------------------------------
# Main application layout
# --------------------------------------------------

app.layout = html.Div([
    dcc.Location(id="url"),
    dcc.Interval(id="status-interval", interval=30_000, n_intervals=0),
    sidebar,

    html.Div([
        topbar,
        html.Main(id="page-content", className="main-content"),
        html.Footer(
            "CRICKET LOG SEMANTIC SEARCH  ·  DJANGO REST  "
            "·  QDRANT  ·  OLLAMA  ·  MCP",
            className="app-footer",
        ),
    ], className="main-panel"),
], className="app-shell")


# --------------------------------------------------
# Navigation callback
# --------------------------------------------------

@callback(
    Output("page-content", "children"),
    Output("topbar-title", "children"),
    Input("url", "pathname"),
)
def route_page(pathname):
    pages = {
        "/": ("Overview", overview_page),
        "/search": ("Semantic Search", search_page),
        "/chat": ("AI Chat", chat_page),
        "/statistics": ("Dataset Statistics", stats_page),
    }

    title, content = pages.get(pathname or "/", pages["/"])
    return content, title


# --------------------------------------------------
# System status callback
# --------------------------------------------------

@callback(
    Output("sidebar-api-status", "children"),
    Output("sidebar-qdrant-status", "children"),
    Input("status-interval", "n_intervals"),
    Input("refresh-status", "n_clicks"),
)
def update_status(n_intervals, refresh_clicks):
    api_ok = get_api_status()
    qdrant_ok = bool(get_qdrant_data())

    api_status = (
        "●  Django API · Online" if api_ok
        else "●  Django API · Offline"
    )
    qdrant_status = (
        "●  Qdrant · Online" if qdrant_ok
        else "●  Qdrant · Offline"
    )

    return api_status, qdrant_status


# --------------------------------------------------
# Semantic search callback
# --------------------------------------------------

@callback(
    Output("search-message", "children"),
    Output("search-summary", "children"),
    Output("search-results", "children"),
    Output("search-download-container", "children"),
    Input("search-button", "n_clicks"),
    State("search-mode", "value"),
    State("search-query", "value"),
    State("search-limit", "value"),
    prevent_initial_call=True,
)
def run_search(n_clicks, mode, query, limit):
    if not query or not query.strip():
        return (
            dbc.Alert("Enter a query or exact event before searching.",
                      color="warning"),
            "", "", "",
        )

    params = {"limit": int(limit or 5)}

    if mode == "semantic":
        params["query"] = query.strip()
    else:
        params["event"] = query.strip()

    try:
        response = requests.get(
            f"{API_BASE_URL}/api/search/",
            params=params,
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()

    except requests.RequestException as exc:
        return (
            dbc.Alert(f"Search request failed: {exc}", color="danger"),
            "", "", "",
        )
    except ValueError:
        return (
            dbc.Alert("The API returned invalid JSON.", color="danger"),
            "", "", "",
        )

    records = result.get("results", [])
    validation = result.get("validation_summary", {})

    records_with_warnings = validation.get(
        "records_with_warnings",
        sum(bool(r.get("validation_warnings")) for r in records),
    )

    high_severity_records = validation.get(
        "records_with_high_severity_warnings",
        sum(
            any(
                isinstance(w, dict) and w.get("severity") == "high"
                for w in r.get("validation_warnings", [])
            )
            for r in records
        ),
    )

    summary = dbc.Alert([
        html.Div(
            f"Returned {len(records)} record(s). "
            f"More results available: "
            f"{'Yes' if result.get('has_more') else 'No'}.",
            className="fw-bold mb-1",
        ),
        html.Div(
            f"Records with validation warnings: {records_with_warnings} "
            f"| Records with high-severity warnings: {high_severity_records}."
        ),
        html.Small(
            "Similarity scores indicate relevance to the query, not factual "
            "accuracy. Warnings flag records for review; they do not "
            "automatically correct or remove data."
        ),
    ], color="warning" if high_severity_records else (
        "success" if records else "light"
    ))

    table = make_table(records)

    download = ""
    if records:
        df = pd.DataFrame(records)
        download = html.A(
            "Download CSV",
            href="data:text/csv;charset=utf-8,"
                 + requests.utils.quote(df.to_csv(index=False)),
            download="cricket_search_results.csv",
            className="btn btn-outline-success",
        )

    return "", summary, table, download


# --------------------------------------------------
# RAG chat callback
# --------------------------------------------------

@callback(
    Output("chat-message", "children"),
    Output("chat-answer", "children"),
    Output("chat-sources", "children"),
    Input("chat-button", "n_clicks"),
    State("chat-question", "value"),
    prevent_initial_call=True,
)
def run_chat(n_clicks, question):
    if not question or not question.strip():
        return (
            dbc.Alert("Enter a question first.", color="warning"),
            "", "",
        )

    try:
        response = requests.post(
            f"{API_BASE_URL}/api/chat/",
            json={"question": question.strip()},
            timeout=240,
        )
        response.raise_for_status()
        result = response.json()

    except requests.Timeout:
        return (
            dbc.Alert("The AI response timed out. Please try again.",
                      color="warning"),
            "", "",
        )
    except requests.RequestException as exc:
        return (
            dbc.Alert(f"Chat request failed: {exc}", color="danger"),
            "", "",
        )
    except ValueError:
        return (
            dbc.Alert("The API returned invalid JSON.", color="danger"),
            "", "",
        )

    answer = result.get("answer", "No answer returned.")
    sources = result.get("sources", [])

    answer_component = dbc.Card(dbc.CardBody([
        html.Div("GENERATED ANSWER", className="section-kicker"),
        dcc.Markdown(answer),
    ]), className="content-card")

    if sources:
        source_component = html.Div([
            html.H4("Retrieved source records", className="section-title"),
            make_compact_chat_table(sources),
        ])
    else:
        source_component = dbc.Alert(
            "No source records were returned.", color="light"
        )

    return "", answer_component, source_component


# --------------------------------------------------
# Dataset statistics callback
# --------------------------------------------------

@callback(
    Output("stats-message", "children"),
    Output("stats-metrics", "children"),
    Input("stats-button", "n_clicks"),
    prevent_initial_call=True,
)
def refresh_statistics(n_clicks):
    data = get_qdrant_data()

    if not data:
        return (
            dbc.Alert("Could not connect to Qdrant.", color="danger"),
            no_update,
        )

    points = data.get("points_count")
    vectors = data.get("indexed_vectors_count")
    status = data.get("status", "Unknown")

    metrics = dbc.Row([
        dbc.Col(card("TOTAL POINTS",
                     points if points is not None else "Unknown",
                     "Stored records"),
                md=4, className="mb-3"),
        dbc.Col(card("INDEXED VECTORS",
                     vectors if vectors is not None else "Unknown",
                     "Qdrant index status"),
                md=4, className="mb-3"),
        dbc.Col(card("COLLECTION STATUS",
                     str(status).title(),
                     "Vector collection",
                     GREEN if status == "green" else "#B54708"),
                md=4, className="mb-3"),
    ])

    return (
        dbc.Alert("Statistics refreshed from Qdrant.", color="success"),
        metrics,
    )


# --------------------------------------------------
# Start the application
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=8050,
    )
