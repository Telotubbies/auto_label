"""ORM schema, one module per domain. Annotations live as JSON on the image row (one write per save,
trivially snapshotted into versions); everything else is relational.

Every name is re-exported here, so ``from app.models import Image`` keeps working and all tables are
registered on ``Base.metadata`` as soon as this package is imported.
"""
from . import alerts, insights, identity, project, streams, training
from .alerts import ALERT_KINDS, AlertChannel, AlertDelivery
from .common import (API_SCOPES, CONNECTOR_KINDS, DATA_REGIONS, DEPLOY_ALIASES, METRICS, PROJECT_ROLES,
                     PROJECT_TYPES, ROLES, SPLITS, STATUSES, WEBHOOK_EVENTS, WORKSPACE_ROLES, new_id, now)
from .identity import (ApiKey, Connector, CustomRole, EmailToken, Invite, LoginEvent, Member, ProjectMember,
                       RefreshToken, User, Webhook, WebhookDelivery, Workspace, WorkspaceFlag)
from .insights import (Audit, ConsensusAssignment, ConsensusJob, Dashboard, Honeypot, HoneypotAttempt,
                       LabelEvent, UsageEvent, Worker)
from .project import (Batch, Collection, CollectionItem, Comment, Folder, Image, ImageClass, LabelClass,
                      Project, SuspectFeedback, Version, Video, Workflow, WorkflowVersion, set_annotations)
from .streams import EventSearchFrame, OtDelivery, OtOutput, Stream, StreamEvent
from .training import (AnomalyStation, DeploymentAlias, DeploymentEvent, DriftRun, DriftSample, Job,
                      TrainedModel)

DOMAIN_MODULES = (identity, project, training, streams, insights, alerts)
