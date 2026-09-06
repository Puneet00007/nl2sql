"""
Core NL2SQL class: the main entry point developers embed in their own code.
Handles connecting to a real database (Postgres/MySQL/SQL Server/SQLite/etc
via any SQLAlchemy-compatible connection string), schema introspection,
NL -> SQL translation via OpenRouter, and safe execution.
"""
import os
from dataclasses import dataclass, field
from typing import List, Any, Dict, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .schema import get_schema, schema_to_prompt_text, TableInfo
from .llm import nl_to_sql, LLMError
from .safety import enforce_policy, SQLSafetyError, classify_sql

DIALECT_DISPLAY_NAMES = {
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mssql": "Microsoft SQL Server",
    "sqlite": "SQLite",
    "oracle": "Oracle",
}


@dataclass
class QueryResult:
    question: Optional[str]
    sql: str
    explanation: str
    kind: str                       # "read" | "write"
    columns: List[str] = field(default_factory=list)
    rows: List[List[Any]] = field(default_factory=list)
    affected_rows: int = 0
    executed: bool = False

    def to_dicts(self) -> List[Dict[str, Any]]:
        return [dict(zip(self.columns, row)) for row in self.rows]

    def __repr__(self):
        status = "executed" if self.executed else "generated (not executed)"
        return f"<QueryResult kind={self.kind} status={status} sql={self.sql!r}>"


class NL2SQL:
    """
    Main developer-facing class.

    Example:
        db = NL2SQL(
            connection_string="postgresql+psycopg2://user:pass@host:5432/mydb",
            api_key="sk-or-...",
            model="openai/gpt-4o-mini",
        )
        result = db.ask("top 5 customers by total spend")
        for row in result.to_dicts():
            print(row)
    """

    def __init__(
        self,
        connection_string: str,
        api_key: Optional[str] = None,
        model: str = "openai/gpt-4o-mini",
        db_schema: Optional[str] = None,
        allow_write: bool = False,
        sample_rows_in_schema: bool = True,
        engine_kwargs: Optional[dict] = None,
    ):
        """
        connection_string: any SQLAlchemy URL, e.g.
            postgresql+psycopg2://user:pass@host:5432/dbname
            mysql+pymysql://user:pass@host:3306/dbname
            mssql+pyodbc://user:pass@host:1433/dbname?driver=ODBC+Driver+18+for+SQL+Server
            sqlite:///path/to/file.db
        api_key: OpenRouter API key. Falls back to OPENROUTER_API_KEY env var.
        model: any OpenRouter model id.
        db_schema: optional schema/namespace to restrict introspection to
                   (e.g. "public" for Postgres, or a specific SQL Server schema).
        allow_write: if False (default), write/destructive SQL is generated but
                   NOT executed automatically -- .ask() will return it with
                   executed=False and kind="write" so your app can prompt for
                   confirmation before calling .execute(result.sql, confirmed=True).
        """
        self.connection_string = connection_string
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.model = model
        self.db_schema = db_schema
        self.allow_write = allow_write
        self.sample_rows_in_schema = sample_rows_in_schema
        self.history: List[Dict[str, str]] = []

        self.engine: Engine = create_engine(connection_string, **(engine_kwargs or {}))
        self.dialect_name = self.engine.dialect.name  # e.g. 'postgresql', 'mysql', 'mssql', 'sqlite'
        self._schema_cache: Optional[List[TableInfo]] = None

    # ---------- connection / schema ----------

    def test_connection(self) -> bool:
        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True

    def get_dialect_display_name(self) -> str:
        return DIALECT_DISPLAY_NAMES.get(self.dialect_name, self.dialect_name)

    def refresh_schema(self) -> List[TableInfo]:
        self._schema_cache = get_schema(
            self.engine, schema_name=self.db_schema,
            include_samples=self.sample_rows_in_schema,
        )
        return self._schema_cache

    def get_schema(self, force_refresh: bool = False) -> List[TableInfo]:
        if self._schema_cache is None or force_refresh:
            return self.refresh_schema()
        return self._schema_cache

    def schema_text(self, force_refresh: bool = False) -> str:
        return schema_to_prompt_text(self.get_schema(force_refresh=force_refresh))

    # ---------- NL -> SQL ----------

    def generate_sql(self, question: str) -> Dict[str, str]:
        """Translate a natural language question into SQL without executing it."""
        schema_txt = self.schema_text()
        result = nl_to_sql(
            api_key=self.api_key,
            model=self.model,
            dialect=self.get_dialect_display_name(),
            schema_text=schema_txt,
            question=question,
            conversation_history=self.history,
        )
        return result

    # ---------- execution ----------

    def execute(self, sql: str, confirmed: bool = False) -> QueryResult:
        """Execute a raw SQL statement against the connected database.
        Write/destructive statements require confirmed=True (or self.allow_write=True)."""
        classification = enforce_policy(sql, allow_write=self.allow_write or confirmed)

        columns: List[str] = []
        rows: List[List[Any]] = []
        affected = 0

        with self.engine.begin() as conn:
            cursor_result = conn.execute(text(sql))
            if cursor_result.returns_rows:
                columns = list(cursor_result.keys())
                rows = [list(r) for r in cursor_result.fetchall()]
            else:
                affected = cursor_result.rowcount if cursor_result.rowcount is not None else 0

        return QueryResult(
            question=None,
            sql=sql,
            explanation="",
            kind=classification.kind,
            columns=columns,
            rows=rows,
            affected_rows=affected,
            executed=True,
        )

    def ask(self, question: str, confirm_writes: bool = False, remember: bool = True) -> QueryResult:
        """
        High-level one-shot method: translate `question` to SQL, and run it
        immediately if it's a read query. Write/destructive queries are only
        executed if confirm_writes=True (or self.allow_write=True at init);
        otherwise the SQL is returned with executed=False so your app can show
        it to a human for approval first.
        """
        generated = self.generate_sql(question)
        sql = generated["sql"]
        explanation = generated.get("explanation", "")
        classification = classify_sql(sql)

        can_execute = classification.kind == "read" or self.allow_write or confirm_writes

        if not classification.is_single_statement:
            raise SQLSafetyError("Model returned multiple SQL statements; refusing for safety.")

        if not can_execute:
            return QueryResult(
                question=question, sql=sql, explanation=explanation,
                kind=classification.kind, executed=False,
            )

        exec_result = self.execute(sql, confirmed=True)
        exec_result.question = question
        exec_result.explanation = explanation

        if remember:
            self.history.append({"question": question, "sql": sql, "explanation": explanation})
            self.history = self.history[-20:]

        return exec_result

    def clear_history(self):
        self.history = []

    def close(self):
        self.engine.dispose()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
