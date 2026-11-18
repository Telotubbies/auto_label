"""A training worker reports where it is (dataset, weights, train) and the train loss, so the page is never blank."""
from labeldesk_worker.cli import StageClock, loss_row


def test_the_clock_records_stages_with_elapsed_seconds_and_a_running_note():
    ticks = iter([100.0, 103.2, 112.7])
    clock = StageClock(now=lambda: next(ticks))             # 100.0 is the start

    clock.mark("materialise")                               # 3.2 s in
    clock.mark("train", "running", "epoch 1")               # 12.7 s in

    assert clock.stages == {"materialise": {"status": "done", "t": 3.2},
                            "train": {"status": "running", "t": 12.7, "note": "epoch 1"}}


def test_a_later_mark_replaces_the_stage():
    ticks = iter([0.0, 1.0, 9.0])
    clock = StageClock(now=lambda: next(ticks))

    clock.mark("train", "running")
    clock.mark("train", "done")

    assert clock.stages["train"] == {"status": "done", "t": 9.0}


def test_stages_snapshot_is_a_copy():
    clock = StageClock(now=iter([0.0, 1.0]).__next__)
    clock.mark("queue")

    snap = clock.snapshot()
    snap["queue"]["status"] = "failed"

    assert clock.stages["queue"]["status"] == "done"


class _Trainer:
    tloss = [1.5, 2.5, 0.5]

    def label_loss_items(self, loss, prefix="train"):
        return {f"{prefix}/box_loss": float(loss[0]), f"{prefix}/seg_loss": float(loss[1]), f"{prefix}/cls_loss": float(loss[2])}


def test_the_loss_row_carries_train_and_val_losses_as_plain_floats():
    trainer = _Trainer()
    trainer.metrics = {"metrics/mAP50(B)": 0.5, "val/box_loss": 1.1}

    row = loss_row(trainer)

    assert row["train/box_loss"] == 1.5 and row["train/seg_loss"] == 2.5
    assert "metrics/mAP50(B)" not in row and "val/box_loss" not in row   # the caller already has the metrics


def test_the_loss_row_is_empty_when_the_trainer_has_no_loss_yet():
    class Bare:
        tloss = None

    assert loss_row(Bare()) == {}
