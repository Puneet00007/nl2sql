"""
OpenRouter integration: converts a natural language question + schema context
into a single SQL statement targeted at a specific SQL dialect.
"""
import json
import re
import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT_TEMPLATE = """You are an expert {dialect} database engineer working \
as a pair-programmer for a software developer.

You will be given:
1. A database schema (tables, columns, types, foreign keys, and a few sample rows).
2. A natural language question or instruction from the developer.

Produce a single, correct SQL statement, written in valid {dialect} syntax, that
answers the question or performs the requested operation.

Rules:
- Output ONLY valid {dialect} SQL. Use {dialect}-specific syntax and functions
  (date/string functions, LIMIT/TOP/FETCH, quoting, etc. as appropriate for {dialect}).
- Use only tables/columns that exist in the schema below. Never invent names.
  If schemas/namespaces are shown as "schema.table", use fully qualified names.
- Prefer SELECT queries unless the user explicitly asks to insert, update,
  delete, alter, or otherwise modify data/schema.
- Never use destructive statements (DROP, DELETE, UPDATE, ALTER, TRUNCATE) unless
  the developer's request clearly and explicitly asks for that action.
- Do not include comments or markdown fences inside the SQL string.
- Return exactly one SQL statement (no semicolon-separated multiple statements).
- If the request is ambiguous, make the most reasonable interpretation given the schema.
- Respond ONLY with a JSON object of the form:
  {{"sql": "<the sql statement>", "explanation": "<one short sentence explaining the query>"}}

Database schema ({dialect}):
{schema}
"""


class LLMError(Exception):
    pass


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise LLMError(f"Could not parse JSON from model response: {text[:500]}")


def nl_to_sql(api_key: str, model: str, dialect: str, schema_text: str,
              question: str, conversation_history=None, timeout: int = 60) -> dict:
    """Call OpenRouter chat completions to convert NL -> SQL.
    Returns {"sql": str, "explanation": str}."""
    if not api_key:
        raise LLMError(
            "Missing OpenRouter API key. Pass api_key=... or set the "
            "OPENROUTER_API_KEY environment variable."
        )

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(dialect=dialect, schema=schema_text)

    messages = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        for turn in conversation_history[-6:]:
            messages.append({"role": "user", "content": turn["question"]})
            messages.append({"role": "assistant", "content": json.dumps({
                "sql": turn["sql"], "explanation": turn.get("explanation", "")
            })})
    messages.append({"role": "user", "content": question})

    payload = {"model": model, "messages": messages, "temperature": 0.1}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://arena.ai",
        "X-Title": "NL2SQL Toolkit",
    }

    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=timeout)
    except requests.RequestException as e:
        raise LLMError(f"Network error calling OpenRouter: {e}")

    if resp.status_code != 200:
        raise LLMError(f"OpenRouter API error ({resp.status_code}): {resp.text[:500]}")

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise LLMError(f"Unexpected OpenRouter response shape: {data}")

    parsed = _extract_json(content)
    if "sql" not in parsed:
        raise LLMError(f"Model response missing 'sql' field: {parsed}")

    sql = parsed["sql"].strip()
    if sql.endswith(";"):
        sql = sql[:-1].strip()

    return {"sql": sql, "explanation": parsed.get("explanation", "")}
