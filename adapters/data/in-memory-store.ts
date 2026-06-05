// adapters/data/in-memory-store.ts
// InMemoryDataStore — reference IDataStore implementation for testing.
// Deterministic, zero-dependency, no I/O. Used in unit tests and local dev.
// Also serves as the conformance reference for all other IDataStore adapters.

import { randomUUID } from 'node:crypto'
import type {
  CollectionSchema,
  DataStoreKind,
  IDataStore,
  ITransaction,
  IsolationLevel,
  PagedResult,
  QueryOptions,
  WhereClause,
} from './protocols.js'

class InMemoryTransaction implements ITransaction {
  private _active = true
  private readonly _snapshots: Map<string, Map<string, Record<string, unknown>>>
  private readonly _store: InMemoryDataStore

  constructor(store: InMemoryDataStore, snapshots: Map<string, Map<string, Record<string, unknown>>>) {
    this._store = store
    this._snapshots = snapshots
  }

  get isActive(): boolean { return this._active }

  async commit(): Promise<void> {
    if (!this._active) throw new Error('Transaction already completed')
    this._active = false
    // Changes are already applied to the live store; commit is a no-op here
    // (optimistic concurrency — real adapters implement MVCC)
  }

  async rollback(): Promise<void> {
    if (!this._active) throw new Error('Transaction already completed')
    this._active = false
    // Restore pre-transaction snapshots
    this._store._restoreSnapshots(this._snapshots)
  }
}

export class InMemoryDataStore implements IDataStore {
  readonly kind:    DataStoreKind = 'nosql'
  readonly storeId: string

  private _connected = false
  private readonly _collections = new Map<string, Map<string, Record<string, unknown>>>()
  private readonly _schemas     = new Map<string, CollectionSchema>()

  constructor(storeId = 'in-memory') {
    this.storeId = storeId
  }

  get isConnected(): boolean { return this._connected }

  async connect():    Promise<void> { this._connected = true }
  async disconnect(): Promise<void> { this._connected = false }
  async ping():       Promise<boolean> { return this._connected }

  async createCollection(schema: CollectionSchema): Promise<void> {
    if (!this._collections.has(schema.name)) {
      this._collections.set(schema.name, new Map())
    }
    this._schemas.set(schema.name, schema)
  }

  async dropCollection(name: string): Promise<void> {
    this._collections.delete(name)
    this._schemas.delete(name)
  }

  async collectionExists(name: string): Promise<boolean> {
    return this._collections.has(name)
  }

  async listCollections(): Promise<string[]> {
    return Array.from(this._collections.keys())
  }

  async insert<T extends Record<string, unknown>>(collection: string, record: T): Promise<string> {
    const coll = this._getCollection(collection)
    const id   = (record['id'] as string | undefined) ?? randomUUID()
    coll.set(id, { ...record, id })
    return id
  }

  async insertMany<T extends Record<string, unknown>>(collection: string, records: T[]): Promise<string[]> {
    return Promise.all(records.map(r => this.insert(collection, r)))
  }

  async findById<T extends Record<string, unknown>>(collection: string, id: string): Promise<T | null> {
    const coll = this._getCollection(collection)
    return (coll.get(id) as T | undefined) ?? null
  }

  async find<T extends Record<string, unknown>>(
    collection: string,
    options:    QueryOptions<T> = {},
  ): Promise<PagedResult<T>> {
    const coll   = this._getCollection(collection)
    let   results = Array.from(coll.values()) as T[]

    if (options.where) {
      results = results.filter(r => this._applyWhere(r, options.where!))
    }

    if (options.orderBy) {
      for (const { field, direction } of [...options.orderBy].reverse()) {
        results.sort((a, b) => {
          const av = a[field as string] as number | string
          const bv = b[field as string] as number | string
          const cmp = av < bv ? -1 : av > bv ? 1 : 0
          return direction === 'asc' ? cmp : -cmp
        })
      }
    }

    const total   = results.length
    const offset  = options.offset  ?? 0
    const limit   = options.limit   ?? 100
    const page    = results.slice(offset, offset + limit)

    if (options.select) {
      const keys = options.select as string[]
      return {
        data:    page.map(r => Object.fromEntries(keys.map(k => [k, r[k]])) as T),
        total, limit, offset,
        hasMore: offset + limit < total,
      }
    }

    return { data: page, total, limit, offset, hasMore: offset + limit < total }
  }

  async findOne<T extends Record<string, unknown>>(
    collection: string,
    where:      WhereClause[],
  ): Promise<T | null> {
    const result = await this.find<T>(collection, { where, limit: 1 })
    return result.data[0] ?? null
  }

  async update<T extends Record<string, unknown>>(
    collection: string,
    id:         string,
    patch:      Partial<T>,
  ): Promise<boolean> {
    const coll = this._getCollection(collection)
    const existing = coll.get(id)
    if (!existing) return false
    coll.set(id, { ...existing, ...patch, id })
    return true
  }

  async upsert<T extends Record<string, unknown>>(
    collection:  string,
    record:      T,
    matchFields: (keyof T)[],
  ): Promise<{ id: string; created: boolean }> {
    const where: WhereClause[] = matchFields.map(f => ({
      field:    f as string,
      operator: '=' as const,
      value:    record[f],
    }))
    const existing = await this.findOne<T>(collection, where)
    if (existing) {
      const id = existing['id'] as string
      await this.update(collection, id, record)
      return { id, created: false }
    }
    const id = await this.insert(collection, record)
    return { id, created: true }
  }

  async delete(collection: string, id: string): Promise<boolean> {
    const coll = this._getCollection(collection)
    return coll.delete(id)
  }

  async count(collection: string, where?: WhereClause[]): Promise<number> {
    const result = await this.find(collection, { where, limit: Number.MAX_SAFE_INTEGER })
    return result.total
  }

  async beginTransaction(_isolation?: IsolationLevel): Promise<ITransaction> {
    // Snapshot all collections for rollback
    const snapshots = new Map<string, Map<string, Record<string, unknown>>>()
    for (const [name, coll] of this._collections) {
      snapshots.set(name, new Map(Array.from(coll.entries()).map(([k, v]) => [k, { ...v }])))
    }
    return new InMemoryTransaction(this, snapshots)
  }

  async bulkInsert<T extends Record<string, unknown>>(
    collection: string,
    records:    T[],
    options:    { batchSize?: number; onError?: 'abort' | 'skip' } = {},
  ): Promise<{ inserted: number; failed: number; errors: Array<{ index: number; error: string }> }> {
    const onError = options.onError ?? 'abort'
    let inserted = 0
    let failed   = 0
    const errors: Array<{ index: number; error: string }> = []

    for (let i = 0; i < records.length; i++) {
      try {
        await this.insert(collection, records[i])
        inserted++
      } catch (err) {
        failed++
        errors.push({ index: i, error: (err as Error).message })
        if (onError === 'abort') break
      }
    }

    return { inserted, failed, errors }
  }

  // Internal: used by InMemoryTransaction.rollback()
  _restoreSnapshots(snapshots: Map<string, Map<string, Record<string, unknown>>>): void {
    for (const [name, snapshot] of snapshots) {
      this._collections.set(name, snapshot)
    }
  }

  private _getCollection(name: string): Map<string, Record<string, unknown>> {
    if (!this._collections.has(name)) {
      this._collections.set(name, new Map())
    }
    return this._collections.get(name)!
  }

  private _applyWhere(record: Record<string, unknown>, clauses: WhereClause[]): boolean {
    return clauses.every(({ field, operator, value }) => {
      const rv = record[field]
      switch (operator) {
        case '=':       return rv === value
        case '!=':      return rv !== value
        case '<':       return (rv as number) < (value as number)
        case '<=':      return (rv as number) <= (value as number)
        case '>':       return (rv as number) > (value as number)
        case '>=':      return (rv as number) >= (value as number)
        case 'in':      return Array.isArray(value) && value.includes(rv)
        case 'not_in':  return Array.isArray(value) && !value.includes(rv)
        case 'like':    return typeof rv === 'string' && rv.includes(String(value).replace(/%/g, ''))
        case 'exists':  return rv !== undefined && rv !== null
        default:        return true
      }
    })
  }
}
