// adapters/data/datastore-plugin.ts
// DataStorePlugin — IPlugin that registers IDataStore as OOAgent tools.
// Exposes insert, find, findById, update, delete, count as callable ITool specs.
// The agent can query and write to any IDataStore backend via tool calls.

import { randomUUID } from 'node:crypto'
import type {
  IDataStore,
  CollectionSchema,
  WhereClause,
  QueryOptions,
} from './protocols.js'
import { DefaultNormalizer } from './normalizer.js'
import { DefaultSchemaValidator } from './validator.js'

interface IPluginRuntime {
  readonly pluginId: string
  readonly version:  string
  onRegister(agent: unknown): void
  onDispose(): void
  contributes(): { tools?: ITool[] }
}

interface ITool {
  readonly name: string
  readonly description: string
  inputSchema(): Record<string, unknown>
  execute(args: Record<string, unknown>): Promise<unknown>
  toVendorSpec(vendor: string): Record<string, unknown>
}

// Thin ITool wrapper around a DataStore operation
class DataStoreTool implements ITool {
  constructor(
    readonly name: string,
    readonly description: string,
    private readonly _schema: () => Record<string, unknown>,
    private readonly _execute: (args: Record<string, unknown>) => Promise<unknown>,
  ) {}

  inputSchema(): Record<string, unknown> { return this._schema() }
  async execute(args: Record<string, unknown>): Promise<unknown> { return this._execute(args) }

  toVendorSpec(_vendor: string): Record<string, unknown> {
    return { name: this.name, description: this.description, input_schema: this.inputSchema() }
  }
}

export interface DataStorePluginOptions {
  /** Collections to expose. If omitted, all operations are unlocked. */
  allowedCollections?: string[]
  /** Schemas per collection for validation + normalization. */
  schemas?: CollectionSchema[]
  /** Whether to validate+normalize writes. Default: true */
  enforceSchema?: boolean
}

export class DataStorePlugin implements IPluginRuntime {
  readonly pluginId = 'ooagent.datastore'
  readonly version  = '2026.06.01'

  private readonly _store:     IDataStore
  private readonly _opts:      DataStorePluginOptions
  private readonly _normalizer = new DefaultNormalizer()
  private readonly _validator  = new DefaultSchemaValidator()
  private readonly _schemaMap  = new Map<string, CollectionSchema>()
  private _connected = false

  constructor(store: IDataStore, opts: DataStorePluginOptions = {}) {
    this._store = store
    this._opts  = { enforceSchema: true, ...opts }
    for (const s of opts.schemas ?? []) {
      this._schemaMap.set(s.name, s)
    }
  }

  onRegister(_agent: unknown): void {
    this._store.connect().then(() => {
      this._connected = true
    }).catch(err => {
      console.error(`[DataStorePlugin] Connect failed: ${(err as Error).message}`)
    })
  }

  onDispose(): void {
    if (this._connected) {
      this._store.disconnect().catch(() => undefined)
      this._connected = false
    }
  }

  contributes(): { tools: ITool[] } {
    return { tools: this._buildTools() }
  }

  private _isAllowed(collection: string): boolean {
    if (!this._opts.allowedCollections) return true
    return this._opts.allowedCollections.includes(collection)
  }

  private _guard(collection: string): void {
    if (!this._isAllowed(collection)) {
      throw new Error(`Collection '${collection}' is not in the allowedCollections list`)
    }
    if (!this._connected) {
      throw new Error('DataStore is not connected')
    }
  }

  private _normalizeAndValidate(collection: string, record: Record<string, unknown>): Record<string, unknown> {
    const schema = this._schemaMap.get(collection)
    if (!schema || !this._opts.enforceSchema) return record

    const { normalized, warnings } = this._normalizer.normalize(record, schema)
    if (warnings.length > 0) {
      console.warn(`[DataStorePlugin] Normalization warnings for '${collection}':`, warnings)
    }

    // Assign a primary key if missing
    const pk = Array.isArray(schema.primaryKey) ? schema.primaryKey[0] : schema.primaryKey
    if (!(normalized as Record<string, unknown>)[pk]) {
      (normalized as Record<string, unknown>)[pk] = randomUUID()
    }

    const validation = this._validator.validate(normalized as Record<string, unknown>, schema)
    if (!validation.valid) {
      throw new Error(
        `Schema validation failed for '${collection}':\n` +
        validation.errors.map(e => `  ${e.field}: ${e.message}`).join('\n'),
      )
    }

    return normalized as Record<string, unknown>
  }

  private _buildTools(): ITool[] {
    const self = this
    return [
      // ── ds_insert ────────────────────────────────────────────────────────
      new DataStoreTool(
        'ds_insert',
        'Insert a single record into a datastore collection. Validates and normalizes before writing.',
        () => ({
          type: 'object',
          properties: {
            collection: { type: 'string', description: 'Target collection name' },
            record:     { type: 'object', description: 'Record to insert' },
          },
          required: ['collection', 'record'],
        }),
        async (args) => {
          const { collection, record } = args as { collection: string; record: Record<string, unknown> }
          self._guard(collection)
          const clean = self._normalizeAndValidate(collection, record)
          const id = await self._store.insert(collection, clean)
          return { id, collection, status: 'inserted' }
        },
      ),

      // ── ds_find ──────────────────────────────────────────────────────────
      new DataStoreTool(
        'ds_find',
        'Query records from a datastore collection with optional filtering, ordering, and pagination.',
        () => ({
          type: 'object',
          properties: {
            collection: { type: 'string' },
            where: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  field:    { type: 'string' },
                  operator: { type: 'string', enum: ['=', '!=', '<', '<=', '>', '>=', 'in', 'not_in', 'like', 'exists'] },
                  value:    {},
                },
                required: ['field', 'operator', 'value'],
              },
            },
            limit:  { type: 'number', minimum: 1, maximum: 1000, default: 20 },
            offset: { type: 'number', minimum: 0, default: 0 },
            orderBy: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  field:     { type: 'string' },
                  direction: { type: 'string', enum: ['asc', 'desc'] },
                },
              },
            },
          },
          required: ['collection'],
        }),
        async (args) => {
          const { collection, where, limit, offset, orderBy } = args as {
            collection: string
            where?: WhereClause[]
            limit?:  number
            offset?: number
            orderBy?: QueryOptions['orderBy']
          }
          self._guard(collection)
          return self._store.find(collection, { where, limit, offset, orderBy })
        },
      ),

      // ── ds_find_by_id ────────────────────────────────────────────────────
      new DataStoreTool(
        'ds_find_by_id',
        'Retrieve a single record by its primary key ID.',
        () => ({
          type: 'object',
          properties: {
            collection: { type: 'string' },
            id:         { type: 'string' },
          },
          required: ['collection', 'id'],
        }),
        async (args) => {
          const { collection, id } = args as { collection: string; id: string }
          self._guard(collection)
          const record = await self._store.findById(collection, id)
          return record ?? { error: `Record '${id}' not found in '${collection}'` }
        },
      ),

      // ── ds_update ────────────────────────────────────────────────────────
      new DataStoreTool(
        'ds_update',
        'Update a record by ID with a partial patch. Validates patch fields against schema.',
        () => ({
          type: 'object',
          properties: {
            collection: { type: 'string' },
            id:         { type: 'string' },
            patch:      { type: 'object', description: 'Fields to update (partial)' },
          },
          required: ['collection', 'id', 'patch'],
        }),
        async (args) => {
          const { collection, id, patch } = args as { collection: string; id: string; patch: Record<string, unknown> }
          self._guard(collection)
          const updated = await self._store.update(collection, id, patch)
          return { id, collection, updated, status: updated ? 'updated' : 'not_found' }
        },
      ),

      // ── ds_upsert ────────────────────────────────────────────────────────
      new DataStoreTool(
        'ds_upsert',
        'Insert or update a record based on match fields. Normalizes and validates before writing.',
        () => ({
          type: 'object',
          properties: {
            collection:  { type: 'string' },
            record:      { type: 'object' },
            matchFields: { type: 'array', items: { type: 'string' }, description: 'Fields to match for update detection' },
          },
          required: ['collection', 'record', 'matchFields'],
        }),
        async (args) => {
          const { collection, record, matchFields } = args as { collection: string; record: Record<string, unknown>; matchFields: string[] }
          self._guard(collection)
          const clean = self._normalizeAndValidate(collection, record)
          return self._store.upsert(collection, clean, matchFields)
        },
      ),

      // ── ds_delete ────────────────────────────────────────────────────────
      new DataStoreTool(
        'ds_delete',
        'Delete a record by ID from a collection.',
        () => ({
          type: 'object',
          properties: {
            collection: { type: 'string' },
            id:         { type: 'string' },
          },
          required: ['collection', 'id'],
        }),
        async (args) => {
          const { collection, id } = args as { collection: string; id: string }
          self._guard(collection)
          const deleted = await self._store.delete(collection, id)
          return { id, collection, deleted, status: deleted ? 'deleted' : 'not_found' }
        },
      ),

      // ── ds_count ─────────────────────────────────────────────────────────
      new DataStoreTool(
        'ds_count',
        'Count records in a collection with optional filtering.',
        () => ({
          type: 'object',
          properties: {
            collection: { type: 'string' },
            where: { type: 'array' },
          },
          required: ['collection'],
        }),
        async (args) => {
          const { collection, where } = args as { collection: string; where?: WhereClause[] }
          self._guard(collection)
          const count = await self._store.count(collection, where)
          return { collection, count }
        },
      ),
    ]
  }
}
