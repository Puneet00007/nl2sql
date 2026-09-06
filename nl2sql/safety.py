"""
Safety utilities: classify SQL statements as read/write, detect multi-statement
payloads, and provide guard-rail checks before anything touches a real database.

This is a defense-in-depth layer, not a substitute for proper DB user
permissions. Always run this tool with a database role that has the minimum
privileges needed (see README "Production safety checklist").
"""
import re
from dataclasses import dataclass

WRITE_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "REPLACE", "GRANT", "REVOKE", "MERGE", "EXEC", "EXECUTE",
}

READ_KEYWORDS = {"SELECT", "WITH", "EXPLAIN", "SHOW", "DESCRIBE", "DESC"}


class SQLSafetyError(Exception):
    """Raised when a generated/user-provided SQL statement fails a safety check."""


@dataclass
class SQLClassification:
    kind: str            # "read" | "write" | "unknown"
    leading_keyword: str
    is_single_statement: bool


def _leading_keyword(sql: str) -> str:
    stripped = sql.strip().lstrip("(").strip()
    match = re.match(r"[A-Za-z]+", stripped)
    return match.group(0).upper() if match else ""


def is_single_statement(sql: str) -> bool:
    """Defensive check against statement stacking (e.g. "...; DROP TABLE users;").
    Not a full SQL parser — strips a trailing semicolon and rejects any
    remaining semicolon. Good enough as a guard rail; combine with a
    least-privilege DB user for real safety.
    """
    cleaned = sql.strip()
    while cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()
    return ";" not in cleaned


def classify_sql(sql: str) -> SQLClassification:
    kw = _leading_keyword(sql)
    if kw in WRITE_KEYWORDS:
        kind = "write"
    elif kw in READ_KEYWORDS:
        kind = "read"
    else:
        kind = "unknown"
    return SQLClassification(
        kind=kind,
        leading_keyword=kw,
        is_single_statement=is_single_statement(sql),
    )


def enforce_policy(sql: str, allow_write: bool) -> SQLClassification:
    """Raise SQLSafetyError if the statement violates the current policy.
    Returns the classification if it's OK to proceed (caller may still want
    to prompt for human confirmation on writes)."""
    classification = classify_sql(sql)

    if not classification.is_single_statement:
        raise SQLSafetyError(
            "Refusing to execute: multiple SQL statements detected in one payload."
        )

    if classification.kind == "unknown":
        raise SQLSafetyError(
            f"Refusing to execute: unrecognized/unsafe statement type "
            f"(leading keyword: '{classification.leading_keyword}')."
        )

    if classification.kind == "write" and not allow_write:
        raise SQLSafetyError(
            "This statement modifies data or schema (write query). "
            "Re-run with allow_write=True / --allow-write / confirm=True to permit it."
        )

    return classification
