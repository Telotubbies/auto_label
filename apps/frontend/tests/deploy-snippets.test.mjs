import test from 'node:test'
import assert from 'node:assert/strict'
import { INSTALL, deploySnippet } from '../src/features/project/deploySnippets.ts'

test('every kind/language pair embeds the endpoint', () => {
  for (const kind of ['images', 'video'])
    for (const lang of ['python', 'javascript', 'curl'])
      assert.match(deploySnippet(kind, lang, 'https://x/api/v1/models/m1/predict'), /\/models\/m1\/predict/)
})
test('video python loops frames; install lines cover all languages', () => {
  assert.match(deploySnippet('video', 'python', 'e'), /cv2\.VideoCapture/)
  assert.equal(Object.keys(INSTALL).length, 3)
})
