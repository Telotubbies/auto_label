"""Batch inference over a project batch, video frames or a connector prefix (``batch_infer``)."""
from ..services import batch_inference


def run_batch_infer(job):
    from .. import worker as w
    return batch_inference.run(job, progress=lambda f: w._set(job.id, progress=round(f * 100, 1)))


HANDLERS = {"batch_infer": run_batch_infer}
