// testing/fixtures.ts — Common Query / Solution / Artifact test doubles
import {
  Artifact,
  Query,
  Solution,
} from '../core/protocols.js'

export function makeQuery(overrides: Partial<Query> = {}): Query {
  return {
    text: 'test query',
    format: 'text',
    metadata: {},
    ...overrides,
  }
}

export function makeSolution(overrides: Partial<Solution> = {}): Solution {
  return {
    content: 'test solution content',
    format: 'text',
    sources: [],
    ...overrides,
  }
}

export function makeArtifact(overrides: Partial<Artifact> = {}): Artifact {
  return {
    content: 'test artifact content',
    format: 'text',
    provenance: [],
    ...overrides,
  }
}
