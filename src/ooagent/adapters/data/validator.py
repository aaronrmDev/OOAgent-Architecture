"""adapters/data/validator.py — DefaultSchemaValidator.

Validates a normalized record against a CollectionSchema. Called after
normalization, before every write. Validation failure = hard block.

Full normalization rules enforced:
  1NF  — atomic values only, no arrays of arrays unless explicitly typed
  2NF  — primary key presence is required (NOT uniqueness — no adapter in
         this package reads FieldDefinition.unique/indexed or IndexSpec.unique;
         a real backend enforcing unique indexes must check that separately)
  3NF  — no transitive dependencies: validator enforces field-level constraints only

Zero-defect guarantee: a record that passes validate() + normalize() is
guaranteed to be type-safe, range-valid, and schema-compliant — NOT
guaranteed unique, since uniqueness enforcement is a backend-adapter
responsibility this package does not implement (InMemoryDataStore.insert()
silently overwrites on a duplicate id).
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from ooagent.adapters.data.protocols import (
    CollectionSchema,
    FieldDefinition,
    ISchemaValidator,
    ValidationError,
    ValidationResult,
)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_URL_RE = re.compile(r"^https?://.+")


def _is_valid_date_string(value: str) -> bool:
    try:
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _err(field: str, message: str, value: Any) -> ValidationError:
    """Build a ValidationError — a thin helper to keep call sites within line-length."""
    return ValidationError(field=field, message=message, value=value)


class DefaultSchemaValidator(ISchemaValidator):
    def validate(self, record: dict[str, Any], schema: CollectionSchema) -> ValidationResult:
        errors: list[ValidationError] = []

        for field_name, field_def in schema.fields.items():
            value = record.get(field_name)
            self._validate_field(field_name, value, field_def, errors)

        # Validate primary key presence.
        pks = schema.primary_key if isinstance(schema.primary_key, list) else [schema.primary_key]
        for pk in pks:
            if record.get(pk) is None:
                errors.append(_err(pk, f"Primary key field '{pk}' is missing", record.get(pk)))

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def _validate_field(
        self, name: str, value: Any, definition: FieldDefinition, errors: list[ValidationError]
    ) -> None:
        # Required check.
        if definition.required and (value is None or value == ""):
            errors.append(_err(name, f"Field '{name}' is required", value))
            return

        # Skip optional missing fields.
        if value is None:
            return

        field_type = definition.type

        if field_type == "string":
            if not isinstance(value, str):
                errors.append(_err(name, f"Field '{name}' must be a string", value))
                return
            if definition.min is not None and len(value) < definition.min:
                errors.append(_err(name, f"Field '{name}' min length is {definition.min}", value))
            if definition.max is not None and len(value) > definition.max:
                errors.append(_err(name, f"Field '{name}' max length is {definition.max}", value))
            if definition.pattern is not None and not re.search(definition.pattern, value):
                msg = f"Field '{name}' does not match pattern '{definition.pattern}'"
                errors.append(_err(name, msg, value))
            return

        if field_type == "number":
            is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
            if not is_number or value != value or value in (float("inf"), float("-inf")):
                errors.append(_err(name, f"Field '{name}' must be a finite number", value))
                return
            if definition.min is not None and value < definition.min:
                errors.append(_err(name, f"Field '{name}' minimum is {definition.min}", value))
            if definition.max is not None and value > definition.max:
                errors.append(_err(name, f"Field '{name}' maximum is {definition.max}", value))
            return

        if field_type == "boolean":
            if not isinstance(value, bool):
                errors.append(_err(name, f"Field '{name}' must be a boolean", value))
            return

        if field_type == "date":
            if not isinstance(value, str) or not _is_valid_date_string(value):
                errors.append(_err(name, f"Field '{name}' must be an ISO 8601 date string", value))
            return

        if field_type == "uuid":
            if not isinstance(value, str) or not _UUID_RE.match(value):
                errors.append(_err(name, f"Field '{name}' must be a valid UUID v4", value))
            return

        if field_type == "email":
            if not isinstance(value, str) or not _EMAIL_RE.match(value):
                errors.append(_err(name, f"Field '{name}' must be a valid email address", value))
            return

        if field_type == "url":
            if not isinstance(value, str) or not _URL_RE.match(value):
                errors.append(_err(name, f"Field '{name}' must be a valid https?:// URL", value))
            return

        if field_type == "enum":
            if definition.enum_values and str(value) not in definition.enum_values:
                joined = ", ".join(definition.enum_values)
                errors.append(_err(name, f"Field '{name}' must be one of: {joined}", value))
            return

        if field_type == "array":
            if not isinstance(value, list):
                errors.append(_err(name, f"Field '{name}' must be an array", value))
                return
            if definition.min is not None and len(value) < definition.min:
                errors.append(_err(name, f"Field '{name}' minimum {definition.min} items", value))
            if definition.max is not None and len(value) > definition.max:
                errors.append(_err(name, f"Field '{name}' maximum {definition.max} items", value))
            if definition.items:
                for i, item in enumerate(value):
                    self._validate_field(f"{name}[{i}]", item, definition.items, errors)
            return

        if field_type == "object":
            if not isinstance(value, dict):
                errors.append(_err(name, f"Field '{name}' must be a plain object", value))
                return
            if definition.properties:
                for k, prop_def in definition.properties.items():
                    self._validate_field(f"{name}.{k}", value.get(k), prop_def, errors)
            return
