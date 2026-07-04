"""adapters/data/datastore_plugin.py — DataStorePlugin.

An IPlugin that registers IDataStore as OOAgent tools. Exposes insert, find,
find_by_id, update, upsert, delete, count as callable ITool specs. The agent
can query and write to any IDataStore backend via tool calls.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from ooagent.core.protocols import (
    IAgent,
    ITool,
    JSONSchema,
    LLMVendor,
    PluginContributions,
    VendorToolSpec,
    IPlugin,
)

from ooagent.adapters.data.protocols import (
    CollectionSchema,
    DataStoreGuardError,
    IDataStore,
    OrderBySpec,
    QueryOptions,
    SchemaValidationError,
    WhereClause,
)
from ooagent.adapters.data.normalizer import DefaultNormalizer
from ooagent.adapters.data.validator import DefaultSchemaValidator

_logger = logging.getLogger("ooagent.datastore_plugin")


def _fire_and_forget(coro: Awaitable[None]) -> None:
    """Schedules `coro` without awaiting it.

    Mirrors the TS `.then()/.catch()` fire-and-forget pattern used in
    `onRegister`/`onDispose` (both are synchronous methods that kick off an
    async connect/disconnect without blocking). Python has no implicit
    always-on event loop like Node — if one happens to be running we hand
    the coroutine to it as a background task; otherwise we run it to
    completion synchronously so it is never silently dropped.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
    else:
        loop.create_task(coro)


class DataStoreTool(ITool):
    """Thin ITool wrapper around a DataStore operation."""

    def __init__(
        self,
        name: str,
        description: str,
        schema_fn: Callable[[], JSONSchema],
        execute_fn: Callable[[dict[str, Any]], Awaitable[Any]],
    ) -> None:
        self._name = name
        self._description = description
        self._schema_fn = schema_fn
        self._execute_fn = execute_fn

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    def input_schema(self) -> JSONSchema:
        return self._schema_fn()

    async def execute(self, args: dict[str, Any]) -> Any:
        return await self._execute_fn(args)

    def to_vendor_spec(self, vendor: LLMVendor) -> VendorToolSpec:
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema()}


@dataclass(frozen=True)
class DataStorePluginOptions:
    """Collections to expose. If `allowed_collections` is omitted, all
    operations are unlocked. `schemas` are used for validation + normalization.
    `enforce_schema` (default True) toggles whether writes are validated."""

    allowed_collections: list[str] | None = None
    schemas: list[CollectionSchema] = field(default_factory=list)
    enforce_schema: bool = True


def _parse_where(raw: Any) -> list[WhereClause] | None:
    if raw is None:
        return None
    return [WhereClause(field=w["field"], operator=w["operator"], value=w["value"]) for w in raw]


def _parse_order_by(raw: Any) -> list[OrderBySpec] | None:
    if raw is None:
        return None
    return [OrderBySpec(field=o["field"], direction=o["direction"]) for o in raw]


class DataStorePlugin(IPlugin):
    def __init__(self, store: IDataStore, options: DataStorePluginOptions | None = None) -> None:
        self._store = store
        self._opts = options or DataStorePluginOptions()
        self._normalizer = DefaultNormalizer()
        self._validator = DefaultSchemaValidator()
        self._schema_map: dict[str, CollectionSchema] = {s.name: s for s in self._opts.schemas}
        self._connected = False

    @property
    def plugin_id(self) -> str:
        return "ooagent.datastore"

    @property
    def version(self) -> str:
        return "2026.06.01"

    def on_register(self, agent: "IAgent[Any, Any]") -> None:
        async def _connect() -> None:
            try:
                await self._store.connect()
                self._connected = True
            except Exception as exc:  # noqa: BLE001 - mirrors TS catch-all
                _logger.error("[DataStorePlugin] Connect failed: %s", exc)

        _fire_and_forget(_connect())

    def on_dispose(self) -> None:
        if self._connected:
            async def _disconnect() -> None:
                try:
                    await self._store.disconnect()
                except Exception:  # noqa: BLE001 - mirrors TS `.catch(() => undefined)`
                    pass

            _fire_and_forget(_disconnect())
            self._connected = False

    def contributes(self) -> PluginContributions:
        return PluginContributions(tools=self._build_tools())

    def _is_allowed(self, collection: str) -> bool:
        if self._opts.allowed_collections is None:
            return True
        return collection in self._opts.allowed_collections

    def _guard(self, collection: str) -> None:
        if not self._is_allowed(collection):
            raise DataStoreGuardError(f"Collection '{collection}' is not in the allowedCollections list")
        if not self._connected:
            raise DataStoreGuardError("DataStore is not connected")

    def _normalize_and_validate(self, collection: str, record: dict[str, Any]) -> dict[str, Any]:
        schema = self._schema_map.get(collection)
        if schema is None or not self._opts.enforce_schema:
            return record

        result = self._normalizer.normalize(record, schema)
        if result.warnings:
            _logger.warning("[DataStorePlugin] Normalization warnings for '%s': %s", collection, result.warnings)

        normalized = dict(result.normalized)

        # Assign a primary key if missing.
        pk = schema.primary_key[0] if isinstance(schema.primary_key, list) else schema.primary_key
        if not normalized.get(pk):
            normalized[pk] = str(uuid.uuid4())

        validation = self._validator.validate(normalized, schema)
        if not validation.valid:
            raise SchemaValidationError(collection, validation.errors)

        return normalized

    def _build_tools(self) -> list[ITool]:
        return [
            self._build_insert_tool(),
            self._build_find_tool(),
            self._build_find_by_id_tool(),
            self._build_update_tool(),
            self._build_upsert_tool(),
            self._build_delete_tool(),
            self._build_count_tool(),
        ]

    # ── ds_insert ─────────────────────────────────────────────────────────────
    def _build_insert_tool(self) -> DataStoreTool:
        async def execute(args: dict[str, Any]) -> Any:
            collection = args["collection"]
            record = args["record"]
            self._guard(collection)
            clean = self._normalize_and_validate(collection, record)
            id_ = await self._store.insert(collection, clean)
            return {"id": id_, "collection": collection, "status": "inserted"}

        return DataStoreTool(
            "ds_insert",
            "Insert a single record into a datastore collection. Validates and normalizes before writing.",
            lambda: {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Target collection name"},
                    "record": {"type": "object", "description": "Record to insert"},
                },
                "required": ["collection", "record"],
            },
            execute,
        )

    # ── ds_find ───────────────────────────────────────────────────────────────
    def _build_find_tool(self) -> DataStoreTool:
        async def execute(args: dict[str, Any]) -> Any:
            collection = args["collection"]
            self._guard(collection)
            options = QueryOptions(
                where=_parse_where(args.get("where")),
                limit=args.get("limit"),
                offset=args.get("offset"),
                order_by=_parse_order_by(args.get("orderBy")),
            )
            return await self._store.find(collection, options)

        return DataStoreTool(
            "ds_find",
            "Query records from a datastore collection with optional filtering, ordering, and pagination.",
            lambda: {
                "type": "object",
                "properties": {
                    "collection": {"type": "string"},
                    "where": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "operator": {
                                    "type": "string",
                                    "enum": ["=", "!=", "<", "<=", ">", ">=", "in", "not_in", "like", "exists"],
                                },
                                "value": {},
                            },
                            "required": ["field", "operator", "value"],
                        },
                    },
                    "limit": {"type": "number", "minimum": 1, "maximum": 1000, "default": 20},
                    "offset": {"type": "number", "minimum": 0, "default": 0},
                    "orderBy": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "direction": {"type": "string", "enum": ["asc", "desc"]},
                            },
                        },
                    },
                },
                "required": ["collection"],
            },
            execute,
        )

    # ── ds_find_by_id ─────────────────────────────────────────────────────────
    def _build_find_by_id_tool(self) -> DataStoreTool:
        async def execute(args: dict[str, Any]) -> Any:
            collection = args["collection"]
            id_ = args["id"]
            self._guard(collection)
            record = await self._store.find_by_id(collection, id_)
            return record if record is not None else {"error": f"Record '{id_}' not found in '{collection}'"}

        return DataStoreTool(
            "ds_find_by_id",
            "Retrieve a single record by its primary key ID.",
            lambda: {
                "type": "object",
                "properties": {
                    "collection": {"type": "string"},
                    "id": {"type": "string"},
                },
                "required": ["collection", "id"],
            },
            execute,
        )

    # ── ds_update ─────────────────────────────────────────────────────────────
    def _build_update_tool(self) -> DataStoreTool:
        async def execute(args: dict[str, Any]) -> Any:
            collection = args["collection"]
            id_ = args["id"]
            patch = args["patch"]
            self._guard(collection)
            updated = await self._store.update(collection, id_, patch)
            return {"id": id_, "collection": collection, "updated": updated, "status": "updated" if updated else "not_found"}

        return DataStoreTool(
            "ds_update",
            "Update a record by ID with a partial patch. Validates patch fields against schema.",
            lambda: {
                "type": "object",
                "properties": {
                    "collection": {"type": "string"},
                    "id": {"type": "string"},
                    "patch": {"type": "object", "description": "Fields to update (partial)"},
                },
                "required": ["collection", "id", "patch"],
            },
            execute,
        )

    # ── ds_upsert ─────────────────────────────────────────────────────────────
    def _build_upsert_tool(self) -> DataStoreTool:
        async def execute(args: dict[str, Any]) -> Any:
            collection = args["collection"]
            record = args["record"]
            match_fields = args["matchFields"]
            self._guard(collection)
            clean = self._normalize_and_validate(collection, record)
            return await self._store.upsert(collection, clean, match_fields)

        return DataStoreTool(
            "ds_upsert",
            "Insert or update a record based on match fields. Normalizes and validates before writing.",
            lambda: {
                "type": "object",
                "properties": {
                    "collection": {"type": "string"},
                    "record": {"type": "object"},
                    "matchFields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Fields to match for update detection",
                    },
                },
                "required": ["collection", "record", "matchFields"],
            },
            execute,
        )

    # ── ds_delete ─────────────────────────────────────────────────────────────
    def _build_delete_tool(self) -> DataStoreTool:
        async def execute(args: dict[str, Any]) -> Any:
            collection = args["collection"]
            id_ = args["id"]
            self._guard(collection)
            deleted = await self._store.delete(collection, id_)
            return {"id": id_, "collection": collection, "deleted": deleted, "status": "deleted" if deleted else "not_found"}

        return DataStoreTool(
            "ds_delete",
            "Delete a record by ID from a collection.",
            lambda: {
                "type": "object",
                "properties": {
                    "collection": {"type": "string"},
                    "id": {"type": "string"},
                },
                "required": ["collection", "id"],
            },
            execute,
        )

    # ── ds_count ──────────────────────────────────────────────────────────────
    def _build_count_tool(self) -> DataStoreTool:
        async def execute(args: dict[str, Any]) -> Any:
            collection = args["collection"]
            self._guard(collection)
            count = await self._store.count(collection, _parse_where(args.get("where")))
            return {"collection": collection, "count": count}

        return DataStoreTool(
            "ds_count",
            "Count records in a collection with optional filtering.",
            lambda: {
                "type": "object",
                "properties": {
                    "collection": {"type": "string"},
                    "where": {"type": "array"},
                },
                "required": ["collection"],
            },
            execute,
        )
