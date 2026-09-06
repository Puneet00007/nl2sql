"""
Example: dropping nl2sql-toolkit into an existing Flask backend as a feature
(e.g. an internal "ask your database" endpoint for your team/product).

Run with:  python flask_plugin_example.py
Then:      curl -X POST localhost:5001/api/ask -H "Content-Type: application/json" \
                -d '{"question": "how many orders were placed this month"}'
"""
import os
from flask import Flask, request, jsonify
from nl2sql import NL2SQL, SQLSafetyError

app = Flask(__name__)

# One shared NL2SQL client for the whole app (thread-safe enough for demo
# purposes since SQLAlchemy engines pool connections internally; for high
# concurrency, consider one engine + short-lived sessions per request).
db = NL2SQL(
    connection_string=os.environ.get("DATABASE_URL", "sqlite:///demo.db"),
    api_key=os.environ.get("OPENROUTER_API_KEY"),
    model="openai/gpt-4o-mini",
    allow_write=False,
)


@app.route("/api/ask", methods=["POST"])
def ask():
    payload = request.get_json(force=True) or {}
    question = payload.get("question", "").strip()
    confirm_writes = bool(payload.get("confirm_writes", False))

    if not question:
        return jsonify({"error": "Missing 'question'."}), 400

    try:
        result = db.ask(question, confirm_writes=confirm_writes)
    except SQLSafetyError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "sql": result.sql,
        "explanation": result.explanation,
        "kind": result.kind,
        "executed": result.executed,
        "columns": result.columns,
        "rows": result.rows,
        "affected_rows": result.affected_rows,
    })


if __name__ == "__main__":
    app.run(port=5001, debug=True)
