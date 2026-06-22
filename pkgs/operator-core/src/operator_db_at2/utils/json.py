"""Generic JSON type aliases."""

JsonScalar = str | int | float | bool | None
JsonObject = dict[str, "JsonValue"]
JsonValue = JsonScalar | list["JsonValue"] | JsonObject

__all__ = ["JsonObject", "JsonScalar", "JsonValue"]
