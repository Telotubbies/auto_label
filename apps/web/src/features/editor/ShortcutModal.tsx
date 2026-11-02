import { Modal } from '@/components/ui'

const SHORTCUTS: { keys: string; action: string }[] = [
  { keys: 'V', action: 'Pan / move canvas' },
  { keys: 'B', action: 'Bounding box tool' },
  { keys: 'P', action: 'Polygon tool' },
  { keys: 'O', action: 'Rotated box tool' },
  { keys: 'K', action: 'Keypoints tool' },
  { keys: 'S', action: 'Smart Polygon (SAM)' },
  { keys: '← / →', action: 'Previous / next image' },
  { keys: 'Delete / Backspace', action: 'Delete selected annotation' },
  { keys: 'Esc', action: 'Deselect / cancel drawing' },
  { keys: 'Enter', action: 'Finish polygon' },
  { keys: 'Double-click', action: 'Finish polygon' },
  { keys: 'Ctrl + Z', action: 'Undo' },
  { keys: 'Ctrl + Shift + Z', action: 'Redo' },
  { keys: 'Scroll', action: 'Zoom canvas' },
  { keys: 'Click point', action: 'Remove Smart Polygon point' },
  { keys: '?', action: 'Toggle this help' },
]

export function ShortcutModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Modal open={open} onClose={onClose} title="Keyboard Shortcuts" wide>
      <div className="grid grid-cols-1 gap-x-10 sm:grid-cols-2">
        {SHORTCUTS.map((s) => (
          <div key={s.action} className="flex items-center justify-between gap-4 border-b border-muted py-2.5 text-sm">
            <span className="text-muted-foreground">{s.action}</span>
            <kbd className="whitespace-nowrap rounded border bg-muted px-2 py-0.5 font-mono text-xs">{s.keys}</kbd>
          </div>
        ))}
      </div>
    </Modal>
  )
}
