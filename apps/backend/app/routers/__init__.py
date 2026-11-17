"""Router registry: every feature module's router, in the order the API has always mounted them.

``app.main`` calls ``include_routers``; a new feature adds its module to the imports and its router
to ``ROUTERS`` (or ``EXTRA_ROUTERS`` for a second router defined beside the first). Order matters:
an earlier router wins when two routes share a path shape, and the OpenAPI document lists them in
this order.
"""
from fastapi import FastAPI

from . import (admin, alerts, anomaly, audit, auth, batch_inference, connectors, dashboards, deployments, devapi,
               devapi_actions, devmail, event_search, flags, images, inference, insights, insights_lineage,
               insights_models, labeling, ocr, ops, ot, playground, privacy, projects, rbac, registry, remote, semantic,
               streams, training, versions, videos, webhooks, workflows, workspaces)

ROUTERS = (auth.router, workspaces.router, projects.router, images.router, videos.router, versions.router,
           devapi.router, devapi_actions.router, training.router, remote.router, registry.router, playground.router,
           connectors.router, webhooks.router, insights.router, insights_models.router,
           insights_lineage.router, dashboards.router, labeling.router, rbac.router, privacy.router,
           admin.router, audit.router, deployments.router, ops.router, flags.router, ot.router, ocr.router,
           streams.router, anomaly.router, alerts.router, workflows.router, batch_inference.router,
           semantic.router, event_search.router, inference.router)
# A second router in the same module: the GPU API, the ops websocket, the dev mail inbox.
EXTRA_ROUTERS = (registry.gpu_router, ops.ws_router, devmail.router)


def include_routers(app: FastAPI) -> None:
    for router in (*ROUTERS, *EXTRA_ROUTERS):
        app.include_router(router)
