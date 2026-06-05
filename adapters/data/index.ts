// adapters/data/index.ts — barrel export for database adapters
export type {
  IDataStore,
  INormalizer,
  ISchemaValidator,
  ITransaction,
  IDataStoreTool,
  CollectionSchema,
  FieldDefinition,
  FieldType,
  DataStoreKind,
  WhereClause,
  QueryOptions,
  PagedResult,
  ValidationResult,
  ValidationError,
  NormalizationResult,
  IsolationLevel,
  SortOrder,
} from './protocols.js'

export { DefaultNormalizer }    from './normalizer.js'
export { DefaultSchemaValidator } from './validator.js'
export { InMemoryDataStore }    from './in-memory-store.js'
export { DataStorePlugin }      from './datastore-plugin.js'
export type { DataStorePluginOptions } from './datastore-plugin.js'
