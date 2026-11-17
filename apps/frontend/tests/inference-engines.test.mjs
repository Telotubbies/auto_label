// T-1007: the Engines tab's pure rules — who may be ticked, what the footer promises, and the fact
// that the displayed command line is never sent back. node --test tests/inference-engines.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  argvText, changeHost, footerCopy, installRequest, rowStatusCopy, selectable, totals,
} from '../src/features/inference/engineRows.ts'

const row = (over = {}) => ({
  id: 'vllm', name: 'vLLM', version: '0.6.3', installed: false, disk_mb: 9626, runtimes: ['uv', 'docker'],
  compatibility: { status: 'ok', reasons: [], warnings: [] }, ...over,
})
const blocked = row({ id: 'tensorrt', name: 'TensorRT-LLM', disk_mb: 51200,
  compatibility: { status: 'blocked', reasons: ['Needs CUDA 12.4+; host reports 12.1'], warnings: [] } })
const warn = row({ id: 'llamacpp', name: 'llama.cpp', disk_mb: 512, installed: true,
  compatibility: { status: 'warn', reasons: [], warnings: ['CPU only: slower than a GPU'] } })
const fourth = row({ id: 'ollama', name: 'Ollama', disk_mb: 1024 })

test('test_blocked_rows_cannot_be_selected', () => {
  assert.equal(selectable(blocked), false)
  assert.equal(selectable(row()), true)
  assert.equal(selectable(warn), true)
})

test('test_totals_count_only_selected_and_sum_disk', () => {
  const rows = [row(), warn, fourth, blocked]
  const frozen = JSON.stringify(rows)
  const t = totals(rows, new Set(['vllm', 'ollama']))
  assert.equal(t.count, 2)
  assert.equal(t.diskMb, 9626 + 1024)
  // The host's free disk is not the totals' to spend: the rows come back untouched.
  assert.equal(JSON.stringify(rows), frozen)
  assert.deepEqual(Object.keys(t).sort(), ['count', 'diskMb'])
})

test('test_footer_says_why_the_action_is_disabled', () => {
  const none = { count: 0, diskMb: 0 }
  assert.equal(footerCopy(none, 812, true), 'Select an engine first.')
  assert.equal(footerCopy(none, 812, false), 'Select an engine first.')
  assert.equal(footerCopy({ count: 2, diskMb: 10650 }, 812, true, false), 'This host is offline.')
  assert.equal(footerCopy({ count: 2, diskMb: 10650 }, 812, false),
    'This host has not enabled installs (`LD_ALLOW_ENGINE_INSTALL=1`).')
  assert.equal(footerCopy({ count: 2, diskMb: 9626 }, 812, true), '2 engines · 9.4 GB to install · 812 GB free')
  assert.equal(footerCopy({ count: 1, diskMb: 512 }, 812, true), '1 engine · 0.5 GB to install · 812 GB free')
})

test('test_argv_is_shown_verbatim_and_never_joined_into_a_shell_line', () => {
  const step = { argv: [['uv', 'venv', '/engines/vllm-0.6.3'],
    ['uv', 'pip', 'install', '--python', '/engines/vllm-0.6.3/bin/python', 'vllm==0.6.3']] }
  const text = argvText(step)
  assert.equal(text, 'uv venv /engines/vllm-0.6.3\nuv pip install --python /engines/vllm-0.6.3/bin/python vllm==0.6.3')
  // Display only: the request carries ids, versions and enums — no argv, no joined line.
  const body = installRequest('gpu-1', [row(), warn], new Set(['vllm', 'llamacpp']),
    { vllm: 'docker' }, 'plan-1')
  assert.deepEqual(body, {
    host: 'gpu-1',
    engines: [{ id: 'vllm', version: '0.6.3', runtime: 'docker' },
      { id: 'llamacpp', version: '0.6.3', runtime: 'uv' }],
    plan_id: 'plan-1', confirm: true,
  })
  const sent = JSON.stringify(body)
  assert.equal(sent.includes('argv'), false)
  assert.equal(sent.includes(text), false)
  assert.equal(/[;|&]|\$\(/.test(sent), false)
  // The tab and the sheet may render argvText; neither may build a command from it.
  for (const f of ['EnginesTab.tsx', 'EngineSheet.tsx']) {
    const src = readFileSync(new URL(`../src/features/inference/${f}`, import.meta.url), 'utf8')
    assert.equal(/argv\s*\(|\.join\(['"] ['"]\)/.test(src), false, `${f} must not build a command line`)
  }
})

test('test_uninstall_is_only_offered_for_an_installed_row', () => {
  assert.equal(rowStatusCopy({ installed: false, version: '0.6.3' }).uninstall, false)
  assert.equal(rowStatusCopy({ installed: false, version: '0.6.3' }).label, 'Not installed')
  const done = rowStatusCopy({ installed: true, version: '0.6.3' })
  assert.equal(done.label, 'Installed 0.6.3')
  assert.equal(done.uninstall, true)
})

test('test_changing_host_clears_the_selection', () => {
  const used = { host: 'gpu-1', selected: new Set(['vllm', 'ollama']), notice: null }
  const next = changeHost(used, 'gpu-2')
  assert.equal(next.host, 'gpu-2')
  assert.equal(next.selected.size, 0)
  assert.equal(next.notice, 'Selection cleared: you changed host.')
  // Same host: keep both the ticks and the earlier notice.
  assert.equal(changeHost(used, 'gpu-1'), used)
  // Nothing ticked: a silent move, no notice to dismiss.
  assert.equal(changeHost({ host: 'gpu-1', selected: new Set(), notice: null }, 'gpu-2').notice, null)
})
