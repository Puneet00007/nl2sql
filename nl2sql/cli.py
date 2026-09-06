"""
Command-line interface for nl2sql-toolkit.

Typical workflow:

    # one-time: save a connection profile
    nl2sql connect "postgresql+psycopg2://user:pass@host:5432/mydb" --save mydb

    # one-time: save your OpenRouter key
    nl2sql config set-key sk-or-v1-...

    # everyday use
    nl2sql ask "show the 5 highest paid employees" --db mydb
    nl2sql ask "deactivate users who haven't logged in for a year" --db mydb --allow-write

    # inspect schema
    nl2sql schema --db mydb

    # run raw SQL directly
    nl2sql exec "SELECT COUNT(*) FROM orders" --db mydb
"""
import sys
import click
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
from rich.panel import Panel

from . import config as cfg
from .core import NL2SQL
from .safety import SQLSafetyError
from .llm import LLMError

console = Console()


def _resolve_connection_string(db: str, conn: str) -> tuple:
    """Returns (connection_string, db_schema)."""
    if conn:
        return conn, None
    if db:
        saved = cfg.get_connection(db)
        if not saved:
            console.print(f"[red]No saved connection named '{db}'. "
                           f"Use 'nl2sql connect <url> --save {db}' first, "
                           f"or pass --conn directly.[/red]")
            sys.exit(1)
        return saved["connection_string"], saved.get("db_schema")
    console.print("[red]You must provide either --db <saved-name> or --conn <connection-string>.[/red]")
    sys.exit(1)


def _build_client(db: str, conn: str, model: str, allow_write: bool, require_llm: bool = True) -> NL2SQL:
    connection_string, db_schema = _resolve_connection_string(db, conn)
    api_key = cfg.get_api_key()
    if not api_key and require_llm:
        console.print("[yellow]Warning: no OpenRouter API key configured. "
                       "Run 'nl2sql config set-key <key>' or set OPENROUTER_API_KEY.[/yellow]")
    return NL2SQL(
        connection_string=connection_string,
        api_key=api_key,
        model=model or cfg.get_default_model(),
        db_schema=db_schema,
        allow_write=allow_write,
    )


@click.group()
def main():
    """nl2sql — turn natural language into SQL and run it against real databases."""
    pass


# ---------------- connection management ----------------

@main.command()
@click.argument("connection_string")
@click.option("--save", "save_name", default=None, help="Save this connection under a name for future use.")
@click.option("--schema", "db_schema", default=None, help="Restrict to a specific DB schema/namespace.")
def connect(connection_string, save_name, db_schema):
    """Test a connection string against a real database, optionally saving it."""
    try:
        client = NL2SQL(connection_string=connection_string, db_schema=db_schema, api_key="unused")
        client.test_connection()
        console.print(f"[green]✓ Connected successfully "
                       f"({client.get_dialect_display_name()}).[/green]")
    except Exception as e:
        console.print(f"[red]✗ Connection failed: {e}[/red]")
        sys.exit(1)

    if save_name:
        cfg.save_connection(save_name, connection_string, db_schema)
        console.print(f"[green]Saved as '{save_name}'. Use it with --db {save_name}.[/green]")


@main.command("list-connections")
def list_connections_cmd():
    """List saved connection profiles."""
    conns = cfg.list_connections()
    if not conns:
        console.print("[yellow]No saved connections yet. Use 'nl2sql connect <url> --save <name>'.[/yellow]")
        return
    table = Table(title="Saved Connections")
    table.add_column("Name", style="cyan")
    table.add_column("Connection String (redacted)")
    for name, info in conns.items():
        redacted = _redact(info["connection_string"])
        table.add_row(name, redacted)
    console.print(table)


@main.command("remove-connection")
@click.argument("name")
def remove_connection_cmd(name):
    """Remove a saved connection profile."""
    if cfg.remove_connection(name):
        console.print(f"[green]Removed '{name}'.[/green]")
    else:
        console.print(f"[red]No such connection: {name}[/red]")


def _redact(url: str) -> str:
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            creds, host_part = rest.split("@", 1)
            return f"{scheme}://***:***@{host_part}"
    return url


# ---------------- config ----------------

@main.group(name="config")
def config_cmd():
    """Manage stored settings (API key, default model)."""
    pass


@config_cmd.command("set-key")
@click.argument("api_key")
def set_key(api_key):
    """Save your OpenRouter API key locally (~/.nl2sql/config.json, 0600)."""
    cfg.set_api_key(api_key)
    console.print("[green]API key saved.[/green]")


@config_cmd.command("set-model")
@click.argument("model")
def set_model(model):
    """Set the default OpenRouter model id (e.g. openai/gpt-4o-mini)."""
    cfg.set_default_model(model)
    console.print(f"[green]Default model set to {model}.[/green]")


@config_cmd.command("show")
def show_config():
    """Show current config (API key redacted)."""
    c = cfg.load_config()
    key = c.get("api_key", "")
    console.print(f"API key: {'set (' + key[:8] + '...)' if key else 'not set'}")
    console.print(f"Default model: {c.get('default_model')}")
    console.print(f"Saved connections: {list(c.get('connections', {}).keys())}")


# ---------------- schema ----------------

@main.command()
@click.option("--db", default=None, help="Saved connection name.")
@click.option("--conn", default=None, help="Raw connection string (overrides --db).")
def schema(db, conn):
    """Print the introspected schema of a connected database."""
    client = _build_client(db, conn, model=None, allow_write=False, require_llm=False)
    try:
        tables = client.get_schema()
    except Exception as e:
        console.print(f"[red]Failed to read schema: {e}[/red]")
        sys.exit(1)

    for t in tables:
        cols = ", ".join(
            f"{c.name}:{c.type}" + (" PK" if c.primary_key else "") for c in t.columns
        )
        console.print(Panel(cols, title=f"{t.qualified_name} ({t.row_count} rows)"))


# ---------------- ask (NL -> SQL -> execute) ----------------

@main.command()
@click.argument("question")
@click.option("--db", default=None, help="Saved connection name.")
@click.option("--conn", default=None, help="Raw connection string (overrides --db).")
@click.option("--model", default=None, help="OpenRouter model id (overrides default).")
@click.option("--allow-write", is_flag=True, default=False,
              help="Permit executing write/destructive statements without an extra prompt.")
@click.option("--dry-run", is_flag=True, default=False,
              help="Only generate SQL, never execute it.")
def ask(question, db, conn, model, allow_write, dry_run):
    """Ask a natural language question; generates SQL and (for reads) runs it."""
    client = _build_client(db, conn, model, allow_write)

    try:
        generated = client.generate_sql(question)
    except LLMError as e:
        console.print(f"[red]LLM error: {e}[/red]")
        sys.exit(1)

    sql = generated["sql"]
    explanation = generated.get("explanation", "")

    console.print(Panel(explanation or "(no explanation provided)", title="Explanation", style="dim"))
    console.print(Syntax(sql, "sql", theme="monokai", word_wrap=True))

    from .safety import classify_sql
    classification = classify_sql(sql)

    if dry_run:
        console.print("[yellow]--dry-run set: not executing.[/yellow]")
        return

    if classification.kind == "write" and not allow_write:
        if not click.confirm("⚠️  This is a write/destructive query. Run it anyway?", default=False):
            console.print("[yellow]Cancelled.[/yellow]")
            return

    try:
        result = client.execute(sql, confirmed=True)
    except SQLSafetyError as e:
        console.print(f"[red]Blocked by safety check: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Execution error: {e}[/red]")
        sys.exit(1)

    _print_result(result)
    client.history.append({"question": question, "sql": sql, "explanation": explanation})


@main.command()
@click.argument("sql_text")
@click.option("--db", default=None, help="Saved connection name.")
@click.option("--conn", default=None, help="Raw connection string (overrides --db).")
@click.option("--allow-write", is_flag=True, default=False)
def exec(sql_text, db, conn, allow_write):
    """Run a raw SQL statement directly (bypasses the LLM)."""
    client = _build_client(db, conn, model=None, allow_write=allow_write, require_llm=False)
    try:
        result = client.execute(sql_text, confirmed=allow_write)
    except SQLSafetyError as e:
        if click.confirm(f"⚠️  {e}\nRun it anyway?", default=False):
            result = client.execute(sql_text, confirmed=True)
        else:
            console.print("[yellow]Cancelled.[/yellow]")
            return
    except Exception as e:
        console.print(f"[red]Execution error: {e}[/red]")
        sys.exit(1)
    _print_result(result)


def _print_result(result):
    if result.columns:
        table = Table(show_lines=False)
        for c in result.columns:
            table.add_column(str(c))
        for row in result.rows:
            table.add_row(*[str(v) for v in row])
        console.print(table)
        console.print(f"[dim]{len(result.rows)} row(s) returned[/dim]")
    else:
        console.print(f"[green]✓ Success. {result.affected_rows} row(s) affected.[/green]")


if __name__ == "__main__":
    main()
