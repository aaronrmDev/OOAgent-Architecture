"""adapters/data/in_memory_store.py — InMemoryDataStore.

Reference IDataStore implementation for testing. Deterministic,
zero-dependency, no I/O. Used in unit tests and local dev. Also serves as the
conformance reference for all other IDataStore adapters.
"""

from __future__ import annotations

import functools
import uuid
from collections.abc import Callable
from typing import Any, Literal

from ooagent.adapters.data.protocols import (
    CollectionSchema,
    DataStoreKind,
    IDataStore,
    IsolationLevel,
    ITransaction,
    PagedResult,
    QueryOptions,
    SortOrder,
    TransactionError,
    WhereClause,
)

# Number.MAX_SAFE_INTEGER — used by count() to page through every record.
_MAX_SAFE_INTEGER = 2**53 - 1


def _make_comparator(
    field: str, direction: SortOrder
) -> Callable[[dict[str, Any], dict[str, Any]], int]:
    """Builds a JS-`Array.prototype.sort`-equivalent 2-arg comparator.

    Values that are not directly ordering-comparable (e.g. mixed types) are
    treated as equal rather than raising — mirroring JS's permissive `<`/`>`
    operators, which never throw for this comparison.
    """

    def _cmp(a: dict[str, Any], b: dict[str, Any]) -> int:
        av = a.get(field)
        bv = b.get(field)
        try:
            # av/bv may be None or otherwise mutually non-comparable (e.g.
            # str vs int); the surrounding try/except TypeError is the
            # intentional guard for that (mirrors JS's permissive `<`/`>`,
            # which never throws) — not a bug to fix here.
            if av < bv:  # type: ignore[operator]
                cmp = -1
            elif av > bv:  # type: ignore[operator]
                cmp = 1
            else:
                cmp = 0
        except TypeError:
            cmp = 0
        return cmp if direction == "asc" else -cmp

    return _cmp


class InMemoryTransaction(ITransaction):
    def __init__(
        self,
        store: InMemoryDataStore,
        snapshots: dict[str, dict[str, dict[str, Any]]],
    ) -> None:
        self._active = True
        self._snapshots = snapshots
        self._store = store

    @property
    def is_active(self) -> bool:
        return self._active

    async def commit(self) -> None:
        if not self._active:
            raise TransactionError("Transaction already completed")
        self._active = False
        # Changes are already applied to the live store; commit is a no-op
        # here (optimistic concurrency — real adapters implement MVCC).

    async def rollback(self) -> None:
        if not self._active:
            raise TransactionError("Transaction already completed")
        self._active = False
        # Restore pre-transaction snapshots.
        self._store._restore_snapshots(self._snapshots)


class InMemoryDataStore(IDataStore):
    def __init__(self, store_id: str = "in-memory") -> None:
        self._store_id = store_id
        self._connected = False
        self._collections: dict[str, dict[str, dict[str, Any]]] = {}
        self._schemas: dict[str, CollectionSchema] = {}

    @property
    def kind(self) -> DataStoreKind:
        return "nosql"

    @property
    def store_id(self) -> str:
        return self._store_id

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def ping(self) -> bool:
        return self._connected

    async def create_collection(self, schema: CollectionSchema) -> None:
        if schema.name not in self._collections:
            self._collections[schema.name] = {}
        self._schemas[schema.name] = schema

    async def drop_collection(self, name: str) -> None:
        self._collections.pop(name, None)
        self._schemas.pop(name, None)

    async def collection_exists(self, name: str) -> bool:
        return name in self._collections

    async def list_collections(self) -> list[str]:
        return list(self._collections.keys())

    async def insert(self, collection: str, record: dict[str, Any]) -> str:
        coll = self._get_collection(collection)
        record_id = record.get("id")
        id_ = record_id if record_id is not None else str(uuid.uuid4())
        coll[id_] = {**record, "id": id_}
        return id_

    async def insert_many(self, collection: str, records: list[dict[str, Any]]) -> list[str]:
        ids = []
        for r in records:
            ids.append(await self.insert(collection, r))
        return ids

    async def find_by_id(self, collection: str, id: str) -> dict[str, Any] | None:
        coll = self._get_collection(collection)
        return coll.get(id)

    async def find(
        self, collection: str, options: QueryOptions | None = None
    ) -> PagedResult[dict[str, Any]]:
        options = options or QueryOptions()
        coll = self._get_collection(collection)
        results: list[dict[str, Any]] = list(coll.values())

        if options.where:
            results = [r for r in results if self._apply_where(r, options.where)]

        if options.order_by:
            for spec in reversed(options.order_by):
                results.sort(key=functools.cmp_to_key(_make_comparator(spec.field, spec.direction)))

        total = len(results)
        offset = options.offset if options.offset is not None else 0
        limit = options.limit if options.limit is not None else 100
        page = results[offset : offset + limit]

        if options.select:
            keys = options.select
            data = [{k: r.get(k) for k in keys} for r in page]
            return PagedResult(
                data=data,
                total=total,
                limit=limit,
                offset=offset,
                has_more=offset + limit < total,
            )

        return PagedResult(
            data=page,
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + limit < total,
        )

    async def find_one(self, collection: str, where: list[WhereClause]) -> dict[str, Any] | None:
        result = await self.find(collection, QueryOptions(where=where, limit=1))
        return result.data[0] if result.data else None

    async def update(self, collection: str, id: str, patch: dict[str, Any]) -> bool:
        coll = self._get_collection(collection)
        existing = coll.get(id)
        if existing is None:
            return False
        coll[id] = {**existing, **patch, "id": id}
        return True

    async def upsert(
        self, collection: str, record: dict[str, Any], match_fields: list[str]
    ) -> dict[str, Any]:
        where = [WhereClause(field=f, operator="=", value=record.get(f)) for f in match_fields]
        existing = await self.find_one(collection, where)
        if existing is not None:
            id_ = existing["id"]
            await self.update(collection, id_, record)
            return {"id": id_, "created": False}
        id_ = await self.insert(collection, record)
        return {"id": id_, "created": True}

    async def delete(self, collection: str, id: str) -> bool:
        coll = self._get_collection(collection)
        return coll.pop(id, None) is not None

    async def count(self, collection: str, where: list[WhereClause] | None = None) -> int:
        result = await self.find(collection, QueryOptions(where=where, limit=_MAX_SAFE_INTEGER))
        return result.total

    async def begin_transaction(self, isolation: IsolationLevel | None = None) -> ITransaction:
        # Snapshot all collections for rollback.
        snapshots: dict[str, dict[str, dict[str, Any]]] = {
            name: {k: {**v} for k, v in coll.items()} for name, coll in self._collections.items()
        }
        return InMemoryTransaction(self, snapshots)

    async def bulk_insert(
        self,
        collection: str,
        records: list[dict[str, Any]],
        batch_size: int | None = None,
        on_error: Literal["abort", "skip"] = "abort",
    ) -> dict[str, Any]:
        inserted = 0
        failed = 0
        errors: list[dict[str, Any]] = []

        for i, record in enumerate(records):
            try:
                await self.insert(collection, record)
                inserted += 1
            except Exception as err:  # noqa: BLE001 - mirrors TS catch-all
                failed += 1
                errors.append({"index": i, "error": str(err)})
                if on_error == "abort":
                    break

        return {"inserted": inserted, "failed": failed, "errors": errors}

    # Internal: used by InMemoryTransaction.rollback()
    def _restore_snapshots(self, snapshots: dict[str, dict[str, dict[str, Any]]]) -> None:
        for name, snapshot in snapshots.items():
            self._collections[name] = snapshot

    def _get_collection(self, name: str) -> dict[str, dict[str, Any]]:
        if name not in self._collections:
            self._collections[name] = {}
        return self._collections[name]

    def _apply_where(self, record: dict[str, Any], clauses: list[WhereClause]) -> bool:
        def _matches(clause: WhereClause) -> bool:
            rv = record.get(clause.field)
            value = clause.value
            op = clause.operator
            if op == "=":
                return bool(rv == value)
            if op == "!=":
                return bool(rv != value)
            if op == "<":
                return bool(rv < value)
            if op == "<=":
                return bool(rv <= value)
            if op == ">":
                return bool(rv > value)
            if op == ">=":
                return bool(rv >= value)
            if op == "in":
                return isinstance(value, list) and rv in value
            if op == "not_in":
                return isinstance(value, list) and rv not in value
            if op == "like":
                return isinstance(rv, str) and str(value).replace("%", "") in rv
            if op == "exists":
                return rv is not None
            return True

        return all(_matches(c) for c in clauses)
