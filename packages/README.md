# packages/

Code that other trees import. Never deployed on its own.

The rule is a deployability test, not a folder name: if a directory has its own
deploy or release target and sits at the end of the dependency graph, it is an
app and belongs in `apps/`. If other code imports it, it is a package and belongs
here. `packages/sdk` is the Python client and CLI published as `labeldesk-sdk`
and imported by `apps/backend/tests/test_sdk_cli.py`.
