/** Editable editor shortcuts: defaults, validation, per-user persistence and key matching.
 *
 * Enter, Esc, `?` and the arrow keys stay fixed — they are conventions users rely on and a remap
 * could strand the keyboard-only annotation flow. Everything else is stored per user.
 */
export const SHORTCUT_STORAGE_KEY = 'ld:editor-shortcuts'
export const SHORTCUT_VERSION = 1

export type ShortcutId = 'pan' | 'bbox' | 'polygon' | 'obb' | 'keypoints' | 'smart' | 'delete' | 'save'
export type ShortcutMap = Record<ShortcutId, string>

export interface KeyEventLike {
  key: string
  ctrlKey?: boolean
  metaKey?: boolean
  shiftKey?: boolean
  altKey?: boolean
}

export interface ShortcutAction {
  id: ShortcutId
  label: string
  key: string
}

export const SHORTCUT_ACTIONS: ShortcutAction[] = [
  { id: 'pan', label: 'Pan / move canvas', key: 'v' },
  { id: 'bbox', label: 'Bounding box tool', key: 'b' },
  { id: 'polygon', label: 'Polygon tool', key: 'p' },
  { id: 'obb', label: 'Rotated box tool', key: 'o' },
  { id: 'keypoints', label: 'Keypoints tool', key: 'k' },
  { id: 'smart', label: 'Smart Polygon (SAM)', key: 's' },
  { id: 'delete', label: 'Delete selected annotation', key: 'delete' },
  { id: 'save', label: 'Save annotations', key: 'ctrl+s' },
]

export const DEFAULT_SHORTCUTS = Object.fromEntries(
  SHORTCUT_ACTIONS.map((a) => [a.id, a.key]),
) as ShortcutMap

/** Shown in the cheat sheet without a remap control. */
export const FIXED_SHORTCUTS: { keys: string; label: string }[] = [
  { keys: '← / →', label: 'Previous / next image' },
  { keys: 'Enter', label: 'Finish polygon / commit Smart Polygon' },
  { keys: 'Esc', label: 'Deselect / cancel drawing' },
  { keys: 'Ctrl + Z', label: 'Undo' },
  { keys: 'Ctrl + Shift + Z', label: 'Redo' },
  { keys: '?', label: 'Toggle this help' },
  { keys: '1–9', label: 'Pick a class (visible rows when filtering)' },
  { keys: '/', label: 'Focus the class search' },
]

export const MOUSE_SHORTCUTS: { keys: string; label: string }[] = [
  { keys: 'Double-click', label: 'Finish polygon' },
  { keys: 'Scroll', label: 'Zoom canvas' },
  { keys: 'Click point', label: 'Remove Smart Polygon point' },
]

const PROTECTED = new Set([
  '?', 'enter', 'escape', 'tab', 'arrowleft', 'arrowright', 'arrowup', 'arrowdown',
  'shift', 'control', 'meta', 'alt', 'capslock',
])
const NAMED_KEYS = new Set(['delete', 'backspace', 'space', 'home', 'end'])
/** Owned by the editor itself (focuses the class search), so it can never be an action key. */
const RESERVED_KEYS = new Set(['/'])
const PRINTABLE = /^[\x21-\x7e]$/

function normKey(key: string): string {
  return key.length === 1 ? key.toLowerCase() : key.toLowerCase()
}

function hasBindingShape(binding: string): boolean {
  if (binding.startsWith('ctrl+')) return /^ctrl\+[a-z0-9]$/.test(binding)
  return NAMED_KEYS.has(binding) || PRINTABLE.test(binding)
}

/**
 * The one accepted set, shared by capture, validation, save and load: a printable single key
 * (lowercased), `ctrl+<letter|digit>`, or a named key — never a protected/shadowed key.
 */
export function isAcceptedBinding(binding: string): boolean {
  if (!binding || !hasBindingShape(binding)) return false
  if (PROTECTED.has(binding) || RESERVED_KEYS.has(binding) || binding === 'ctrl+z') return false
  return !/^[1-9]$/.test(binding)
}

/** One keypress -> a stored binding, or null when the key must stay fixed / cannot be bound. */
export function captureBinding(e: KeyEventLike): string | null {
  const key = normKey(e.key ?? '')
  if (!key || PROTECTED.has(key) || e.altKey) return null
  if (key === ' ') return 'space'
  if (e.ctrlKey || e.metaKey) {
    if (!/^[a-z0-9]$/.test(key) || key === 'z') return null
    return `ctrl+${key}`
  }
  if (key.length === 1 || NAMED_KEYS.has(key)) return key
  return null
}

export function resolveShortcut(e: KeyEventLike, map: ShortcutMap): ShortcutId | null {
  const binding = captureBinding(e)
  if (!binding) return null
  return (Object.keys(map) as ShortcutId[]).find((id) => map[id] === binding) ?? null
}

export function keyLabel(binding: string): string {
  if (binding.startsWith('ctrl+')) return `Ctrl + ${binding.slice(5).toUpperCase()}`
  if (binding === 'delete' || binding === 'backspace' || binding === 'space') {
    return binding[0].toUpperCase() + binding.slice(1)
  }
  return binding.toUpperCase()
}

function labelOf(id: ShortcutId): string {
  return SHORTCUT_ACTIONS.find((a) => a.id === id)?.label ?? id
}

/** Ids that share a binding; an empty array means the map can be saved. */
export function duplicateIds(map: ShortcutMap): ShortcutId[] {
  const byBinding = new Map<string, ShortcutId[]>()
  for (const id of Object.keys(map) as ShortcutId[]) {
    const list = byBinding.get(map[id]) ?? []
    list.push(id)
    byBinding.set(map[id], list)
  }
  return [...byBinding.values()].filter((ids) => ids.length > 1).flat()
}

/** -> null when the binding is acceptable, else the message the panel shows. */
export function validateBinding(binding: string, map: ShortcutMap, id: ShortcutId): string | null {
  if (/^[1-9]$/.test(binding)) return '1–9 are reserved for class hotkeys'
  if (RESERVED_KEYS.has(binding)) return '“/” focuses the class search — pick another key'
  if (!isAcceptedBinding(binding)) return 'Enter, Esc, ? and the arrow keys stay fixed'
  const owner = (Object.keys(map) as ShortcutId[]).find((other) => other !== id && map[other] === binding)
  if (owner) return `${keyLabel(binding)} is already used by ${labelOf(owner)}`
  return null
}

export interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

export function loadShortcuts(storage: StorageLike | null): ShortcutMap {
  const map: ShortcutMap = { ...DEFAULT_SHORTCUTS }
  if (!storage) return map
  let raw: string | null = null
  try {
    raw = storage.getItem(SHORTCUT_STORAGE_KEY)
  } catch {
    return map
  }
  if (!raw) return map
  try {
    const parsed = JSON.parse(raw)
    const keys = parsed?.keys ?? parsed
    if (!keys || typeof keys !== 'object') return map
    for (const id of Object.keys(DEFAULT_SHORTCUTS) as ShortcutId[]) {
      const value = keys[id]
      if (typeof value === 'string' && isAcceptedBinding(value)) map[id] = value
    }
    for (const id of duplicateIds(map)) map[id] = DEFAULT_SHORTCUTS[id]   // never load a conflict
  } catch {
    return { ...DEFAULT_SHORTCUTS }
  }
  return map
}

export function saveShortcuts(map: ShortcutMap, storage: StorageLike | null): boolean {
  if (!storage || duplicateIds(map).length) return false
  if (!Object.values(map).every(isAcceptedBinding)) return false   // never store what the loader would drop
  try {
    storage.setItem(SHORTCUT_STORAGE_KEY, JSON.stringify({ v: SHORTCUT_VERSION, keys: map }))
    return true
  } catch {
    return false
  }
}
