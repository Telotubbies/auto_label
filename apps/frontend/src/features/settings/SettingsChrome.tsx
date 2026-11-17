import { toast } from '@/components/ui'

/** Copy to the clipboard, or tell the reader how to do it by hand. */
export const copy = (s: string, message = 'Copied') => {
  navigator.clipboard.writeText(s).then(() => toast.ok(message)).catch(() => toast.err('Could not copy — select the text and copy it by hand.'))
}
