// The Deploy snippet must not hide its first line under the Copy button (T-522, UI-AUDIT A11).
// Source assertions only: the block is plain Tailwind markup with no runtime behaviour of its own.
//   node --test tests/deploy-snippet.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')
const deploy = read('../src/features/project/Deploy.tsx')

// The block that renders the cURL/Python/JS/URL snippet, from the `<pre>` that prints it to the
// closing tag of the button that copies it.
function snippetBlock() {
  const start = deploy.indexOf('{snippets[lang]}')
  assert.ok(start > 0, 'Deploy.tsx still renders a snippet from snippets[lang]')
  const preOpen = deploy.lastIndexOf('<pre', start)
  const end = deploy.indexOf('</div>', start)
  assert.ok(preOpen > 0 && end > start, 'the snippet <pre> sits inside the card div')
  return { pre: deploy.slice(preOpen, start), block: deploy.slice(preOpen, end) }
}

test('test_code_block_reserves_room_for_the_copy_button', () => {
  const { pre, block } = snippetBlock()
  assert.match(pre, /className="[^"]*\bpr-(?:12|14|16)\b/, 'the snippet <pre> reserves right padding for the Copy button')
  const button = block.slice(block.indexOf('<button'))
  assert.ok(button.startsWith('<button'), 'the snippet block still carries its Copy button')
  assert.match(button, /className="[^"]*\babsolute\b/, 'the Copy button is absolutely positioned, not on a code line')
  assert.match(button, /className="[^"]*\bright-2\b/, 'the Copy button keeps its right-2 corner')
  assert.match(button, /className="[^"]*\btop-2\b/, 'the Copy button keeps its top-2 corner')
})

test('test_one_snippet_source_per_language', () => {
  const tabs = deploy.match(/Tabs tabs=\{\[([\s\S]*?)\]\}/)
  assert.ok(tabs, 'Deploy.tsx still declares the language tabs')
  const langs = [...tabs[1].matchAll(/id:\s*'([^']+)'/g)].map((m) => m[1])
  assert.ok(langs.length > 0, 'the language tabs name their ids')

  const source = deploy.match(/const snippets: Record<string, string> = \{([\s\S]*?)\n {2}\}/)
  assert.ok(source, 'Deploy.tsx keeps one snippets map')
  const keys = [...source[1].matchAll(/^ {4}(\w+):/gm)].map((m) => m[1])

  assert.deepEqual(keys, langs, 'snippets has exactly one entry per language tab, in tab order')
  // One copy source: the button copies the active snippet, never a second hard-coded string.
  assert.equal([...deploy.matchAll(/navigator\.clipboard\.writeText\(([^)]*)\)/g)].length, 1,
    'only one Copy handler writes to the clipboard')
  assert.match(deploy, /navigator\.clipboard\.writeText\(snippets\[lang\]\)/, 'Copy copies the active snippet')
})
