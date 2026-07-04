"""adapters/data/normalizer.py — DefaultNormalizer: zero-defect data processor.

Zero-defect principles applied here:
  1. Every string is trimmed and sanitized (no raw user text to store)
  2. Every number is validated for NaN/Infinity before storage
  3. Every date is coerced to ISO 8601 UTC
  4. Every UUID is lowercased and validated
  5. Every email is lowercased and trimmed
  6. Every URL is normalized (trailing slash, scheme check)
  7. Null/undefined optional fields are dropped (not stored as null)
  8. Unknown fields not in schema are stripped (no schema pollution)
  9. Enum values are validated against declared options
 10. Array elements are recursively normalized
"""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any

from ooagent.adapters.data.protocols import (
    CollectionSchema,
    FieldChange,
    FieldDefinition,
    INormalizer,
    NormalizationResult,
)

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_URL_RE = re.compile(r"^https?://")


def _changed(original: Any, normalized: Any) -> bool:
    """Mirrors JS strict inequality (`!==`) for change-tracking purposes.

    Python's `==` treats `True == 1` / `False == 0`, which JS's `===` does
    not — special-cased here so a boolean-vs-number coercion is always
    recorded as a change, matching the TS behavior.
    """
    if isinstance(original, bool) != isinstance(normalized, bool):
        return True
    return original != normalized


class DefaultNormalizer(INormalizer[dict[str, Any]]):
    def normalize(self, raw: Any, schema: CollectionSchema) -> NormalizationResult[dict[str, Any]]:
        changes: list[FieldChange] = []
        warnings: list[str] = []

        if not isinstance(raw, dict):
            warnings.append("Input is not a plain object — returning empty record")
            return NormalizationResult(normalized={}, changes=changes, warnings=warnings)

        input_ = raw
        normalized: dict[str, Any] = {}

        for field_name, field_def in schema.fields.items():
            original = input_.get(field_name)

            # Missing (or explicitly null) optional fields — use default or skip.
            if original is None:
                if field_def.default is not None:
                    normalized[field_name] = field_def.default
                    changes.append(FieldChange(field=field_name, original=original, normalized=field_def.default))
                # Required fields with no value are left absent — validator catches them.
                continue

            value = self._normalize_field(field_name, original, field_def, warnings)
            if _changed(original, value):
                changes.append(FieldChange(field=field_name, original=original, normalized=value))
            # `None` here plays the role of TS `undefined` — "no value, drop
            # the field". A JSON field whose raw value normalizes to a
            # legitimate `null` collapses into the same "omit" behavior;
            # this is inert downstream because every consumer in this slice
            # (ISchemaValidator, DataStorePlugin) treats an absent key and an
            # explicit `None` value identically.
            if value is not None:
                normalized[field_name] = value

        # Strip unknown fields (schema pollution prevention).
        known_fields = set(schema.fields.keys())
        for key in input_.keys():
            if key not in known_fields:
                warnings.append(f"Unknown field '{key}' stripped (not in schema '{schema.name}')")

        return NormalizationResult(normalized=normalized, changes=changes, warnings=warnings)

    def _normalize_field(
        self, name: str, value: Any, definition: FieldDefinition, warnings: list[str]
    ) -> Any:
        field_type = definition.type

        if field_type == "string":
            return self._normalize_string(value, warnings, name)

        if field_type == "number":
            return self._normalize_number(value, warnings, name)

        if field_type == "boolean":
            if isinstance(value, bool):
                return value
            is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
            if value == "true" or (is_number and value == 1):
                return True
            if value == "false" or (is_number and value == 0):
                return False
            warnings.append(f"Field '{name}': cannot coerce '{value}' to boolean, skipping")
            return None

        if field_type == "date":
            return self._normalize_date(value, warnings, name)

        if field_type == "uuid":
            s = str(value).lower().strip()
            if not _UUID_RE.match(s):
                warnings.append(f"Field '{name}': value '{value}' is not a valid UUID")
            return s

        if field_type == "email":
            s = str(value).lower().strip()
            if not _EMAIL_RE.match(s):
                warnings.append(f"Field '{name}': value '{value}' is not a valid email")
            return s

        if field_type == "url":
            s = str(value).strip()
            if not _URL_RE.match(s):
                warnings.append(f"Field '{name}': '{s}' has no https?:// scheme — prepending https://")
                s = f"https://{s}"
            # Remove trailing slash for consistency.
            return re.sub(r"/$", "", s)

        if field_type == "enum":
            s = str(value)
            if definition.enum_values and s not in definition.enum_values:
                warnings.append(f"Field '{name}': value '{s}' not in enum {definition.enum_values}")
            return s

        if field_type == "json":
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    warnings.append(f"Field '{name}': invalid JSON string, storing as-is")
                    return value
            return value

        if field_type == "array":
            if not isinstance(value, list):
                warnings.append(f"Field '{name}': expected array, got {type(value).__name__}")
                return []
            if not definition.items:
                return value
            items = [
                self._normalize_field(f"{name}[{i}]", item, definition.items, warnings)
                for i, item in enumerate(value)
            ]
            return [v for v in items if v is not None]

        if field_type == "object":
            if not isinstance(value, dict):
                warnings.append(f"Field '{name}': expected object, got {type(value).__name__}")
                return {}
            if not definition.properties:
                return value
            obj: dict[str, Any] = {}
            for k, prop_def in definition.properties.items():
                v = value.get(k)
                if v is not None:
                    obj[k] = self._normalize_field(f"{name}.{k}", v, prop_def, warnings)
                elif prop_def.default is not None:
                    obj[k] = prop_def.default
            return obj

        return value

    def _normalize_string(self, value: Any, warnings: list[str], name: str) -> str:
        if not isinstance(value, str):
            warnings.append(f"Field '{name}': coerced {type(value).__name__} to string")
            return str(value).strip()
        return value.strip()

    def _normalize_number(self, value: Any, warnings: list[str], name: str) -> float | None:
        n = _to_number(value)
        if n != n:  # NaN
            warnings.append(f"Field '{name}': value '{value}' is NaN — skipping")
            return None
        if n in (float("inf"), float("-inf")):
            warnings.append(f"Field '{name}': value '{value}' is Infinity — skipping")
            return None
        return n

    def _normalize_date(self, value: Any, warnings: list[str], name: str) -> str | None:
        if isinstance(value, dt.datetime):
            return _to_iso(value)
        if isinstance(value, str):
            parsed = _parse_date_string(value)
            if parsed is None:
                warnings.append(f"Field '{name}': '{value}' is not a valid date — skipping")
                return None
            return _to_iso(parsed)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                parsed = dt.datetime.fromtimestamp(value / 1000, tz=dt.timezone.utc)
            except (OverflowError, OSError, ValueError):
                warnings.append(f"Field '{name}': '{value}' is not a valid date — skipping")
                return None
            return _to_iso(parsed)
        warnings.append(f"Field '{name}': cannot coerce {type(value).__name__} to date — skipping")
        return None


def _to_number(value: Any) -> float:
    """Approximates JS `Number(value)` coercion for the primitive shapes this
    normalizer expects to see (string, number, boolean)."""
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            return 0.0  # `Number('')` === 0 in JS
        try:
            return float(s)
        except ValueError:
            return float("nan")
    return float("nan")


def _parse_date_string(value: str) -> dt.datetime | None:
    """Best-effort ISO 8601 parse, standing in for JS's permissive `Date`
    constructor. Judgment call: exotic JS-only date formats are not replicated.
    """
    s = value.strip()
    try:
        parsed = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = dt.datetime.fromisoformat(f"{s}T00:00:00+00:00")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def _to_iso(value: dt.datetime) -> str:
    """Formats like JS `Date.prototype.toISOString()`: milliseconds, `Z` suffix, UTC."""
    utc = value.astimezone(dt.timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"
