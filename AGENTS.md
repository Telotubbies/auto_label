# AGENTS.md — Enterprise Engineering Rules

## Purpose

This file defines mandatory working rules for every AI agent and engineer operating in this repository.

The objective is to produce work that is:

- Evidence-based
- Technically accurate
- Secure by default
- Reliable in production
- Maintainable by other engineers
- Auditable and reproducible
- Suitable for enterprise use

These rules are project-independent. Do not add project architecture, local paths, credentials, passwords, model details, datasets, or environment-specific facts to this file.

---

## 1. Mandatory Research Before Action

### 1.1 Research-first rule

Before making any non-trivial technical decision, implementation, dependency change, configuration change, migration, optimization, or architectural recommendation:

1. Search the web for current and authoritative information.
2. Read the official documentation for the relevant technology.
3. Verify that the documentation applies to the version actually used by the repository.
4. Compare the documentation with the existing implementation and dependency files.
5. Record the sources that materially influenced the decision.
6. Do not implement based only on memory, assumptions, tutorials, or generated knowledge.

Research is required for:

- Framework and library APIs
- CLI flags and configuration formats
- Security controls
- Authentication and authorization
- Database behavior and migrations
- Cloud services and deployment platforms
- Model formats and inference runtimes
- Hardware, GPU, driver, CUDA, ROCm, and accelerator support
- Dependency compatibility
- Performance recommendations
- Licensing and redistribution conditions
- Public APIs and interoperability contracts
- Standards, protocols, and compliance requirements

For trivial repository-local work, such as correcting a typo or renaming a private variable without changing behavior, inspect the repository first. Web research is not a substitute for understanding local code.

### 1.2 Source hierarchy

Prefer sources in this order:

1. Official specifications and standards
2. Official vendor or framework documentation
3. Official source repositories, release notes, and migration guides
4. Peer-reviewed papers or recognized institutional publications
5. Maintainer-authored technical material
6. Reputable engineering references
7. Community discussions only as supporting evidence

Do not use the following as the sole authority:

- Search-result summaries
- Unverified blogs
- AI-generated articles
- Copied code without provenance
- Outdated tutorials
- Anonymous forum answers
- Social-media claims

### 1.3 Source verification

For every important source:

- Confirm the publisher or maintainer.
- Confirm the publication or update date when available.
- Confirm the applicable software version.
- Check whether the page is deprecated or superseded.
- Distinguish normative requirements from examples or opinions.
- Cross-check high-impact claims with at least one additional authoritative source.

Security-sensitive, production-critical, compliance-related, or irreversible decisions require at least two independent authoritative sources whenever practical.

### 1.4 Citation requirements

When reporting findings or proposing a technical decision:

- Include direct links to the authoritative sources consulted.
- State which claim or decision each source supports.
- Include relevant version and access date when the information may change.
- Clearly separate verified facts, repository observations, assumptions, and recommendations.
- Never invent citations, URLs, quotations, benchmarks, versions, or test results.

If no reliable source can be found, state that explicitly and treat the conclusion as uncertain.

---

## 2. Repository Investigation

Before changing code:

1. Read repository rules and contribution instructions.
2. Inspect the relevant source files and surrounding code.
3. Inspect dependency manifests and lockfiles.
4. Locate related tests, interfaces, call sites, and configuration.
5. Trace the execution path affected by the change.
6. Identify generated files and avoid editing them directly.
7. Check the current Git status to avoid overwriting unrelated work.
8. Preserve established conventions unless there is verified justification to change them.

Do not assume a package, tool, runtime, service, or command is available. Verify it from the repository or environment.

Do not silently replace existing architecture with a preferred pattern. First establish why the current pattern exists and whether compatibility constraints apply.

---

## 3. Planning and Decision Quality

For non-trivial work, create an explicit plan before implementation.

A good plan must include:

- Objective and user-visible outcome
- Scope and non-goals
- Current behavior
- Proposed behavior
- Affected components and interfaces
- Dependencies and authoritative references
- Security and privacy considerations
- Compatibility and migration impact
- Testing strategy
- Observability requirements
- Rollback strategy
- Known risks and open questions

### 3.1 Decision principles

Choose solutions that optimize for:

1. Correctness
2. Security
3. Reliability
4. Simplicity
5. Maintainability
6. Observability
7. Performance
8. Cost

Do not optimize performance before measuring it. Do not introduce abstractions without a demonstrated need. Prefer the smallest change that completely satisfies the requirement.

### 3.2 Uncertainty handling

Never hide uncertainty.

Use these labels where useful:

- **Verified** — confirmed by code, tests, runtime evidence, or authoritative documentation
- **Inferred** — strongly supported but not directly confirmed
- **Assumed** — required to proceed but not yet verified
- **Unknown** — insufficient evidence

Ask the user before proceeding when an unresolved decision could materially affect behavior, data, security, cost, compatibility, or delivery scope.

---

## 4. Enterprise Implementation Standards

### 4.1 Correctness

- Define expected behavior before implementation.
- Handle valid edge cases explicitly.
- Keep state transitions deterministic where possible.
- Validate inputs at trust boundaries.
- Preserve invariants and data integrity.
- Avoid silent fallback that changes semantics.
- Fail clearly when required dependencies or capabilities are unavailable.
- Do not report success unless the result was verified.

### 4.2 Maintainability

- Follow the repository’s established style and abstractions.
- Use clear and domain-appropriate names.
- Keep functions and modules focused.
- Minimize coupling and hidden side effects.
- Avoid duplicated business logic.
- Remove accidental complexity.
- Keep public interfaces stable unless a migration is planned.
- Document important decisions, constraints, and non-obvious trade-offs.

### 4.3 Compatibility

Before changing behavior:

- Identify public and internal consumers.
- Check backward compatibility.
- Check supported runtime and dependency versions.
- Preserve serialization and configuration compatibility where required.
- Provide migration steps for breaking changes.
- Use deprecation periods rather than abrupt removal when consumers may exist.

### 4.4 Dependencies

Before adding or upgrading a dependency:

1. Verify it is necessary.
2. Use the official package registry.
3. Review maintenance activity and release history.
4. Review license compatibility.
5. Check known security advisories.
6. Pin or constrain versions according to repository policy.
7. Update the lockfile using the package manager.
8. Run compatibility and regression tests.
9. Avoid newly published versions until they have had reasonable time for ecosystem review, unless an urgent security fix requires them.

Do not weaken package-manager security controls to make installation succeed.

---

## 5. Security and Privacy

Security is a release requirement, not an optional review step.

### 5.1 Required controls

- Treat all external input as untrusted.
- Validate type, format, size, range, and allowed values.
- Use parameterized queries and safe APIs.
- Apply least privilege.
- Use secure defaults.
- Keep authentication and authorization separate and explicit.
- Enforce authorization on the server side.
- Protect against injection, traversal, SSRF, unsafe deserialization, and command execution.
- Apply timeouts and resource limits to external operations.
- Avoid exposing internal errors, stack traces, or sensitive metadata.
- Keep secrets out of source code, logs, tests, examples, and documentation.
- Never commit credentials, tokens, private keys, passwords, or production data.

### 5.2 Secrets

- Use an approved secrets manager or environment injection.
- Never print secret values.
- Never pass secrets through command history when a safer mechanism exists.
- Redact secrets from diagnostics and reports.
- If a secret may have been exposed, stop and request rotation.

### 5.3 Data protection

- Minimize collected and retained data.
- Identify personal, confidential, regulated, and proprietary data.
- Avoid copying production data into development or tests.
- Use synthetic or anonymized fixtures where possible.
- Define retention and deletion behavior.
- Encrypt sensitive data in transit and at rest using approved mechanisms.
- Do not perform destructive data operations without explicit confirmation and a recovery plan.

### 5.4 Security verification

For security-relevant changes:

- Review against applicable OWASP guidance or authoritative standards.
- Add abuse-case and negative-path tests.
- Run dependency and static security checks when available.
- Confirm logs do not leak secrets or sensitive data.
- Document residual risks.

---

## 6. Testing and Verification

Every behavior change requires evidence that it works.

### 6.1 Test strategy

Use the lowest-cost test that provides strong confidence, then add higher-level coverage where risk requires it:

1. Unit tests
2. Component or module tests
3. Integration tests
4. Contract tests
5. End-to-end tests
6. Performance, resilience, and security tests

For bug fixes:

1. Reproduce the defect.
2. Add a failing regression test when practical.
3. Implement the root-cause fix.
4. Confirm the new test passes.
5. Run relevant regression tests.

### 6.2 Verification requirements

Before declaring completion:

- Run relevant tests.
- Run linting and formatting checks.
- Run type checking when configured.
- Run build or packaging checks.
- Validate configuration files.
- Review the final diff.
- Test error and cancellation paths.
- Confirm no unrelated files changed.
- Confirm no secrets or sensitive artifacts were added.
- Report exactly which checks passed, failed, or were not run.

Never claim a test passed if it was not executed successfully.

### 6.3 Test quality

Tests must:

- Verify observable behavior, not implementation trivia.
- Be deterministic.
- Avoid dependence on external systems unless explicitly integration tests.
- Use controlled fixtures.
- Cover boundary and failure cases.
- Avoid false positives caused by broad mocks or weak assertions.

---

## 7. Reliability and Resilience

Production-facing work must consider:

- Timeouts
- Retries with bounded exponential backoff and jitter
- Idempotency
- Concurrency and race conditions
- Partial failure
- Resource exhaustion
- Backpressure
- Graceful shutdown
- Recovery after interruption
- Data consistency
- Dependency outages

Do not retry operations that are unsafe to repeat unless idempotency is guaranteed.

Define failure behavior explicitly. Silent data loss, silent fallback, and unbounded retry loops are prohibited.

---

## 8. Observability

Production behavior must be diagnosable.

### 8.1 Logging

- Use structured logging where supported.
- Include useful context such as operation, component, correlation identifier, and outcome.
- Use appropriate log levels.
- Do not log secrets, credentials, personal data, or large payloads.
- Avoid noisy per-item logs in high-volume paths unless sampled or debug-only.

### 8.2 Metrics

Add metrics for critical paths where appropriate:

- Request or job count
- Success and failure count
- Latency distributions
- Throughput
- Queue depth
- Retry count
- Resource usage
- Domain-specific correctness or quality indicators

### 8.3 Tracing and diagnostics

For distributed operations:

- Preserve correlation identifiers.
- Propagate trace context.
- Record dependency latency and failures.
- Make failure ownership identifiable.

Observability must support detection, diagnosis, and recovery—not merely produce logs.

---

## 9. Performance and Scalability

- Establish a measurable baseline before optimization.
- Define the relevant workload and success metric.
- Profile before changing code.
- Measure after the change using the same methodology.
- Report hardware, software versions, dataset or workload, sample count, warm-up, and variability.
- Distinguish latency, throughput, memory, storage, and cost trade-offs.
- Avoid benchmark claims based on a single run.
- Do not sacrifice correctness or security for unverified performance gains.

Performance-sensitive changes require regression thresholds when practical.

---

## 10. API and Interface Design

Public interfaces must be deliberate and stable.

- Use explicit schemas and types.
- Validate requests and responses.
- Define error contracts.
- Use consistent naming and semantics.
- Support idempotency where clients may retry.
- Provide pagination and limits for collections.
- Avoid exposing internal implementation details.
- Version breaking changes.
- Document compatibility and lifecycle expectations.
- Add contract tests for consumers and providers.

API examples must be executable, safe, and consistent with the implemented version.

---

## 11. Configuration and Environments

- Keep configuration external to code where appropriate.
- Validate configuration at startup.
- Fail fast on missing required values.
- Use explicit environment-specific overrides.
- Never assume development defaults are safe for production.
- Do not commit secrets in configuration.
- Keep sample configuration non-sensitive and clearly labeled.
- Document units, allowed ranges, defaults, and operational impact.

Configuration changes that affect production behavior require tests and rollout notes.

---

## 12. Database and Data Migrations

Before a migration:

- Assess data volume and lock behavior.
- Plan backward and forward compatibility.
- Support mixed application versions during rollout when necessary.
- Back up or verify recovery capability.
- Test against production-like data volume.
- Define validation queries and rollback steps.

Prefer expand-and-contract migrations:

1. Add compatible schema.
2. Deploy code supporting old and new schema.
3. Backfill safely and observably.
4. Switch reads and writes.
5. Verify.
6. Remove old schema in a later release.

Never run destructive production migrations without explicit approval.

---

## 13. Git and Change Management

### 13.1 Working tree safety

- Inspect status and diff before editing.
- Preserve unrelated user changes.
- Do not discard, reset, or overwrite work without explicit authorization.
- Keep commits focused and reviewable.
- Do not commit generated or large artifacts unless required and approved.
- Use Git LFS or an artifact registry for approved large binaries.

### 13.2 Commit quality

Commit messages should explain why the change exists and its meaningful impact.

Do not add automated co-author identities, promotional footers, or generated-by attribution unless the user explicitly requests them.

### 13.3 Push and history

- Do not push unless explicitly requested.
- Do not force-push, rewrite history, delete branches, or modify tags without explicit confirmation.
- Verify the remote and branch before pushing.
- Confirm the remote accepted the commit; do not infer success from partial upload output.

### 13.4 Pull requests

A production-quality pull request must include:

- Problem statement
- Solution summary
- Key design decisions
- Security impact
- Compatibility or migration impact
- Test evidence
- Observability impact
- Rollout plan
- Rollback plan
- Known limitations
- References to authoritative sources

---

## 14. Documentation

Documentation must be accurate, current, and verifiable.

Update documentation when changing:

- Public behavior
- APIs and schemas
- Configuration
- Operational procedures
- Architecture
- Dependencies
- Deployment or rollback procedures
- Security assumptions

Documentation must distinguish:

- Required steps
- Optional steps
- Examples
- Environment-specific instructions
- Known limitations

Never include credentials, passwords, private URLs, personal data, or internal secrets in documentation.

Important architectural decisions should be recorded in an ADR containing context, decision, alternatives, consequences, and references.

---

## 15. Licensing and Provenance

Before copying, modifying, distributing, or packaging external material:

- Verify the applicable license from the authoritative source.
- Confirm redistribution and modification rights.
- Preserve required notices and attribution.
- Check compatibility with the repository’s distribution model.
- Record the source and version.
- Do not interpret password protection or repository privacy as a substitute for license compliance.

Do not claim ownership of third-party code, models, datasets, documentation, or media.

If licensing is unclear, stop distribution and ask for clarification.

---

## 16. Production Release Gate

A change is not enterprise-ready until all applicable gates pass.

### Required gates

- [ ] Requirements are explicit and accepted.
- [ ] Relevant official documentation was reviewed.
- [ ] Important claims have trustworthy citations.
- [ ] Architecture and compatibility impacts were assessed.
- [ ] Security and privacy impacts were reviewed.
- [ ] Tests cover expected behavior and failure paths.
- [ ] Lint, type checks, build, and tests pass.
- [ ] Performance impact was measured where relevant.
- [ ] Logs, metrics, and alerts are sufficient.
- [ ] Deployment and rollback procedures exist.
- [ ] Configuration and migration changes are documented.
- [ ] Dependencies and licenses were reviewed.
- [ ] No secrets or sensitive data are included.
- [ ] Final diff received a quality review.
- [ ] Residual risks and limitations are documented.

If a gate is not applicable, state why. If a gate cannot be completed, report it as a blocker or accepted risk rather than silently skipping it.

---

## 17. Completion Report Format

At the end of a task, report:

### Changes
- What changed
- Why it changed
- Which interfaces or behaviors are affected

### Evidence
- Tests executed and results
- Build, lint, and type-check results
- Runtime or benchmark evidence where relevant

### Sources
- Official documentation and authoritative references used
- Version applicability

### Risk
- Known limitations
- Security, compatibility, performance, or operational risks

### Operations
- Deployment steps
- Migration steps
- Rollback steps
- Required monitoring

Never state that work is complete when essential validation is still pending.

---

## 18. Prohibited Practices

Agents and engineers must not:

- Invent facts, metrics, test results, sources, or URLs.
- Implement unfamiliar APIs without checking official documentation.
- Hide errors or failed verification.
- Silently fall back to materially different behavior.
- Commit secrets, passwords, tokens, private keys, or production data.
- Disable security controls to make a build pass.
- Use destructive commands without explicit approval.
- Rewrite Git history without explicit approval.
- Introduce dependencies without verification.
- Copy code without checking license and provenance.
- Claim enterprise readiness without passing applicable quality gates.
- Treat a successful build as proof of functional correctness.
- Treat repository privacy, encryption, or password protection as license permission.
- Modify unrelated files merely to clean them up.

---

## 19. Default Agent Workflow

For every non-trivial task, use this workflow:

1. **Understand** — restate the requirement and identify ambiguity.
2. **Inspect** — examine repository rules, code, tests, configuration, and Git state.
3. **Research** — consult current authoritative online sources.
4. **Cite** — record the sources supporting important decisions.
5. **Plan** — define scope, risks, tests, rollout, and rollback.
6. **Implement** — make the smallest complete and idiomatic change.
7. **Verify** — run tests, checks, builds, and targeted runtime validation.
8. **Review** — inspect the diff for correctness, security, and maintainability.
9. **Document** — update affected interfaces, operations, and decisions.
10. **Report** — provide evidence, sources, limitations, and next steps.

When speed conflicts with correctness, security, or reliability, choose correctness, security, and reliability unless the user explicitly accepts the documented risk.
