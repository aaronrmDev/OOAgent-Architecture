"""adapters/data/protocols.py — IDataStore, INormalizer, ISchemaValidator.

Database-agnostic persistence interface. Works with any SQL (PostgreSQL,
MySQL, SQLite) or NoSQL (MongoDB, DynamoDB, Redis, Firestore) backend via an
adapter. Zero runtime dependencies here.

Design:
 - IDataStore is the stable contract (DIP). Adapters implement it.
 - INormalizer enforces zero-defect data processing before any write.
 - ISchemaValidator gates reads and writes against a declared schema.
 - ITransaction provides ACID-like semantics for both SQL and NoSQL.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Literal, TypeVar

from ooagent.core.protocols import ITool, OOAgentError

# ── Primitive types ───────────────────────────────────────────────────────────

DataStoreKind = Literal["sql", "nosql", "kv", "graph", "timeseries"]

FieldType = Literal[
    "string",
    "number",
    "boolean",
    "date",
    "uuid",
    "email",
    "url",
    "json",
    "enum",
    "array",
    "object",
]

SortOrder = Literal["asc", "desc"]

IsolationLevel = Literal[
    "read_uncommitted",
    "read_committed",
    "repeatable_read",
    "serializable",
]

# A record is always a plain string-keyed mapping — the runtime shape behind
# every TS `T extends Record<string, unknown>` generic parameter in this file.
Record_ = dict[str, Any]

# ── Field / Schema definitions ────────────────────────────────────────────────


@dataclass(frozen=True)
class FieldDefinition:
    type: FieldType
    required: bool
    unique: bool | None = None
    indexed: bool | None = None
    default: Any = None
    min: float | None = None  # numeric/string min value/length
    max: float | None = None  # numeric/string max value/length
    pattern: str | None = None  # regex for string validation
    enum_values: list[str] | None = None  # valid values for 'enum' type
    items: FieldDefinition | None = None  # element type for 'array'
    properties: dict[str, FieldDefinition] | None = None  # for 'object'


@dataclass(frozen=True)
class IndexSpec:
    fields: list[str]
    unique: bool | None = None


@dataclass(frozen=True)
class CollectionSchema:
    name: str
    version: str
    fields: dict[str, FieldDefinition]
    primary_key: str | list[str]
    indexes: list[IndexSpec] | None = None


# ── Query types ───────────────────────────────────────────────────────────────

WhereOperator = Literal[
    "=",
    "!=",
    "<",
    "<=",
    ">",
    ">=",
    "in",
    "not_in",
    "like",
    "exists",
]


@dataclass(frozen=True)
class WhereClause:
    field: str
    operator: WhereOperator
    value: Any


@dataclass(frozen=True)
class OrderBySpec:
    field: str
    direction: SortOrder


@dataclass(frozen=True)
class QueryOptions:
    where: list[WhereClause] | None = None
    select: list[str] | None = None
    order_by: list[OrderBySpec] | None = None
    limit: int | None = None
    offset: int | None = None


# ── Result types ──────────────────────────────────────────────────────────────

T = TypeVar("T")


@dataclass(frozen=True)
class PagedResult(Generic[T]):
    data: list[T]
    total: int
    limit: int
    offset: int
    has_more: bool


# ── Validation result ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ValidationError:
    field: str
    message: str
    value: Any


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[ValidationError]


# ── Normalization result ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class FieldChange:
    field: str
    original: Any
    normalized: Any


@dataclass(frozen=True)
class NormalizationResult(Generic[T]):
    normalized: T
    changes: list[FieldChange]
    warnings: list[str]


# ── Errors ────────────────────────────────────────────────────────────────────
# Reuse ooagent.core.protocols.OOAgentError as the common base — this module
# does not invent an unrelated exception hierarchy.


class TransactionError(OOAgentError):
    """Raised by ITransaction.commit()/rollback() when the transaction has
    already completed (mirrors the TS `throw new Error('Transaction already
    completed')` guard in in-memory-store.ts)."""


class DataStoreGuardError(OOAgentError):
    """Raised when a datastore operation is attempted against a disallowed
    collection, or while the store is not connected."""


class SchemaValidationError(OOAgentError):
    """Raised when a record fails ISchemaValidator.validate() during a
    normalize-then-validate write path. Carries the underlying field errors."""

    def __init__(self, collection: str, errors: list[ValidationError]) -> None:
        detail = "\n".join(f"  {e.field}: {e.message}" for e in errors)
        super().__init__(f"Schema validation failed for '{collection}':\n{detail}")
        self.collection = collection
        self.errors = errors


# ── Transaction ───────────────────────────────────────────────────────────────


class ITransaction(ABC):
    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...

    @property
    @abstractmethod
    def is_active(self) -> bool: ...


# ── Core interfaces ───────────────────────────────────────────────────────────


class IDataStore(ABC):
    """Stable, database-agnostic CRUD + query interface.
    Implement this for any backend: PostgreSQL, MongoDB, DynamoDB, Redis, etc.
    """

    @property
    @abstractmethod
    def kind(self) -> DataStoreKind: ...

    @property
    @abstractmethod
    def store_id(self) -> str: ...

    # Lifecycle
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def ping(self) -> bool: ...

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...

    # Schema management
    @abstractmethod
    async def create_collection(self, schema: CollectionSchema) -> None: ...

    @abstractmethod
    async def drop_collection(self, name: str) -> None: ...

    @abstractmethod
    async def collection_exists(self, name: str) -> bool: ...

    @abstractmethod
    async def list_collections(self) -> list[str]: ...

    # CRUD
    @abstractmethod
    async def insert(self, collection: str, record: Record_) -> str:
        """Returns the generated (or supplied) ID."""

    @abstractmethod
    async def insert_many(self, collection: str, records: list[Record_]) -> list[str]: ...

    @abstractmethod
    async def find_by_id(self, collection: str, id: str) -> Record_ | None: ...

    @abstractmethod
    async def find(
        self, collection: str, options: QueryOptions | None = None
    ) -> PagedResult[Record_]: ...

    @abstractmethod
    async def find_one(self, collection: str, where: list[WhereClause]) -> Record_ | None: ...

    @abstractmethod
    async def update(self, collection: str, id: str, patch: Record_) -> bool:
        """Returns True if the record was found and updated."""

    @abstractmethod
    async def upsert(
        self, collection: str, record: Record_, match_fields: list[str]
    ) -> dict[str, Any]:
        """Returns {"id": str, "created": bool}."""

    @abstractmethod
    async def delete(self, collection: str, id: str) -> bool: ...

    @abstractmethod
    async def count(self, collection: str, where: list[WhereClause] | None = None) -> int: ...

    # Transactions
    @abstractmethod
    async def begin_transaction(self, isolation: IsolationLevel | None = None) -> ITransaction: ...

    # Bulk operations (zero-defect: all-or-nothing / skip, per `on_error`)
    @abstractmethod
    async def bulk_insert(
        self,
        collection: str,
        records: list[Record_],
        batch_size: int | None = None,
        on_error: Literal["abort", "skip"] = "abort",
    ) -> dict[str, Any]:
        """Returns {"inserted": int, "failed": int, "errors": [{"index": int, "error": str}]}."""


class INormalizer(ABC, Generic[T]):
    """Zero-defect data processor.
    Applied BEFORE every write. Normalizes, trims, coerces, and deduplicates.
    Guarantees the data going into the store is always clean.
    """

    @abstractmethod
    def normalize(self, raw: Any, schema: CollectionSchema) -> NormalizationResult[T]: ...


class ISchemaValidator(ABC):
    """Validates records against a CollectionSchema.
    Applied after normalization, before write. A validation failure is a
    hard block — data is never written in an invalid state.
    """

    @abstractmethod
    def validate(self, record: Record_, schema: CollectionSchema) -> ValidationResult: ...


class IDataStoreTool(ABC):
    """Wraps IDataStore as a set of OOAgent ITools.
    Allows LLM agents to query and write to the store via tool calls.

    Declared in the TS source (protocols.ts) and re-exported from index.ts,
    but not implemented by any file in this slice — DataStorePlugin builds
    its tools directly rather than through this interface. Kept for parity.
    """

    @property
    @abstractmethod
    def store_id(self) -> str: ...

    @abstractmethod
    def tool_specs(self) -> list[ITool]:
        """Returns the set of tool specs to register with ToolRegistry."""
