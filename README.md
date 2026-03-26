# MA Provider Network Assistant — Combined App

Router agent + NPI Search agent + Frontend UI in one runnable app.

---

## Folder structure required

```
ma_combined_app/
├── server.py                      ← combined FastAPI server
├── start.bat                      ← Windows launcher
├── requirements.txt
├── frontend/
│   └── index.html                 ← web UI
│
├── router_standalone/             ← copy your router folder here
│   └── core/
│       └── router/
│           ├── __init__.py
│           ├── orchestrator.py
│           ├── router_agent.py
│           ├── response_builder.py
│           └── product_registry.py
│
├── npi_search_agent/              ← copy your NPI agent folder here
│   └── core/
│       ├── __init__.py
│       ├── npi_agent.py
│       ├── intent_parser.py
│       ├── query_engine.py
│       ├── response_synthesiser.py
│       └── schema.py
│
└── data/                          ← your parquet files go here
    ├── hwai_specialty_mapping.parquet
    ├── npi_scores.parquet
    └── specialties/
        ├── cardiovascular_disease.parquet
        ├── family_practice.parquet
        └── ... (all specialty files)
```

---

## Step-by-step setup

### Step 1 — Copy your agent folders
Copy `router_standalone/` and `npi_search_agent/` into this folder.

### Step 2 — Copy your data
Place your parquet files into `data/`:
- `data/hwai_specialty_mapping.parquet`
- `data/npi_scores.parquet`
- `data/specialties/*.parquet`

If you only have `HWAI_specialty_mapping.xlsx`, convert it first:
```cmd
cd npi_search_agent
python data_prep.py --mapping HWAI_specialty_mapping.xlsx --data-dir ..\data
```

### Step 3 — Install dependencies
```cmd
cd ma_combined_app
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Step 4 — Edit start.bat
Open `start.bat` in Notepad. Set:
```bat
set OPENAI_API_KEY=sk-proj-...
set DATA_DIR=data
```

### Step 5 — Launch
```cmd
start.bat
```

Open `http://localhost:8000` in your browser.

### Step 6 — Share with team
Run `ipconfig` in a new terminal, find your IPv4 address.
Share `http://YOUR_IP:8000` with anyone on the same network.

If teammates can't connect, run once in admin terminal:
```cmd
netsh advfirewall firewall add rule name="MA Router" dir=in action=allow protocol=TCP localport=8000
```

---

## How the two agents connect

```
User query
    │
    ▼
Router agent classifies query
    │
    ├── mode=answer + product=npi_search
    │       │
    │       ▼
    │   NPI Search agent
    │   Step 1: GPT parses query → NpiSearchIntent
    │   Step 2: DuckDB queries parquet files → rows
    │   Step 3: GPT narrates rows → response string
    │       │
    │       ▼
    │   Response returned to router
    │
    ├── mode=guide    → router explains which dashboard to use
    ├── mode=strategy → router gives analytical approach
    └── mode=out_of_scope → router declines cleanly
```

---

## Token cost per query

| Query type | LLM calls | Approx cost |
|-----------|-----------|-------------|
| NPI Search (answer) | 3 calls: router + parse + narrate | ~$0.013 |
| Guide / Strategy | 2 calls: router + response | ~$0.003 |
| Out of scope | 2 calls: router + decline | ~$0.002 |
| Clarification | 1 call: router only | ~$0.001 |
