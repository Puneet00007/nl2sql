"""
Database-agnostic schema introspection using SQLAlchemy's Inspector.
Works against PostgreSQL, MySQL/MariaDB, SQL Server, SQLite, Oracle, etc.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


@dataclass
class ColumnInfo:
    name: str
    type: str
    nullable: bool
    primary_key: bool
    default: Optional[str] = None


@dataclass
class ForeignKeyInfo:
    columns: List[str]
    ref_table: str
    ref_columns: List[str]


@dataclass
class TableInfo:
    name: str
    schema: Optional[str]
    columns: List[ColumnInfo] = field(default_factory=list)
    foreign_keys: List[ForeignKeyInfo] = field(default_factory=list)
    sample_rows: List[Dict[str, Any]] = field(default_factory=list)
    row_count: Optional[int] = None

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.name}" if self.schema else self.name


def get_schema(engine: Engine, schema_name: Optional[str] = None,
                include_samples: bool = True, sample_limit: int = 3,
                max_tables: int = 200) -> List[TableInfo]:
    """Introspect all tables (optionally within a specific schema/database)
    and return structured info, including small data samples to help the LLM
    understand the shape of the data."""
    inspector = inspect(engine)
    table_names = inspector.get_table_names(schema=schema_name)[:max_tables]

    tables: List[TableInfo] = []
    with engine.connect() as conn:
        for tname in table_names:
            pk_constraint = inspector.get_pk_constraint(tname, schema=schema_name) or {}
            pk_cols = set(pk_constraint.get("constrained_columns") or [])

            columns = []
            for col in inspector.get_columns(tname, schema=schema_name):
                columns.append(ColumnInfo(
                    name=col["name"],
                    type=str(col["type"]),
                    nullable=col.get("nullable", True),
                    primary_key=col["name"] in pk_cols,
                    default=str(col["default"]) if col.get("default") is not None else None,
                ))

            fks = []
            for fk in inspector.get_foreign_keys(tname, schema=schema_name):
                fks.append(ForeignKeyInfo(
                    columns=fk.get("constrained_columns", []),
                    ref_table=fk.get("referred_table", ""),
                    ref_columns=fk.get("referred_columns", []),
                ))

            table = TableInfo(name=tname, schema=schema_name, columns=columns, foreign_keys=fks)

            qualified = f'"{schema_name}"."{tname}"' if schema_name else f'"{tname}"'
            if include_samples:
                try:
                    result = conn.execute(text(f"SELECT * FROM {qualified} LIMIT {sample_limit}"))
                    cols = result.keys()
                    table.sample_rows = [dict(zip(cols, row)) for row in result.fetchall()]
                except Exception:
                    table.sample_rows = []
            try:
                count_result = conn.execute(text(f"SELECT COUNT(*) FROM {qualified}"))
                table.row_count = count_result.scalar()
            except Exception:
                table.row_count = None

            tables.append(table)

    return tables


def schema_to_prompt_text(tables: List[TableInfo], max_chars: int = 12000) -> str:
    """Render schema info as compact text for an LLM prompt, truncating if the
    database has a huge number of tables so we don't blow the context window."""
    lines = []
    for t in tables:
        col_descs = []
        for c in t.columns:
            flags = []
            if c.primary_key:
                flags.append("PK")
            if not c.nullable:
                flags.append("NOT NULL")
            flag_str = f" ({', '.join(flags)})" if flags else ""
            col_descs.append(f"{c.name} {c.type}{flag_str}")
        fk_descs = [
            f'{",".join(fk.columns)} -> {fk.ref_table}.{",".join(fk.ref_columns)}'
            for fk in t.foreign_keys
        ]
        row_count_str = f"{t.row_count} rows" if t.row_count is not None else "row count unknown"
        line = f'Table "{t.qualified_name}" ({row_count_str}): ' + ", ".join(col_descs)
        if fk_descs:
            line += " | Foreign keys: " + ", ".join(fk_descs)
        lines.append(line)
        if t.sample_rows:
            lines.append(f"  Sample rows: {t.sample_rows}")

    text_out = "\n".join(lines)
    if len(text_out) > max_chars:
        text_out = text_out[:max_chars] + "\n... (schema truncated, database has many tables/columns)"
    return text_out
