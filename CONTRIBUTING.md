# Contributing to nl2sql-toolkit

Thanks for considering a contribution! This project is small and young, so
contributions of any size are welcome — bug reports, docs fixes, new DB
dialect support, tests, or features.

## Getting set up

```bash
git clone https://github.com/<your-username>/nl2sql-toolkit.git
cd nl2sql-toolkit
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
```

## Running it locally against a throwaway SQLite DB

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('examples/demo.db')
conn.executescript(open('examples/demo_schema.sql').read())
"
nl2sql connect "sqlite:///examples/demo.db" --save demo
nl2sql config set-key <your-openrouter-key>
nl2sql ask "show all tables" --db demo
```

## Guidelines

- Keep `nl2sql/core.py`, `nl2sql/schema.py` dialect-agnostic — anything
  database-specific should go through SQLAlchemy, not raw driver calls.
- Any change touching SQL execution must keep the safety guarantees in
  `nl2sql/safety.py` intact: single-statement enforcement and
  read/write classification before execution.
- Add/update tests for new behavior where practical.
- Run `python3 -m build` locally to make sure packaging still works before
  opening a PR that touches `pyproject.toml`.

## Reporting issues

Please include:
- Your OS + Python version
- The database dialect you're connecting to
- The exact command/code that failed and the full error/traceback
- Whether the issue is in schema introspection, SQL generation, or execution

## Ideas for contributions

- Additional SQL dialect polish (Oracle, Snowflake, BigQuery via SQLAlchemy)
- A `--format json/csv` output option for the `ask`/`exec` commands
- Async/streaming support for large result sets
- A minimal VS Code extension wrapping the SDK
- More test coverage around `safety.py` edge cases
