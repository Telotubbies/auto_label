// T-1106: type-level guard. tsc (npm run build) compiles this file; a Modal with neither a visible
// title nor an aria-label must not type-check. The two accepted shapes prove the other branch works.
import { Modal } from './ui'

export function TitledDialog() {
  return <Modal open onClose={() => {}} title="New project"><p>Body</p></Modal>
}

export function LabelledDialog() {
  return <Modal open onClose={() => {}} aria-label="New project"><p>Body</p></Modal>
}

export function UnnamedDialog() {
  return (
    // @ts-expect-error — T-1106: a Modal with no title must name itself with aria-label.
    <Modal open onClose={() => {}}><p>Body</p></Modal>
  )
}
