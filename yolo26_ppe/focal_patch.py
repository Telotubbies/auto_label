"""Focal Loss monkey-patch for Ultralytics v8DetectionLoss / E2ELoss.

Replaces the standard BCE classification loss with Focal Loss (gamma=1.5)
to better handle class imbalance and hard examples in the PPE dataset.

The PPE dataset has class imbalance up to ~54:1 (helmet vs sandals/harness).
Focal Loss down-weights easy examples and focuses training on hard negatives,
complementing the cls_pw=0.5 class weighting and oversampling already in place.

Usage:
    import focal_patch  # MUST be imported before `from ultralytics import YOLO`

How it works:
    v8DetectionLoss.__init__ sets `self.bce = nn.BCEWithLogitsLoss(reduction="none")`.
    We replace it with FocalBCE (same reduction="none" semantics) so the rest of
    the loss pipeline (class_weights, sum / target_scores_sum) works unchanged.

    v8SegmentationLoss inherits from v8DetectionLoss, so segmentation models
    are also patched. E2ELoss uses v8DetectionLoss internally (one2many + one2one),
    so YOLO26 E2E training is also covered.

Sources:
    - Ultralytics FocalLoss: https://github.com/ultralytics/ultralytics/blob/main/ultralytics/utils/loss.py
    - Custom trainer guide: https://docs.ultralytics.com/guides/custom-trainer
    - Focal Loss paper: https://arxiv.org/abs/1708.02002
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

# Focal Loss hyperparameters
# gamma=1.5: moderate focusing (good default for imbalanced detection)
# alpha=0.25: balancing factor (standard from the Focal Loss paper)
FOCAL_GAMMA = 1.5
FOCAL_ALPHA = 0.25


class FocalBCE(nn.Module):
    """BCEWithLogitsLoss with focal modulation, reduction='none'.

    Mimics nn.BCEWithLogitsLoss(reduction='none') but applies the focal loss
    modulating factor (1 - p_t)^gamma to down-weight easy examples.

    Returns per-element loss (same shape as input) so v8DetectionLoss can
    still apply class_weights and do bce_loss.sum() / target_scores_sum.
    """

    def __init__(self, gamma: float = FOCAL_GAMMA, alpha: float = FOCAL_ALPHA):
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        """Compute focal-modulated BCE loss, per-element (reduction='none')."""
        loss = F.binary_cross_entropy_with_logits(pred, target, reduction="none")
        # p_t = probability of correct classification
        pred_prob = pred.sigmoid()
        p_t = target * pred_prob + (1 - target) * (1 - pred_prob)
        modulating_factor = (1.0 - p_t) ** self.gamma
        loss = loss * modulating_factor
        if self.alpha > 0:
            alpha_factor = target * self.alpha + (1 - target) * (1 - self.alpha)
            loss = loss * alpha_factor
        return loss  # per-element, NOT reduced


def _patch_v8_detection_loss():
    """Monkey-patch v8DetectionLoss to use FocalBCE instead of plain BCE."""
    from ultralytics.utils.loss import v8DetectionLoss

    _original_init = v8DetectionLoss.__init__

    def _patched_init(self, model, tal_topk=10, tal_topk2=None):
        _original_init(self, model, tal_topk=tal_topk, tal_topk2=tal_topk2)
        # Replace BCE with FocalBCE (same reduction='none' semantics)
        self.bce = FocalBCE(gamma=FOCAL_GAMMA, alpha=FOCAL_ALPHA)

    v8DetectionLoss.__init__ = _patched_init


# Apply patch on import
try:
    _patch_v8_detection_loss()
    FOCAL_PATCH_APPLIED = True
except Exception as _e:
    FOCAL_PATCH_APPLIED = False
    import warnings
    warnings.warn(f"focal_patch: failed to apply ({_e}), training will use standard BCE")
