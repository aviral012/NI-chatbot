"""
MA Provider Network Assistant — Streamlit App
==============================================
Single-file Streamlit chatbot. Wires router + NPI agent.

Run locally:
    streamlit run app.py

Share with team (same WiFi):
    streamlit run app.py --server.address 0.0.0.0 --server.port 8501
    Share: http://YOUR_IP:8501
"""

import os
import sys
import logging
import importlib
import importlib.util
from pathlib import Path

import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Page config — must be first Streamlit call
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title = "MA Provider Network Assistant",
    page_icon  = "🏥",
    layout     = "wide",
    initial_sidebar_state = "expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.resolve()
ROUTER_DIR = BASE_DIR / "router_standalone"
NPI_DIR    = BASE_DIR / "npi_search_agent"
DATA_DIR   = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
API_KEY    = os.getenv("OPENAI_API_KEY", "")
PROVIDER   = os.getenv("LLM_PROVIDER", "openai")
MODEL      = os.getenv("OPENAI_MODEL",  "gpt-4o")


# ─────────────────────────────────────────────────────────────────────────────
# importlib loader helpers (same isolation approach as server.py)
# ─────────────────────────────────────────────────────────────────────────────
def load_package(package_name: str, package_dir: Path):
    init = package_dir / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        package_name, str(init),
        submodule_search_locations=[str(package_dir)],
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__path__    = [str(package_dir)]
    mod.__package__ = package_name
    sys.modules[package_name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_module_under(package_name: str, package_dir: Path, mod_name: str):
    full_name = f"{package_name}.{mod_name}"
    mod_path  = package_dir / f"{mod_name}.py"
    spec = importlib.util.spec_from_file_location(
        full_name, str(mod_path),
        submodule_search_locations=[str(package_dir)],
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = package_name
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ─────────────────────────────────────────────────────────────────────────────
# Load agents — cached so they only load once per session
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading agents...")
def load_agents(api_key: str, provider: str, model: str, data_dir: str):
    errors = []

    # Validate folders
    for label, path in [
        ("router_standalone/", ROUTER_DIR),
        ("npi_search_agent/",  NPI_DIR),
        ("data/",              Path(data_dir)),
    ]:
        if not Path(path).exists():
            errors.append(f"Missing folder: {label} (expected at {path})")
    if errors:
        return None, None, errors

    # Load router
    try:
        load_package("router_core",        ROUTER_DIR / "core")
        load_package("router_core.router", ROUTER_DIR / "core" / "router")
        for m in ["product_registry", "router_agent", "response_builder", "orchestrator"]:
            load_module_under("router_core.router", ROUTER_DIR / "core" / "router", m)
        Orchestrator = sys.modules["router_core.router.orchestrator"].Orchestrator
    except Exception as e:
        return None, None, [f"Router load failed: {e}"]

    # Load NPI agent
    try:
        load_package("npi_core", NPI_DIR / "core")
        for m in ["schema", "intent_parser", "query_engine", "response_synthesiser", "npi_agent"]:
            load_module_under("npi_core", NPI_DIR / "core", m)
        NpiSearchAgent = sys.modules["npi_core.npi_agent"].NpiSearchAgent
    except Exception as e:
        return None, None, [f"NPI agent load failed: {e}"]

    # Instantiate
    try:
        npi = NpiSearchAgent(
            provider=provider, api_key=api_key,
            openai_model=model, data_dir=data_dir, max_rows=15,
        )
        bot = Orchestrator(
            provider=provider, api_key=api_key, openai_model=model,
            npi_agent=lambda query, decision: npi.search(query),
        )
        return bot, npi, []
    except Exception as e:
        return None, None, [f"Agent init failed: {e}"]


# ─────────────────────────────────────────────────────────────────────────────
# Session state init
# ─────────────────────────────────────────────────────────────────────────────
if "messages"     not in st.session_state: st.session_state.messages     = []
if "debug_turns"  not in st.session_state: st.session_state.debug_turns  = []
if "turn_count"   not in st.session_state: st.session_state.turn_count   = 0


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏥 MA Network Assistant")
    st.caption("Router + NPI Search Agent")
    st.divider()

    # API key input if not set via env
    key_input = API_KEY
    if not API_KEY:
        key_input = st.text_input(
            "OpenAI API Key", type="password",
            placeholder="sk-...",
            help="Set OPENAI_API_KEY in environment or enter here"
        )

    st.divider()
    st.markdown("**Sample prompts**")

    PROMPTS = [
        ("🔍 Answer", "Find highly rated PCPs in Cook County Illinois not contracted with Humana"),
        ("🔍 Answer", "Show cardiologists in Ohio not in UnitedHealthcare ranked by quality"),
        ("🔍 Answer", "Find General Practice providers contracted with Humana in Illinois"),
        ("🔍 Answer", "Highly rated nephrologists in Texas"),
        ("📖 Guide",  "How do I filter providers by specialty in the NPI Search dashboard?"),
        ("📖 Guide",  "Which dashboard should I use to find network gaps?"),
        ("💡 Strategy", "We are expanding into rural Ohio — how should we build the network?"),
        ("💡 Strategy", "Our cardiology network is weak in the southeast. CMS filing in 3 months. Where do we start?"),
        ("❓ Clarify", "Find me some providers"),
        ("🚫 Out of scope", "How do I process a claims adjudication dispute?"),
    ]

    for tag, prompt in PROMPTS:
        if st.button(f"{tag}", key=prompt, use_container_width=True, help=prompt):
            st.session_state["prefill"] = prompt

    st.divider()

    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages    = []
        st.session_state.debug_turns = []
        st.session_state.turn_count  = 0
        st.rerun()

    st.markdown(f"""
    <small>
    Provider: <code>{PROVIDER}</code><br>
    Model: <code>{MODEL}</code><br>
    Data: <code>{DATA_DIR.name}</code>
    </small>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Load agents
# ─────────────────────────────────────────────────────────────────────────────
active_key = key_input if key_input else API_KEY

if not active_key:
    st.warning("⚠️ Enter your OpenAI API key in the sidebar to get started.")
    st.stop()

bot, npi_agent, load_errors = load_agents(active_key, PROVIDER, MODEL, str(DATA_DIR))

if load_errors:
    st.error("**Failed to load agents:**")
    for e in load_errors:
        st.code(e)
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Main layout — chat on left, debug on right
# ─────────────────────────────────────────────────────────────────────────────
col_chat, col_debug = st.columns([2, 1])

# ── MODE BADGE COLOURS ────────────────────────────────────────────────────────
MODE_COLOURS = {
    "answer":       "🟦",
    "guide":        "🟩",
    "strategy":     "🟨",
    "out_of_scope": "🟥",
    "unknown":      "⬜",
}

# ─────────────────────────────────────────────────────────────────────────────
# Chat column
# ─────────────────────────────────────────────────────────────────────────────
with col_chat:
    st.markdown("### 💬 Chat")

    # Render message history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and "meta" in msg:
                m = msg["meta"]
                mode    = m.get("mode", "unknown")
                conf    = int(m.get("confidence", 0) * 100)
                products = ", ".join(m.get("products", [])) or "—"
                clarify  = " ⏳ awaiting detail" if m.get("awaiting_clarification") else ""
                colour   = MODE_COLOURS.get(mode, "⬜")
                st.caption(
                    f"{colour} **{mode.replace('_',' ')}** &nbsp;·&nbsp; "
                    f"confidence: **{conf}%** &nbsp;·&nbsp; "
                    f"products: `{products}`{clarify}"
                )

    # Pre-fill from sidebar prompt click
    prefill = st.session_state.pop("prefill", "")

    # Chat input
    user_input = st.chat_input(
        "Ask about providers, networks, or strategy...",
    ) or (prefill if prefill else None)

    if user_input:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Get response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Also grab debug info
                    try:
                        debug_intent = npi_agent.debug_intent(user_input)
                        debug_rows   = npi_agent.debug_query(user_input)
                        npi_debug    = {
                            "intent": {
                                "hwai_spec_descs":  debug_intent.hwai_spec_descs,
                                "hwai_spec_codes":  debug_intent.hwai_spec_codes,
                                "new_flags":        debug_intent.new_flags,
                                "geo":              debug_intent.geo.__dict__,
                                "include_carriers": debug_intent.include_carriers,
                                "exclude_carriers": debug_intent.exclude_carriers,
                                "rank_by":          debug_intent.rank_by,
                                "rank_direction":   debug_intent.rank_direction,
                                "score_thresholds": debug_intent.score_thresholds,
                            },
                            "row_count": len(debug_rows),
                            "sample":    debug_rows[:3],
                        }
                    except Exception as de:
                        npi_debug = {"error": str(de)}

                    # Full chat response
                    response = bot.chat(user_input)
                    d = bot.last_decision

                    meta = {
                        "mode":                   d.mode.value if d else "unknown",
                        "products":               d.product_ids if d else [],
                        "confidence":             round(d.confidence, 2) if d else 0.0,
                        "awaiting_clarification": bot.awaiting_clarification,
                        "reasoning":              getattr(d, "reasoning", ""),
                    }

                except Exception as e:
                    response = f"❌ Error: {e}"
                    meta     = {"mode": "unknown", "products": [], "confidence": 0.0,
                                "awaiting_clarification": False, "reasoning": ""}
                    npi_debug = {}

            st.markdown(response)
            mode    = meta.get("mode", "unknown")
            conf    = int(meta.get("confidence", 0) * 100)
            products = ", ".join(meta.get("products", [])) or "—"
            clarify  = " ⏳ awaiting detail" if meta.get("awaiting_clarification") else ""
            colour   = MODE_COLOURS.get(mode, "⬜")
            st.caption(
                f"{colour} **{mode.replace('_',' ')}** &nbsp;·&nbsp; "
                f"confidence: **{conf}%** &nbsp;·&nbsp; "
                f"products: `{products}`{clarify}"
            )

        # Save to history
        st.session_state.messages.append({
            "role": "assistant", "content": response, "meta": meta
        })

        # Save debug turn
        st.session_state.turn_count += 1
        st.session_state.debug_turns.append({
            "turn":      st.session_state.turn_count,
            "query":     user_input,
            "meta":      meta,
            "npi_debug": npi_debug,
        })

        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Debug column
# ─────────────────────────────────────────────────────────────────────────────
with col_debug:
    st.markdown("### 🔍 Debug")

    if not st.session_state.debug_turns:
        st.caption("Send a message to see debug details here.")
    else:
        # Show most recent turn first
        for turn_data in reversed(st.session_state.debug_turns):
            t    = turn_data["turn"]
            meta = turn_data["meta"]
            nd   = turn_data.get("npi_debug", {})
            mode = meta.get("mode", "unknown")
            conf = int(meta.get("confidence", 0) * 100)

            with st.expander(
                f"Turn {t} — {MODE_COLOURS.get(mode,'⬜')} {mode.replace('_',' ')}  ({conf}%)",
                expanded=(t == st.session_state.turn_count),
            ):
                # ── Routing ──
                st.markdown("**Routing**")
                c1, c2 = st.columns(2)
                c1.metric("Mode",       mode.replace("_", " ").title())
                c2.metric("Confidence", f"{conf}%")

                products = meta.get("products", [])
                if products:
                    st.markdown(f"Products: {', '.join(f'`{p}`' for p in products)}")

                reasoning = meta.get("reasoning", "")
                if reasoning:
                    st.caption(f"💭 {reasoning}")

                if meta.get("awaiting_clarification"):
                    st.warning("⏳ Awaiting clarification from user")

                st.divider()

                # ── NPI Intent ──
                st.markdown("**NPI Intent parsed**")
                if "error" in nd:
                    st.error(nd["error"])
                elif "intent" in nd:
                    intent = nd["intent"]
                    fields = {
                        "New flags":        intent.get("new_flags") or "—",
                        "HWAI specialties": intent.get("hwai_spec_descs") or "—",
                        "HWAI codes":       intent.get("hwai_spec_codes") or "—",
                        "State":            intent.get("geo", {}).get("state") or "—",
                        "County":           intent.get("geo", {}).get("county_name") or "—",
                        "City":             intent.get("geo", {}).get("city") or "—",
                        "Incl. carriers":   intent.get("include_carriers") or "—",
                        "Excl. carriers":   intent.get("exclude_carriers") or "—",
                        "Rank by":          intent.get("rank_by", "—"),
                        "Direction":        intent.get("rank_direction", "—"),
                    }
                    for k, v in fields.items():
                        if v != "—":
                            st.markdown(f"- **{k}:** `{v}`")

                    st.divider()

                    # ── Row count ──
                    row_count = nd.get("row_count", 0)
                    if row_count == 0:
                        st.error(f"⚠️ DuckDB returned 0 rows — check specialty files in data/specialties/")
                    else:
                        st.success(f"✅ DuckDB returned **{row_count}** providers")

                    # ── Sample rows ──
                    sample = nd.get("sample", [])
                    if sample:
                        st.markdown("**Sample rows (first 3)**")
                        for i, row in enumerate(sample, 1):
                            with st.expander(f"Row {i} — {row.get('presentation_name', 'N/A')}"):
                                display = {
                                    k: v for k, v in row.items()
                                    if v is not None
                                    and k not in ("latitude", "longitude",
                                                  "FIPS State County Code",
                                                  "Address First Line",
                                                  "Address Second Line")
                                }
                                for k, v in display.items():
                                    st.markdown(f"**{k}:** {v}")
