"""
MA Provider Network Assistant — Combined Server
================================================
Uses importlib to load each agent in complete isolation.
Avoids the core/ package name collision between all three agents.

Agents loaded:
  router_core      → router_standalone/core/router/
  npi_core         → npi_search_agent/core/
  pnc_core         → pnc_agent/core/
"""

import os
import sys
import logging
import importlib
import importlib.util
from pathlib import Path

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR   = Path(__file__).parent.resolve()
ROUTER_DIR = BASE_DIR / "router_standalone"
NPI_DIR    = BASE_DIR / "npi_search_agent"
PNC_DIR    = BASE_DIR / "pnc_agent"
DATA_DIR   = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))


# ── Validate required folders ─────────────────────────────────────────────────
missing = []
for label, path in [
    ("router_standalone/", ROUTER_DIR),
    ("npi_search_agent/",  NPI_DIR),
    ("pnc_agent/",         PNC_DIR),
    ("data/",              DATA_DIR),
]:
    if not path.exists():
        missing.append(f"  MISSING: {label}  (expected at {path})")

if missing:
    print("\n  ERROR: Required folders not found:")
    for m in missing: print(m)
    sys.exit(1)


# ── importlib helpers ─────────────────────────────────────────────────────────
def load_package(package_name: str, package_dir: Path):
    init = package_dir / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        package_name,
        str(init),
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
    if not mod_path.exists():
        raise FileNotFoundError(f"Missing: {mod_path}")
    spec = importlib.util.spec_from_file_location(
        full_name, str(mod_path),
        submodule_search_locations=[str(package_dir)],
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = package_name
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── Load router ───────────────────────────────────────────────────────────────
try:
    load_package("router_core",        ROUTER_DIR / "core")
    load_package("router_core.router", ROUTER_DIR / "core" / "router")
    for m in ["product_registry", "router_agent", "response_builder", "orchestrator"]:
        load_module_under("router_core.router", ROUTER_DIR / "core" / "router", m)
    Orchestrator = sys.modules["router_core.router.orchestrator"].Orchestrator
    logger.info("Router agent loaded OK")
except Exception as e:
    print(f"\n  ERROR loading router agent: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)


# ── Load NPI Search agent ─────────────────────────────────────────────────────
try:
    load_package("npi_core", NPI_DIR / "core")
    for m in ["schema", "intent_parser", "query_engine", "response_synthesiser", "npi_agent"]:
        load_module_under("npi_core", NPI_DIR / "core", m)
    NpiSearchAgent = sys.modules["npi_core.npi_agent"].NpiSearchAgent
    logger.info("NPI Search agent loaded OK")
except Exception as e:
    print(f"\n  ERROR loading NPI Search agent: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)


# ── Load PNC agent ────────────────────────────────────────────────────────────
try:
    load_package("pnc_core", PNC_DIR / "core")
    for m in ["schema", "intent_parser", "query_engine", "response_synthesiser", "pnc_agent"]:
        load_module_under("pnc_core", PNC_DIR / "core", m)
    PncAgent = sys.modules["pnc_core.pnc_agent"].PncAgent
    logger.info("PNC agent loaded OK")
except Exception as e:
    print(f"\n  ERROR loading PNC agent: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)


# ── LLM config ────────────────────────────────────────────────────────────────
PROVIDER = os.getenv("LLM_PROVIDER", "openai")
MODEL    = os.getenv("OPENAI_MODEL",  "gpt-4o")
API_KEY  = (
    os.getenv("OPENAI_API_KEY")    if PROVIDER == "openai"    else
    os.getenv("ANTHROPIC_API_KEY") if PROVIDER == "anthropic" else None
)

if not API_KEY:
    print(f"\n  ERROR: API key not set. Open start.bat and set OPENAI_API_KEY=sk-...\n")
    sys.exit(1)


# ── Instantiate NPI Search agent ──────────────────────────────────────────────
try:
    npi_agent = NpiSearchAgent(
        provider     = PROVIDER,
        api_key      = API_KEY,
        openai_model = MODEL,
        data_dir     = str(DATA_DIR),
        max_rows     = 15,
    )
    logger.info("NPI Search agent ready — data=%s", DATA_DIR)
except Exception as e:
    print(f"\n  ERROR: Failed to start NPI Search agent: {e}\n")
    import traceback; traceback.print_exc()
    sys.exit(1)


# ── Instantiate PNC agent ─────────────────────────────────────────────────────
try:
    pnc_agent = PncAgent(
        provider     = PROVIDER,
        api_key      = API_KEY,
        openai_model = MODEL,
        data_dir     = str(DATA_DIR),
    )
    logger.info("PNC agent ready — data=%s", DATA_DIR / "pnc")
except Exception as e:
    print(f"\n  ERROR: Failed to start PNC agent: {e}\n")
    import traceback; traceback.print_exc()
    sys.exit(1)


# ── Instantiate Router with both agents wired in ──────────────────────────────
try:
    bot = Orchestrator(
        provider     = PROVIDER,
        api_key      = API_KEY,
        openai_model = MODEL,
        npi_agent    = lambda query, decision: npi_agent.search(query),
        pnc_agent    = lambda query, decision: pnc_agent.compare(query),
    )
    logger.info("Router ready — npi_agent=live  pnc_agent=live")
except Exception as e:
    print(f"\n  ERROR: Failed to start Router: {e}\n")
    import traceback; traceback.print_exc()
    sys.exit(1)


# ── FastAPI ───────────────────────────────────────────────────────────────────
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="MA Provider Network Assistant", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_methods = ["*"],
    allow_headers = ["*"],
)


class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response:               str
    mode:                   str
    products:               list[str]
    confidence:             float
    awaiting_clarification: bool

class DebugRequest(BaseModel):
    message: str


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {
        "status":    "ok",
        "version":   "3.0.0",
        "provider":  PROVIDER,
        "model":     MODEL,
        "npi_agent": "live",
        "pnc_agent": "live",
        "data_dir":  str(DATA_DIR),
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(400, "Message cannot be empty.")
    try:
        response_text = bot.chat(req.message)
    except Exception as e:
        logger.exception("Chat error")
        raise HTTPException(500, str(e))
    d = bot.last_decision
    return ChatResponse(
        response               = response_text,
        mode                   = d.mode.value if d else "unknown",
        products               = d.product_ids if d else [],
        confidence             = round(d.confidence, 2) if d else 0.0,
        awaiting_clarification = bot.awaiting_clarification,
    )


@app.post("/api/chat/reset")
def reset():
    bot.clear()
    return {"status": "ok"}


@app.post("/api/debug/route")
def debug_route(req: DebugRequest):
    """Routing decision only — no data query. Fast and cheap."""
    try:
        d = bot.debug_route(req.message)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {
        "mode":           d.mode.value,
        "product_ids":    d.product_ids,
        "confidence":     round(d.confidence, 2),
        "reasoning":      d.reasoning,
        "clarify_needed": d.clarify_needed,
        "clarify_prompt": d.clarify_prompt,
        "missing_fields": d.missing_fields,
    }


@app.post("/api/debug/npi")
def debug_npi(req: DebugRequest):
    """NPI intent + DuckDB rows — no narration. Use to verify parquet data."""
    try:
        intent = npi_agent.debug_intent(req.message)
        rows   = npi_agent.debug_query(req.message)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {
        "intent": {
            "is_hospital":      intent.is_hospital,
            "hwai_spec_descs":  intent.hwai_spec_descs,
            "hwai_spec_codes":  intent.hwai_spec_codes,
            "new_flags":        intent.new_flags,
            "geo":              intent.geo.__dict__,
            "include_carriers": intent.include_carriers,
            "exclude_carriers": intent.exclude_carriers,
            "rank_by":          intent.rank_by,
            "rank_direction":   intent.rank_direction,
            "score_thresholds": intent.score_thresholds,
            "limit":            intent.limit,
        },
        "row_count": len(rows),
        "sample":    rows[:5],
    }


@app.post("/api/debug/pnc")
def debug_pnc(req: DebugRequest):
    """PNC intent + query result — no narration. Use to verify CSV data."""
    try:
        intent = pnc_agent.debug_intent(req.message)
        result = pnc_agent.debug_query(req.message)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {
        "intent": {
            "comparison_type": intent.comparison_type,
            "payor_a":         intent.payor_a,
            "payor_b":         intent.payor_b,
            "plan_type":       intent.plan_type,
            "specialty":       intent.specialty,
            "provider_type":   intent.provider_type,
        },
        "result": {
            "comparison_type":    result.comparison_type,
            "count_a":            result.count_a,
            "count_b":            result.count_b,
            "ppo_count_a":        result.ppo_count_a,
            "ppo_count_b":        result.ppo_count_b,
            "hmo_count_a":        result.hmo_count_a,
            "hmo_count_b":        result.hmo_count_b,
            "pcp_count_a":        result.pcp_count_a,
            "pcp_count_b":        result.pcp_count_b,
            "specialist_count_a": result.specialist_count_a,
            "specialist_count_b": result.specialist_count_b,
            "hospital_count_a":   result.hospital_count_a,
            "hospital_count_b":   result.hospital_count_b,
            "total_providers":    result.total_providers,
            "providers_sample":   result.providers[:3],
        },
    }


@app.get("/")
def index():
    html = BASE_DIR / "frontend" / "index.html"
    if not html.exists():
        raise HTTPException(404, "frontend/index.html not found")
    return FileResponse(str(html))


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    logger.info("Starting on http://%s:%s", host, port)
    uvicorn.run("server:app", host=host, port=port, reload=False)
