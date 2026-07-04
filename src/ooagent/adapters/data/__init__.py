"""ooagent/adapters/data/__init__.py — barrel export for database adapters.

Mirrors `adapters/data/index.ts`.
"""

from __future__ import annotations

from ooagent.adapters.data.datastore_plugin import DataStorePlugin, DataStorePluginOptions
from ooagent.adapters.data.in_memory_store import InMemoryDataStore
from ooagent.adapters.data.normalizer import DefaultNormalizer
from ooagent.adapters.data.protocols import (
    CollectionSchema,
    DataStoreGuardError,
    DataStoreKind,
    FieldDefinition,
    FieldType,
    IDataStore,
    IDataStoreTool,
    INormalizer,
    ISchemaValidator,
    IsolationLevel,
    ITransaction,
    NormalizationResult,
    PagedResult,
    QueryOptions,
    SchemaValidationError,
    SortOrder,
    TransactionError,
    ValidationError,
    ValidationResult,
    WhereClause,
)
from ooagent.adapters.data.validator import DefaultSchemaValidator

__all__ = [
    "IDataStore",
    "INormalizer",
    "ISchemaValidator",
    "ITransaction",
    "IDataStoreTool",
    "CollectionSchema",
    "FieldDefinition",
    "FieldType",
    "DataStoreKind",
    "WhereClause",
    "QueryOptions",
    "PagedResult",
    "ValidationResult",
    "ValidationError",
    "NormalizationResult",
    "IsolationLevel",
    "SortOrder",
    "DefaultNormalizer",
    "DefaultSchemaValidator",
    "InMemoryDataStore",
    "DataStorePlugin",
    "DataStorePluginOptions",
    "TransactionError",
    "DataStoreGuardError",
    "SchemaValidationError",
]
