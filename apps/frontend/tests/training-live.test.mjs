// While a model trains, the Models page shows what the history already holds: the latest score per epoch,
// every loss the trainer reports (ultralytics names them `train/box_loss`, `val/seg_loss`), and the stage stepper.
import test from 'node:test'
import assert from 'node:assert/strict'
import { liveScores, lossSeries, trainingEta } from '../src/features/project/trainingLive.ts'

const row = (epoch, extra = {}) => ({ epoch, 'metrics/mAP50(M)': 0.1 * epoch, 'metrics/mAP50-95(M)': 0.05 * epoch,
  'metrics/precision(M)': 0.5, 'metrics/recall(M)': 0.4, 'metrics/mAP50(B)': 0.9, ...extra })

test('the live scores come from the latest epoch, using the mask columns for a segmentation model', () => {
  const s = liveScores('segment', [row(1), row(2), row(3)])

  assert.equal(s.epoch, 3)
  assert.equal(s.map50, 0.30000000000000004)
  assert.equal(s.precision, 0.5)
  assert.equal(s.recall, 0.4)
})

test('a detection model reads the box columns', () => {
  const s = liveScores('detect', [row(1, { 'metrics/mAP50(B)': 0.7, 'metrics/mAP50-95(B)': 0.4 })])

  assert.equal(s.map50, 0.7)
  assert.equal(s.map5095, 0.4)
})

test('a classifier reads top-1 and top-5', () => {
  const s = liveScores('classify', [{ epoch: 1, 'metrics/accuracy_top1': 0.8, 'metrics/accuracy_top5': 0.99 }])

  assert.deepEqual([s.top1, s.top5], [0.8, 0.99])
})

test('no history yet means no live scores', () => {
  assert.equal(liveScores('segment', []), null)
})

test('loss series finds every ultralytics loss, grouped by train and val, and skips the other columns', () => {
  const h = [{ epoch: 1, 'train/box_loss': 1.5, 'val/box_loss': 1.6, 'val/seg_loss': 2, 'metrics/mAP50(B)': 0.1 },
    { epoch: 2, 'train/box_loss': 1.2, 'val/box_loss': 1.4, 'val/seg_loss': 1.7 }]

  const l = lossSeries(h)

  assert.deepEqual(l.keys.map((k) => k.key), ['train/box_loss', 'val/box_loss', 'val/seg_loss'])
  assert.equal(l.keys[0].label, 'train box')
  assert.equal(l.keys[2].label, 'val seg')
})

test('loss series also takes the generic `val/loss` of other families', () => {
  assert.deepEqual(lossSeries([{ epoch: 1, 'val/loss': 0.4 }]).keys.map((k) => k.key), ['val/loss'])
})

test('a final-evaluation row without losses does not hide the losses of the epochs', () => {
  const l = lossSeries([{ epoch: 1, 'val/box_loss': 1 }, { epoch: 2, 'metrics/mAP50(B)': 0.5 }])

  assert.equal(l.keys.length, 1)
})

test('no loss column means an empty series, not a crash', () => {
  assert.deepEqual(lossSeries([{ epoch: 1, 'metrics/mAP50(B)': 0.5 }]).keys, [])
})

test('the ETA is the average epoch time times the epochs left', () => {
  assert.equal(trainingEta({ started: 1000, now: 1100, done: 10, total: 100 }), 900)
  assert.equal(trainingEta({ started: 1000, now: 1100, done: 0, total: 100 }), null)
  assert.equal(trainingEta({ started: null, now: 1100, done: 5, total: 100 }), null)
})
