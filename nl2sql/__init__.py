"""
nl2sql-toolkit
==============
Turn natural language into SQL and run it against real databases
(PostgreSQL, MySQL, SQL Server, SQLite, and anything else SQLAlchemy supports).

Quick start (as a library):

    from nl2sql import NL2SQL

    db = NL2SQL(
        connection_string="postgresql://user:pass@host:5432/mydb",
        api_key="sk-or-...",          # or set OPENROUTER_API_KEY env var
        model="openai/gpt-4o-mini",   # any OpenRouter model id
    )

    result = db.ask("show the 5 highest paid employees")
    print(result.sql)
    print(result.rows)

Or from the command line, after `pip install -e .`:

    nl2sql connect "postgresql://user:pass@host:5432/mydb" --save mydb
    nl2sql ask "show the 5 highest paid employees" --db mydb
"""
from .core import NL2SQL, QueryResult
from .safety import SQLSafetyError

__all__ = ["NL2SQL", "QueryResult", "SQLSafetyError"]
__version__ = "0.1.0"
