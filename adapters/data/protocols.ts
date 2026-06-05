// adapters/data/protocols.ts
// IDataStore — database-agnostic persistence interface.
// Works with any SQL (PostgreSQL, MySQL, SQLite) or NoSQL (MongoDB, DynamoDB,
// Redis, Firestore) backend via an adapter. Zero runtime dependencies here.
//
// Design:
//  - IDataStore is the stable contract (DIP). Adapters implement it.
//  - INormalizer enforces zero-defect data processing before any write.
//  - ISchemaValidator gates reads and writes against a declared schema.
//  - ITransaction provides ACID-like semantics for both SQL and NoSQL.

// ── Primitive types ───────────────────────────────────────────────────────────

export type DataStoreKind = 'sql' | 'nosql' | 'kv' | 'graph' | 'timeseries'

export type FieldType =
  | 'string' | 'number' | 'boolean' | 'date'
  | 'uuid'   | 'email'  | 'url'     | 'json'
  | 'enum'   | 'array'  | 'object'

export type SortOrder = 'asc' | 'desc'

export type IsolationLevel =
  | 'read_uncommitted'
  | 'read_committed'
  | 'repeatable_read'
  | 'serializable'

// ── Field / Schema definitions ────────────────────────────────────────────────

export interface FieldDefinition {
  readonly type:       FieldType
  readonly required:   boolean
  readonly unique?:    boolean
  readonly indexed?:   boolean
  readonly default?:   unknown
  readonly min?:       number       // numeric/string min value/length
  readonly max?:       number       // numeric/string max value/length
  readonly pattern?:   string       // regex for string validation
  readonly enumValues?: string[]    // valid values for 'enum' type
  readonly items?:     FieldDefinition  // element type for 'array'
  readonly properties?: Record<string, FieldDefinition>  // for 'object'
}

export interface CollectionSchema {
  readonly name:       string
  readonly version:    string
  readonly fields:     Record<string, FieldDefinition>
  readonly primaryKey: string | string[]
  readonly indexes?:   Array<{ fields: string[]; unique?: boolean }>
}

// ── Query types ───────────────────────────────────────────────────────────────

export interface WhereClause {
  field:    string
  operator: '=' | '!=' | '<' | '<=' | '>' | '>=' | 'in' | 'not_in' | 'like' | 'exists'
  value:    unknown
}

export interface QueryOptions<T = Record<string, unknown>> {
  where?:   WhereClause[]
  select?:  (keyof T)[]
  orderBy?: Array<{ field: keyof T; direction: SortOrder }>
  limit?:   number
  offset?:  number
}

// ── Result types ──────────────────────────────────────────────────────────────

export interface PagedResult<T> {
  readonly data:       T[]
  readonly total:      number
  readonly limit:      number
  readonly offset:     number
  readonly hasMore:    boolean
}

// ── Validation result ─────────────────────────────────────────────────────────

export interface ValidationResult {
  readonly valid:  boolean
  readonly errors: ValidationError[]
}

export interface ValidationError {
  readonly field:   string
  readonly message: string
  readonly value:   unknown
}

// ── Normalization result ──────────────────────────────────────────────────────

export interface NormalizationResult<T> {
  readonly normalized: T
  readonly changes:    Array<{ field: string; original: unknown; normalized: unknown }>
  readonly warnings:   string[]
}

// ── Transaction ───────────────────────────────────────────────────────────────

export interface ITransaction {
  commit():   Promise<void>
  rollback(): Promise<void>
  readonly isActive: boolean
}

// ── Core interfaces ───────────────────────────────────────────────────────────

/**
 * IDataStore — stable, database-agnostic CRUD + query interface.
 * Implement this for any backend: PostgreSQL, MongoDB, DynamoDB, Redis, etc.
 */
export interface IDataStore {
  readonly kind:    DataStoreKind
  readonly storeId: string

  // Lifecycle
  connect():    Promise<void>
  disconnect(): Promise<void>
  ping():       Promise<boolean>
  readonly isConnected: boolean

  // Schema management
  createCollection(schema: CollectionSchema):  Promise<void>
  dropCollection(name: string):                Promise<void>
  collectionExists(name: string):              Promise<boolean>
  listCollections():                           Promise<string[]>

  // CRUD
  insert<T extends Record<string, unknown>>(
    collection: string,
    record:     T,
  ): Promise<string>  // returns generated ID

  insertMany<T extends Record<string, unknown>>(
    collection: string,
    records:    T[],
  ): Promise<string[]>

  findById<T extends Record<string, unknown>>(
    collection: string,
    id:         string,
  ): Promise<T | null>

  find<T extends Record<string, unknown>>(
    collection: string,
    options?:   QueryOptions<T>,
  ): Promise<PagedResult<T>>

  findOne<T extends Record<string, unknown>>(
    collection: string,
    where:      WhereClause[],
  ): Promise<T | null>

  update<T extends Record<string, unknown>>(
    collection: string,
    id:         string,
    patch:      Partial<T>,
  ): Promise<boolean>  // true if record was found and updated

  upsert<T extends Record<string, unknown>>(
    collection: string,
    record:     T,
    matchFields: (keyof T)[],
  ): Promise<{ id: string; created: boolean }>

  delete(collection: string, id: string): Promise<boolean>

  count(collection: string, where?: WhereClause[]): Promise<number>

  // Transactions
  beginTransaction(isolation?: IsolationLevel): Promise<ITransaction>

  // Bulk operations (zero-defect: all-or-nothing)
  bulkInsert<T extends Record<string, unknown>>(
    collection: string,
    records:    T[],
    options?:   { batchSize?: number; onError?: 'abort' | 'skip' },
  ): Promise<{ inserted: number; failed: number; errors: Array<{ index: number; error: string }> }>
}

/**
 * INormalizer — zero-defect data processor.
 * Applied BEFORE every write. Normalizes, trims, coerces, and deduplicates.
 * Guarantees the data going into the store is always clean.
 */
export interface INormalizer<T extends Record<string, unknown>> {
  normalize(raw: unknown, schema: CollectionSchema): NormalizationResult<T>
}

/**
 * ISchemaValidator — validates records against a CollectionSchema.
 * Applied after normalization, before write. A validation failure is a
 * hard block — data is never written in an invalid state.
 */
export interface ISchemaValidator {
  validate(record: Record<string, unknown>, schema: CollectionSchema): ValidationResult
}

/**
 * IDataStoreTool — wraps IDataStore as an OOAgent ITool.
 * Allows LLM agents to query and write to the store via tool calls.
 */
export interface IDataStoreTool {
  readonly storeId: string
  // Returns the set of tool specs to register with ToolRegistry
  toolSpecs(): Array<{ name: string; description: string; inputSchema(): Record<string, unknown>; execute(args: Record<string, unknown>): Promise<unknown> }>
}
