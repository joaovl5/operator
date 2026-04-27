from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

JsonScalar = str | int | float | bool | None
JsonObject = dict[str, "JsonValue"]
JsonValue = JsonScalar | list["JsonValue"] | JsonObject

JSONColumn = JSON().with_variant(JSONB(), "postgresql")
"""Generic JSON type for SQLAlchemy that defaults to JSONB for Postgres."""
