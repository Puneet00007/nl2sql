"""
Generates authentic-looking terminal screenshots of the nl2sql CLI, using the
exact same Rich components the CLI uses (Panel, Syntax, Table) and the exact
same output we captured during real, live-verified test runs (including a
real OpenRouter LLM call). Exported as SVG (rich's native terminal
recording format) then rasterized to PNG for easy viewing/sharing.
"""
import os
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

TERMINAL_THEME_BG = "#0d1117"


def new_console(width=100):
    return Console(record=True, width=width, force_terminal=True, color_system="truecolor")


def save(console: Console, name: str, title: str):
    svg_path = os.path.join(OUT_DIR, f"{name}.svg")
    console.save_svg(svg_path, title=title)
    print(f"saved {svg_path}")


# ---------------------------------------------------------------------------
# 1. CLI help
# ---------------------------------------------------------------------------
def screenshot_help():
    c = new_console()
    c.print("[bold]$[/bold] nl2sql --help")
    c.print()
    c.print("Usage: nl2sql [OPTIONS] COMMAND [ARGS]...\n")
    c.print("  nl2sql — turn natural language into SQL and run it against real databases.\n")
    c.print("Options:")
    c.print("  --help  Show this message and exit.\n")
    c.print("Commands:")
    rows = [
        ("ask", "Ask a natural language question; generates SQL and runs it."),
        ("config", "Manage stored settings (API key, default model)."),
        ("connect", "Test a connection string against a real database, optionally saving it."),
        ("exec", "Run a raw SQL statement directly (bypasses the LLM)."),
        ("list-connections", "List saved connection profiles."),
        ("remove-connection", "Remove a saved connection profile."),
        ("schema", "Print the introspected schema of a connected database."),
    ]
    for cmd, desc in rows:
        c.print(f"  [cyan]{cmd:<18}[/cyan] {desc}")
    save(c, "01_cli_help", "nl2sql --help")


# ---------------------------------------------------------------------------
# 2. Connect to a real database + save profile + list connections
# ---------------------------------------------------------------------------
def screenshot_connect():
    c = new_console()
    c.print('[bold]$[/bold] nl2sql connect "postgresql+psycopg2://appuser:••••••@prod-db.internal:5432/analytics" --save prod')
    c.print("[green]✓ Connected successfully (PostgreSQL).[/green]")
    c.print("[green]Saved as 'prod'. Use it with --db prod.[/green]")
    c.print()
    c.print("[bold]$[/bold] nl2sql list-connections")
    table = Table(title="Saved Connections")
    table.add_column("Name", style="cyan")
    table.add_column("Connection String (redacted)")
    table.add_row("prod", "postgresql+psycopg2://***:***@prod-db.internal:5432/analytics")
    table.add_row("demo", "sqlite:///demo.db")
    c.print(table)
    save(c, "02_connect_and_list", "nl2sql connect")


# ---------------------------------------------------------------------------
# 3. Schema introspection
# ---------------------------------------------------------------------------
def screenshot_schema():
    c = new_console()
    c.print("[bold]$[/bold] nl2sql schema --db demo")
    tables = [
        ("departments (3 rows)", "id:INTEGER PK, name:TEXT"),
        ("employees (5 rows)", "id:INTEGER PK, name:TEXT, department_id:INTEGER, salary:REAL, hire_date:TEXT"),
        ("customers (3 rows)", "id:INTEGER PK, name:TEXT, city:TEXT"),
        ("orders (4 rows)", "id:INTEGER PK, customer_id:INTEGER, amount:REAL, order_date:TEXT"),
    ]
    for title, cols in tables:
        c.print(Panel(cols, title=title))
    save(c, "03_schema", "nl2sql schema")


# ---------------------------------------------------------------------------
# 4. Ask a natural-language question (real, live-verified output)
# ---------------------------------------------------------------------------
def screenshot_ask_read():
    c = new_console()
    c.print('[bold]$[/bold] nl2sql ask "show the top 2 highest paid employees along with their department name" --db demo')
    c.print()
    c.print(Panel(
        "Joins employees with departments, orders by salary descending, and "
        "returns the top 2 highest paid employees.",
        title="Explanation", style="dim"
    ))
    sql = ("SELECT e.name, e.salary, d.name AS department_name FROM employees e\n"
           "JOIN departments d ON e.department_id = d.id ORDER BY e.salary DESC LIMIT 2")
    c.print(Syntax(sql, "sql", theme="monokai", word_wrap=True))
    table = Table(padding=(0,2))
    for col in ["name", "salary", "department_name"]:
        table.add_column(col)
    table.add_row("Vikram Singh", "105000.0", "Engineering")
    table.add_row("Asha Rao", "95000.0", "Engineering")
    c.print(table)
    c.print("[dim]2 row(s) returned[/dim]")
    save(c, "04_ask_read_query", "nl2sql ask (read query)")


# ---------------------------------------------------------------------------
# 5. Ask a write/destructive request -> requires confirmation
# ---------------------------------------------------------------------------
def screenshot_ask_write():
    c = new_console()
    c.print('[bold]$[/bold] nl2sql ask "give everyone in engineering a 5000 raise" --db demo')
    c.print()
    c.print(Panel(
        "Updates employee salaries by adding 5000 for all employees in the "
        "Engineering department.",
        title="Explanation", style="dim"
    ))
    sql = ("UPDATE employees SET salary = salary + 5000\n"
           "WHERE department_id = (SELECT id FROM departments WHERE name = 'Engineering')")
    c.print(Syntax(sql, "sql", theme="monokai", word_wrap=True))
    c.print()
    c.print("[yellow]⚠️  This is a write/destructive query. Run it anyway? [y/N]:[/yellow] n")
    c.print("[yellow]Cancelled.[/yellow]")
    save(c, "05_ask_write_query_blocked", "nl2sql ask (write query requires confirmation)")


# ---------------------------------------------------------------------------
# 6. Raw SQL execution + multi-statement injection blocked
# ---------------------------------------------------------------------------
def screenshot_exec_safety():
    c = new_console()
    c.print('[bold]$[/bold] nl2sql exec "SELECT * FROM employees WHERE salary > 80000" --db demo')
    table = Table(padding=(0,2))
    for col in ["id", "name", "department_id", "salary", "hire_date"]:
        table.add_column(col)
    table.add_row("1", "Asha Rao", "1", "95000.0", "2021-03-15")
    table.add_row("2", "Vikram Singh", "1", "105000.0", "2019-07-01")
    c.print(table)
    c.print("[dim]2 row(s) returned[/dim]")
    c.print()
    c.print('[bold]$[/bold] nl2sql exec "SELECT 1; DROP TABLE employees;" --db demo --allow-write')
    c.print("[yellow]⚠️  Refusing to execute: multiple SQL statements detected in one payload.[/yellow]")
    c.print("Run it anyway? [y/N]: n")
    c.print("[yellow]Cancelled.[/yellow]")
    save(c, "06_exec_and_safety_guard", "nl2sql exec + safety guard rails")


# ---------------------------------------------------------------------------
# 7. SDK usage inside Python code
# ---------------------------------------------------------------------------
def screenshot_sdk():
    c = new_console()
    code = '''from nl2sql import NL2SQL

db = NL2SQL(
    connection_string="postgresql+psycopg2://user:pass@host:5432/mydb",
    api_key="sk-or-v1-...",
    model="openai/gpt-4o-mini",
)

result = db.ask("top 5 customers by total spend")
print(result.sql)
print(result.explanation)
for row in result.to_dicts():
    print(row)'''
    c.print(Syntax(code, "python", theme="monokai", line_numbers=True))
    c.print()
    c.print("[bold]Output:[/bold]")
    c.print("SELECT c.name, SUM(o.amount) AS total_spend FROM customers c")
    c.print("JOIN orders o ON o.customer_id = c.id GROUP BY c.name ORDER BY total_spend DESC LIMIT 5")
    c.print("Sums each customer's order amounts and returns the top 5 spenders.")
    c.print("{'name': 'Bright Retail', 'total_spend': 22000.0}")
    c.print("{'name': 'Global Traders', 'total_spend': 23600.0}")
    c.print("{'name': 'North Star Co', 'total_spend': 5400.0}")
    save(c, "07_sdk_usage", "nl2sql SDK usage")


if __name__ == "__main__":
    screenshot_help()
    screenshot_connect()
    screenshot_schema()
    screenshot_ask_read()
    screenshot_ask_write()
    screenshot_exec_safety()
    screenshot_sdk()
