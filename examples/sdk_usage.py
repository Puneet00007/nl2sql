"""
Example: using nl2sql-toolkit as an embedded library inside your own
application/backend. This is the "plugin" use case — you import NL2SQL
and add natural-language querying as a feature of your own product.
"""
import os
from nl2sql import NL2SQL

# --- Real database examples (uncomment the one you need) ---

# PostgreSQL
# conn_str = "postgresql+psycopg2://myuser:mypassword@localhost:5432/mydb"

# MySQL / MariaDB
# conn_str = "mysql+pymysql://myuser:mypassword@localhost:3306/mydb"

# Microsoft SQL Server (requires the ODBC Driver 17/18 installed on the host)
# conn_str = "mssql+pyodbc://myuser:mypassword@localhost:1433/mydb?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"

# SQLite (good for local testing of this SDK)
conn_str = "sqlite:///demo.db"


def main():
    db = NL2SQL(
        connection_string=conn_str,
        api_key=os.environ.get("OPENROUTER_API_KEY"),   # or pass the string directly
        model="openai/gpt-4o-mini",                       # any OpenRouter model id
        allow_write=False,                                 # writes require explicit confirmation
    )

    db.test_connection()
    print(f"Connected to {db.get_dialect_display_name()}")

    # 1) Simple read query -- executes automatically
    result = db.ask("show the 5 highest paid employees")
    print("SQL:", result.sql)
    print("Explanation:", result.explanation)
    for row in result.to_dicts():
        print(row)

    # 2) A write/destructive request -- NOT executed unless you confirm
    result2 = db.ask("give every employee in engineering a 10% raise")
    if not result2.executed:
        print("\nGenerated a write query, awaiting confirmation:")
        print(result2.sql)
        # In a real app you'd show this to a human first. To actually run it:
        # confirmed_result = db.execute(result2.sql, confirmed=True)

    db.close()


if __name__ == "__main__":
    main()
