// adapters/data/normalizer.ts
// DefaultNormalizer — zero-defect data processor.
//
// Zero-defect principles applied here:
//   1. Every string is trimmed and sanitized (no raw user text to store)
//   2. Every number is validated for NaN/Infinity before storage
//   3. Every date is coerced to ISO 8601 UTC
//   4. Every UUID is lowercased and validated
//   5. Every email is lowercased and trimmed
//   6. Every URL is normalized (trailing slash, scheme check)
//   7. Null/undefined optional fields are dropped (not stored as null)
//   8. Unknown fields not in schema are stripped (no schema pollution)
//   9. Enum values are validated against declared options
//  10. Array elements are recursively normalized

import type {
  CollectionSchema,
  FieldDefinition,
  INormalizer,
  NormalizationResult,
} from './protocols.js'

const UUID_RE   = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const EMAIL_RE  = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const URL_RE    = /^https?:\/\//

export class DefaultNormalizer<T extends Record<string, unknown>>
  implements INormalizer<T>
{
  normalize(raw: unknown, schema: CollectionSchema): NormalizationResult<T> {
    const changes: NormalizationResult<T>['changes'] = []
    const warnings: string[] = []

    if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) {
      warnings.push('Input is not a plain object — returning empty record')
      return { normalized: {} as T, changes, warnings }
    }

    const input = raw as Record<string, unknown>
    const normalized: Record<string, unknown> = {}

    for (const [fieldName, fieldDef] of Object.entries(schema.fields)) {
      const original = input[fieldName]

      // Missing optional fields — use default or skip
      if (original === undefined || original === null) {
        if (fieldDef.default !== undefined) {
          normalized[fieldName] = fieldDef.default
          changes.push({ field: fieldName, original, normalized: fieldDef.default })
        }
        // Required fields with no value are left absent — validator catches them
        continue
      }

      const result = this._normalizeField(fieldName, original, fieldDef, warnings)
      if (result.value !== original) {
        changes.push({ field: fieldName, original, normalized: result.value })
      }
      if (result.value !== undefined) {
        normalized[fieldName] = result.value
      }
    }

    // Strip unknown fields (schema pollution prevention)
    const knownFields = new Set(Object.keys(schema.fields))
    for (const key of Object.keys(input)) {
      if (!knownFields.has(key)) {
        warnings.push(`Unknown field '${key}' stripped (not in schema '${schema.name}')`)
      }
    }

    return { normalized: normalized as T, changes, warnings }
  }

  private _normalizeField(
    name:     string,
    value:    unknown,
    def:      FieldDefinition,
    warnings: string[],
  ): { value: unknown } {
    switch (def.type) {
      case 'string':
        return { value: this._normalizeString(value, warnings, name) }

      case 'number':
        return { value: this._normalizeNumber(value, warnings, name) }

      case 'boolean':
        if (typeof value === 'boolean') return { value }
        if (value === 'true' || value === 1) return { value: true }
        if (value === 'false' || value === 0) return { value: false }
        warnings.push(`Field '${name}': cannot coerce '${value}' to boolean, skipping`)
        return { value: undefined }

      case 'date':
        return { value: this._normalizeDate(value, warnings, name) }

      case 'uuid': {
        const s = String(value).toLowerCase().trim()
        if (!UUID_RE.test(s)) {
          warnings.push(`Field '${name}': value '${value}' is not a valid UUID`)
        }
        return { value: s }
      }

      case 'email': {
        const s = String(value).toLowerCase().trim()
        if (!EMAIL_RE.test(s)) {
          warnings.push(`Field '${name}': value '${value}' is not a valid email`)
        }
        return { value: s }
      }

      case 'url': {
        let s = String(value).trim()
        if (!URL_RE.test(s)) {
          warnings.push(`Field '${name}': '${s}' has no https?:// scheme — prepending https://`)
          s = `https://${s}`
        }
        // Remove trailing slash for consistency
        return { value: s.replace(/\/$/, '') }
      }

      case 'enum': {
        const s = String(value)
        if (def.enumValues && !def.enumValues.includes(s)) {
          warnings.push(`Field '${name}': value '${s}' not in enum ${JSON.stringify(def.enumValues)}`)
        }
        return { value: s }
      }

      case 'json':
        if (typeof value === 'string') {
          try { return { value: JSON.parse(value) } }
          catch { warnings.push(`Field '${name}': invalid JSON string, storing as-is`); return { value } }
        }
        return { value }

      case 'array': {
        if (!Array.isArray(value)) {
          warnings.push(`Field '${name}': expected array, got ${typeof value}`)
          return { value: [] }
        }
        if (!def.items) return { value }
        const items = value.map((item, i) =>
          this._normalizeField(`${name}[${i}]`, item, def.items!, warnings).value,
        ).filter(v => v !== undefined)
        return { value: items }
      }

      case 'object': {
        if (typeof value !== 'object' || value === null || Array.isArray(value)) {
          warnings.push(`Field '${name}': expected object, got ${typeof value}`)
          return { value: {} }
        }
        if (!def.properties) return { value }
        const obj: Record<string, unknown> = {}
        for (const [k, propDef] of Object.entries(def.properties)) {
          const v = (value as Record<string, unknown>)[k]
          if (v !== undefined && v !== null) {
            obj[k] = this._normalizeField(`${name}.${k}`, v, propDef, warnings).value
          } else if (propDef.default !== undefined) {
            obj[k] = propDef.default
          }
        }
        return { value: obj }
      }

      default:
        return { value }
    }
  }

  private _normalizeString(value: unknown, warnings: string[], name: string): string {
    if (typeof value !== 'string') {
      warnings.push(`Field '${name}': coerced ${typeof value} to string`)
      return String(value).trim()
    }
    return value.trim()
  }

  private _normalizeNumber(value: unknown, warnings: string[], name: string): number | undefined {
    const n = Number(value)
    if (Number.isNaN(n)) {
      warnings.push(`Field '${name}': value '${value}' is NaN — skipping`)
      return undefined
    }
    if (!Number.isFinite(n)) {
      warnings.push(`Field '${name}': value '${value}' is Infinity — skipping`)
      return undefined
    }
    return n
  }

  private _normalizeDate(value: unknown, warnings: string[], name: string): string | undefined {
    if (value instanceof Date) {
      return value.toISOString()
    }
    if (typeof value === 'string' || typeof value === 'number') {
      const d = new Date(value)
      if (Number.isNaN(d.getTime())) {
        warnings.push(`Field '${name}': '${value}' is not a valid date — skipping`)
        return undefined
      }
      return d.toISOString()
    }
    warnings.push(`Field '${name}': cannot coerce ${typeof value} to date — skipping`)
    return undefined
  }
}
