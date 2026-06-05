// core/state.ts — SessionState, FSM, Memento, Command
import { randomUUID } from 'node:crypto'
import {
  AgentFSMState,
  Command,
  FSMTrace,
  FSMViolationError,
  ISessionState,
  Memento,
  StateObserver,
  Unsubscribe,
} from './protocols.js'

// Valid FSM transitions per CLAUDE.md §12
const VALID_TRANSITIONS = new Map<AgentFSMState, Set<AgentFSMState>>([
  ['IDLE',       new Set<AgentFSMState>(['GATHERING'])],
  ['GATHERING',  new Set<AgentFSMState>(['MODELING', 'AWAITING', 'FAILURE'])],
  ['AWAITING',   new Set<AgentFSMState>(['MODELING', 'FAILURE'])],
  ['MODELING',   new Set<AgentFSMState>(['SOLVING', 'FAILURE'])],
  ['SOLVING',    new Set<AgentFSMState>(['VALIDATING', 'FAILURE'])],
  ['VALIDATING', new Set<AgentFSMState>(['DELIVERING', 'FAILURE'])],
  ['DELIVERING', new Set<AgentFSMState>(['IDLE'])],
  ['FAILURE',    new Set<AgentFSMState>(['DELIVERING'])],
  ['DEGRADED',   new Set<AgentFSMState>(['IDLE', 'FAILURE'])],
])

export class SessionState implements ISessionState {
  private _fsm: AgentFSMState = 'IDLE'
  private _turn = 0
  private _contextName = 'NullContext'
  private _scratch: Record<string, unknown> = {}
  private _trace: FSMTrace = []
  private readonly _mementos = new Map<string, Memento>()
  private readonly _commandLog: Command[] = []
  private readonly _observers = new Set<StateObserver>()
  private readonly _maxMementos: number

  constructor(maxMementos = 100) {
    this._maxMementos = maxMementos
  }

  get fsm(): AgentFSMState { return this._fsm }
  get turn(): number { return this._turn }
  get contextName(): string { return this._contextName }
  get trace(): FSMTrace { return [...this._trace] }
  get history(): Command[] { return [...this._commandLog] }

  transition(to: AgentFSMState): void {
    const allowed = VALID_TRANSITIONS.get(this._fsm)
    if (!allowed?.has(to)) {
      throw new FSMViolationError(this._fsm, to, this.trace)
    }
    this._fsm = to
    this._trace.push({ state: to, timestamp: Date.now() })
    this._notifyObservers()
  }

  setContext(name: string): void {
    this._contextName = name
  }

  snapshot(): Memento {
    if (this._mementos.size >= this._maxMementos) {
      // Evict oldest (LRU)
      const oldestKey = this._mementos.keys().next().value
      if (oldestKey !== undefined) {
        this._mementos.delete(oldestKey)
      }
    }
    const memento: Memento = {
      id: randomUUID(),
      fsm: this._fsm,
      turn: this._turn,
      contextName: this._contextName,
      scratch: { ...this._scratch },
      timestamp: Date.now(),
    }
    this._mementos.set(memento.id, memento)
    return memento
  }

  restore(id: string): void {
    const memento = this._mementos.get(id)
    if (!memento) throw new Error(`Memento not found: ${id}`)
    this._fsm = memento.fsm
    this._contextName = memento.contextName
    this._scratch = { ...memento.scratch }
    this._trace = []
    this._notifyObservers()
  }

  commit(cmd: Command): void {
    this._commandLog.push(cmd)
    this._turn += 1
    this._notifyObservers()
  }

  subscribe(obs: StateObserver): Unsubscribe {
    this._observers.add(obs)
    return () => { this._observers.delete(obs) }
  }

  async flush(): Promise<void> {
    // Base: no-op. Override for persistence.
  }

  reset(): void {
    this._fsm = 'IDLE'
    this._trace = []
    this._scratch = {}
    this._notifyObservers()
  }

  private _notifyObservers(): void {
    for (const obs of this._observers) {
      obs(this._fsm)
    }
  }
}
