"""tests/adapters/test_data_store.py — InMemoryDataStore, normalizer, validator, DataStorePlugin."""

from __future__ import annotations

import pytest

from ooagent.adapters.data.datastore_plugin import DataStorePlugin, DataStorePluginOptions
from ooagent.adapters.data.in_memory_store import InMemoryDataStore
from ooagent.adapters.data.protocols import (
    CollectionSchema,
    FieldDefinition,
    QueryOptions,
    SchemaValidationError,
    WhereClause,
)

SCHEMA = CollectionSchema(
    name="users",
    version="1.0",
    fields={
        "id": FieldDefinition(type="uuid", required=False),
        "email": FieldDefinition(type="email", required=True),
        "age": FieldDefinition(type="number", required=False, min=0, max=150),
    },
    primary_key="id",
)


async def test_insert_find_by_id_and_update_round_trip() -> None:
    store = InMemoryDataStore()
    await store.connect()
    await store.create_collection(SCHEMA)
    record_id = await store.insert("users", {"email": "a@b.com", "age": 30})
    found = await store.find_by_id("users", record_id)
    assert found["email"] == "a@b.com"
    updated = await store.update("users", record_id, {"age": 31})
    assert updated is True
    refetched = await store.find_by_id("users", record_id)
    assert refetched["age"] == 31


async def test_find_with_where_and_pagination() -> None:
    store = InMemoryDataStore()
    await store.connect()
    await store.create_collection(SCHEMA)
    for i in range(5):
        await store.insert("users", {"email": f"user{i}@b.com", "age": 20 + i})

    result = await store.find(
        "users",
        QueryOptions(where=[WhereClause(field="age", operator=">=", value=22)], limit=2, offset=0),
    )
    assert result.total == 3
    assert len(result.data) == 2
    assert result.has_more is True


async def test_transaction_rollback_restores_prior_state() -> None:
    store = InMemoryDataStore()
    await store.connect()
    await store.create_collection(SCHEMA)
    record_id = await store.insert("users", {"email": "a@b.com"})

    tx = await store.begin_transaction()
    await store.update("users", record_id, {"email": "changed@b.com"})
    await tx.rollback()

    restored = await store.find_by_id("users", record_id)
    assert restored["email"] == "a@b.com"


async def test_bulk_insert_reports_inserted_count() -> None:
    store = InMemoryDataStore()
    await store.connect()
    await store.create_collection(SCHEMA)
    result = await store.bulk_insert("users", [{"email": "a@b.com"}, {"email": "b@b.com"}])
    assert result["inserted"] == 2
    assert result["failed"] == 0


async def test_datastore_plugin_ds_insert_tool_rejects_invalid_email() -> None:
    store = InMemoryDataStore()
    await store.connect()
    plugin = DataStorePlugin(store, DataStorePluginOptions(schemas=[SCHEMA]))
    tools = plugin._build_tools()
    insert_tool = next(t for t in tools if t.name == "ds_insert")
    plugin._connected = True  # normally set by on_register()'s fire-and-forget connect()

    with pytest.raises(SchemaValidationError):
        await insert_tool.execute({"collection": "users", "record": {"email": "not-an-email"}})


async def test_datastore_plugin_ds_insert_tool_accepts_valid_record() -> None:
    store = InMemoryDataStore()
    await store.connect()
    plugin = DataStorePlugin(store, DataStorePluginOptions(schemas=[SCHEMA]))
    plugin._connected = True
    tools = plugin._build_tools()
    insert_tool = next(t for t in tools if t.name == "ds_insert")

    result = await insert_tool.execute({"collection": "users", "record": {"email": "valid@b.com"}})
    assert result["status"] == "inserted"
