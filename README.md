<div align="center">

# 🗣️ ➜ 🗄️ nl2sql-toolkit

**Ask your database a question in plain English. Get back real SQL, run against your real database.**

CLI + embeddable Python SDK for turning natural language into SQL — for **PostgreSQL, MySQL, SQL Server, and SQLite** — powered by any LLM via [OpenRouter](https://openrouter.ai).

[![PyPI](https://img.shields.io/badge/pip%20install-nl2sql--toolkit-blue)](#install)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](#install)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](.github/workflows/ci.yml)
[![Databases](https://img.shields.io/badge/works%20with-Postgres%20%7C%20MySQL%20%7C%20SQL%20Server%20%7C%20SQLite-orange)](#connection-strings-for-real-databases)

</div>

---

## Why this exists

Writing throwaway SQL to answer a quick question — *"how many orders did we get last month?"*, *"who are our top 5 customers?"* — is a constant context switch for developers. `nl2sql-toolkit` removes that friction: it introspects your **real, live database schema**, sends your question + schema to an LLM of your choice, and either runs the resulting query immediately (for reads) or shows it to you for approval (for writes).

No vendor lock-in, no proprietary backend — it's a small open-source Python package you drop into your terminal or your own app.

## ✨ Features

- 🔌 **Works with real databases** — PostgreSQL, MySQL/MariaDB, SQL Server, SQLite (via [SQLAlchemy](https://www.sqlalchemy.org/), so any dialect it supports works)
- 🧠 **Bring your own model** — uses your OpenRouter API key, pick GPT, Claude, Gemini, Llama, Qwen, DeepSeek, or anything else on OpenRouter
- 🗺️ **Schema-aware** — automatically introspects tables, columns, types, foreign keys, and sample rows so the model writes accurate, dialect-correct SQL
- 🛡️ **Safe by default** — read queries (`SELECT`) run immediately; write/destructive queries (`INSERT`/`UPDATE`/`DELETE`/`DROP`/`ALTER`) require explicit confirmation; multi-statement injection attempts are rejected outright
- 💻 **Two ways to use it** — a full-featured CLI (`nl2sql ...`) for your terminal/scripts/CI, and a Python SDK (`from nl2sql import NL2SQL`) to embed it as a feature in your own app
- 💬 **Conversational context** — follow-up questions ("now just for Chennai") reuse recent query history
- 🔑 **Local, private config** — saved connection profiles and API keys live in `~/.nl2sql/config.json` (0600 permissions), never sent anywhere except OpenRouter for the LLM call

## 📸 Screenshots

<table>
<tr>
<td width="50%">

**Ask a question, get SQL + results**
<img src="screenshots/04_ask_read_query.png" alt="nl2sql ask - natural language to SQL with results table" width="100%">

</td>
<td width="50%">

**Write queries require confirmation**
<img src="screenshots/05_ask_write_query_blocked.png" alt="nl2sql blocks destructive queries until confirmed" width="100%">

</td>
</tr>
<tr>
<td width="50%">

**Connect to a real database & save the profile**
<img src="screenshots/02_connect_and_list.png" alt="nl2sql connect to PostgreSQL and save profile" width="100%">

</td>
<td width="50%">

**Inspect the live schema**
<img src="screenshots/03_schema.png" alt="nl2sql schema introspection" width="100%">

</td>
</tr>
<tr>
<td width="50%">

**Guard rails against SQL injection**
<img src="screenshots/06_exec_and_safety_guard.png" alt="nl2sql rejects multi-statement SQL" width="100%">

</td>
<td width="50%">

**Embed it as an SDK in your own app**
<img src="screenshots/07_sdk_usage.png" alt="nl2sql Python SDK usage example" width="100%">

</td>
</tr>
</table>

<details>
<summary>See the full CLI help screenshot</summary>
<img src="screenshots/01_cli_help.png" alt="nl2sql --help output" width="70%">
</details>

## 🚀 Quick start

```bash
# 1. Install
pip install nl2sql-toolkit
# with a specific DB driver:
pip install "nl2sql-toolkit[postgres]"   # or [mysql] / [mssql] / [all]

# 2. Point it at your database (any SQLAlchemy connection string)
nl2sql connect "postgresql+psycopg2://user:pass@host:5432/mydb" --save mydb

# 3. Save your OpenRouter API key (get one free at https://openrouter.ai/keys)
nl2sql config set-key sk-or-v1-...

# 4. Ask away
nl2sql ask "show the 5 highest paid employees" --db mydb
```

```
$ nl2sql ask "show the top 2 highest paid employees along with their department name" --db demo

Explanation: Joins employees with departments, orders by salary descending,
             and returns the top 2 highest paid employees.

SELECT e.name, e.salary, d.name AS department_name FROM employees e
JOIN departments d ON e.department_id = d.id ORDER BY e.salary DESC LIMIT 2

┏━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
┃ name         ┃ salary   ┃ department_name ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
│ Vikram Singh │ 105000.0 │ Engineering     │
│ Asha Rao     │ 95000.0  │ Engineering     │
└──────────────┴──────────┴─────────────────┘
2 row(s) returned
```

## 🐍 Use it as a library (embed it in your own app)

```python
from nl2sql import NL2SQL

db = NL2SQL(
    connection_string="postgresql+psycopg2://user:pass@host:5432/mydb",
    api_key="sk-or-v1-...",          # or set OPENROUTER_API_KEY env var
    model="openai/gpt-4o-mini",       # any OpenRouter model id
    allow_write=False,                 # writes are generated but NOT auto-run
)

result = db.ask("top 5 customers by total spend")
print(result.sql)            # the generated SQL — log it, show it, audit it
print(result.explanation)    # one-line plain-English explanation
for row in result.to_dicts():
    print(row)

# Requests that imply a write are held back until you confirm:
r2 = db.ask("delete all test accounts")
if not r2.executed:
    print("Needs human approval:", r2.sql)
    # confirmed = db.execute(r2.sql, confirmed=True)
```

See [`examples/sdk_usage.py`](examples/sdk_usage.py) and
[`examples/flask_plugin_example.py`](examples/flask_plugin_example.py) for a
full example of wiring this into an existing Flask backend as an `/api/ask`
endpoint that your product/team can hit.

## Connection strings for real databases

| Database | Install extra | Example URL |
|---|---|---|
| PostgreSQL | `pip install "nl2sql-toolkit[postgres]"` | `postgresql+psycopg2://user:pass@host:5432/dbname` |
| MySQL / MariaDB | `pip install "nl2sql-toolkit[mysql]"` | `mysql+pymysql://user:pass@host:3306/dbname` |
| SQL Server | `pip install "nl2sql-toolkit[mssql]"` + [ODBC driver](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) | `mssql+pyodbc://user:pass@host:1433/dbname?driver=ODBC+Driver+18+for+SQL+Server` |
| SQLite | built-in | `sqlite:///path/to/file.db` |

## How it works

```
 your question              live schema introspection
      │                              │
      ▼                              ▼
┌─────────────┐   schema + question   ┌──────────────┐
│   nl2sql     │ ─────────────────────▶│  OpenRouter   │
│ (CLI / SDK)  │ ◀───────────────────── │  (any model)  │
└──────┬───────┘   { sql, explanation }└──────────────┘
       │
       ▼ safety check: single statement? read or write?
       │
  ┌────┴─────┐
  │ read?    │──yes──▶ execute immediately, return rows
  └────┬─────┘
       │no (write/destructive)
       ▼
  ask for confirmation ──▶ execute only if approved
```

1. **Connect** — a standard SQLAlchemy connection string (or a saved profile).
2. **Introspect** — tables, columns, types, primary/foreign keys, row counts, and a few sample rows, turned into compact text for the model.
3. **Generate** — your question + schema go to OpenRouter with a dialect-aware system prompt (T-SQL for SQL Server, Postgres syntax for Postgres, etc.), returning `{sql, explanation}` as JSON.
4. **Guard** — SQL must be a single statement (no `; DROP TABLE ...` stacking) and is classified as **read** or **write**.
5. **Execute** — reads run immediately; writes require explicit confirmation.

## ⚠️ Production safety checklist

This tool executes LLM-generated SQL against your real database. Treat it
like any tool with SQL access:

- ✅ **Use a least-privilege DB user** — the strongest safety net; a read-only role can't be tricked into anything destructive no matter what the model outputs.
- ✅ **Review generated SQL before approving writes** — never blindly auto-confirm in production.
- ✅ **Prefer a replica/staging DB** for experimentation.
- ✅ **Log the exact SQL executed** — `QueryResult` includes it, wire it into your audit trail.
- ✅ **Set statement timeouts** at the database level.
- ✅ **Keep `~/.nl2sql/config.json` out of version control** (it's already covered by `.gitignore` here).

## 🗺️ Roadmap / ideas

- [ ] Publish to PyPI
- [ ] `--format json/csv` output for scripting
- [ ] VS Code extension wrapping this SDK
- [ ] Support for more SQLAlchemy dialects (Oracle, Snowflake, BigQuery)
- [ ] Optional row-level result streaming for huge tables

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Project layout

```
nl2sql-toolkit/
├── nl2sql/
│   ├── core.py          # main NL2SQL class (connect, ask, execute)
│   ├── schema.py         # SQLAlchemy-based schema introspection (any dialect)
│   ├── llm.py            # OpenRouter integration, dialect-aware prompting
│   ├── safety.py         # read/write classification + guard rails
│   ├── config.py         # local config store (~/.nl2sql/config.json)
│   └── cli.py             # `nl2sql` command-line interface (click + rich)
├── examples/
│   ├── sdk_usage.py               # basic SDK example
│   ├── flask_plugin_example.py    # embedding as a feature in a Flask backend
│   └── demo_schema.sql             # sample schema/data used in screenshots
├── screenshots/           # README screenshots
├── .github/workflows/ci.yml
├── pyproject.toml
└── README.md
```

## License

[MIT](LICENSE) — use it, fork it, ship it.

---

<div align="center">
<sub>If this is useful, consider ⭐ starring the repo — it helps others find it.</sub>
</div>
