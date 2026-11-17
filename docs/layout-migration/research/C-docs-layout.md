STATUS: DONE

TL;DR

- Diátaxis classifies documentation by *user need* (tutorials, how-to, reference, explanation), not by directory; it warns against creating empty four-way folders and its own repo keeps a flat `source/` tree, not `docs/docs/`.
- Decision records belong in a numbered, append-only log (`docs/adr/NNNN-title.md`), never rewritten: supersede by adding a new record and flipping the old one's status.
- Design docs and RFCs are pre-implementation artefacts with their own lifecycle and number/date scheme; Rust, Kubernetes and Python all keep them in a dedicated tree or repository, separate from user docs.
- Research/spike notes are working material: commit only durable investigation reports, keep them out of the published docs build, and never mix them with user-facing reference.
- Generated output (API reference HTML, site builds, most exported binaries) is a build artefact and belongs in `.gitignore`; the OpenAPI document and diagram sources are the committed truth.

---

## 1. Diátaxis: four modes, and what it does not prescribe

**The four modes.** Diátaxis "identifies four distinct needs, and four corresponding forms of documentation - *tutorials*, *how-to guides*, *technical reference* and *explanation*" and proposes that documentation be organised around those needs (https://diataxis.fr/). The distinctions are summarised in the map:

| | Tutorials | How-to guides | Reference | Explanation |
|---|---|---|---|---|
| what they do | introduce, educate, lead | guide | state, describe, inform | explain, clarify, discuss |
| answers | "Can you teach me to…?" | "How do I…?" | "What is…?" | "Why…?" |
| oriented to | learning | goals | information | understanding |
| form | a lesson | a series of steps | dry description | discursive explanation |

(https://diataxis.fr/map/)

Each mode is defined on its own page: a tutorial is "a practical activity … learning-oriented" (https://diataxis.fr/tutorials/); a how-to guide is "directions that guide the reader through a problem or towards a result … goal-oriented" (https://diataxis.fr/how-to-guides/); reference is "technical descriptions of the machinery … information-oriented" and "should be austere" (https://diataxis.fr/reference/); explanation is "a discursive treatment of a subject, that permits *reflection* … understanding-oriented" whose job includes explaining "why things are so - design decisions, historical reasons, technical constraints" (https://diataxis.fr/explanation/).

**What it says about directories.** Nothing mandatory. Diátaxis is explicit that the structure is "not intended to be a **plan**, something you must complete" and that you should *not* "create empty structures for tutorials/howto guides/reference/explanation with nothing in them. Don't do that. It's horrible." Structure is supposed to "change … from the inside" as content is fixed (https://diataxis.fr/how-to-use-diataxis/). The four-way directory split (`tutorials/`, `how-to/`, `reference/`, `explanation/`) is therefore a **project convention**, not a rule in the framework; it is the natural landing point once the content genuinely sorts into the four needs.

**The `docs/docs/...` claim does not hold up.** The Diátaxis source repository (1.3k stars) does not use `docs/docs/`; it is a Sphinx project with a flat `source/` directory containing one file per page — `source/index.rst`, `source/tutorials.rst`, `source/how-to-guides.rst`, `source/reference.rst`, `source/explanation.rst`, `source/map.rst`, and so on (https://github.com/evildmp/diataxis-documentation-framework/tree/main/source). A nested `docs/docs/` adds a path segment that no tool requires and makes every relative link ambiguous; treat it as an accident of one project's Sphinx config, not a convention to copy.

**Where "research notes" and "design documents" fit.** They do not fit. Diátaxis scopes itself to "the needs of documentation users" and names exactly four forms (https://diataxis.fr/); there is no mode for a working note, a spike, or a decision record. Design *rationale* has a home — explanation — but only in its published, user-facing form ("explain *why* things are so - design decisions, historical reasons" — https://diataxis.fr/explanation/). The raw decision record, the RFC and the investigation report are provider-side artefacts and belong in their own trees (sections 2–4). Explanation is also warned to stay "closely bounded", because it "tends to absorb other things" (https://diataxis.fr/explanation/); that is the same failure as filing an ADR under `explanation/`.

---

## 2. Architecture Decision Records

**Original proposal.** Michael Nygard's 2011 post defines an ADR as "a short text file in a format similar to an Alexandrian pattern", one decision per record, stored "in the project repository under `doc/arch/adr-NNN.md`", "numbered sequentially and monotonically. Numbers will not be reused." A reversed decision is **kept**, "but mark it as superseded. (It's still relevant to know that it *was* the decision, but is *no longer* the decision.)" The format is Title / Context / Decision / Status / Consequences, "one or two pages long", written "as if it is a conversation with a future developer" (https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions). Statuses named there: `proposed`, `accepted`, and `deprecated` or `superseded` (with a reference to the replacement). The article is also formatted as an ADR itself, which is a good hint that the format is prose, not a form.

**Tooling convention.** `adr-tools` stores ADRs "in a subdirectory of your project as Markdown files. The default directory is `doc/adr`, but you can specify the directory when you initialise the ADR log". `adr init <dir>` creates the directory plus "the first ADR, which records that you are using ADRs"; `adr new -s 9 "..."` creates a superseding record and "changes the status of ADR 9 to indicate that it is superceded by the new ADR" (https://github.com/npryce/adr-tools). What `adr init` documents creating is the directory plus that first record; the index README is a team convention layered on top, and its absence from the tool is why it has to be written by hand.

**Current guidance and the `docs/adr/` variant.** adr.github.io frames the collection as a *decision log*: "An Architectural Decision Record (ADR) captures a single AD and its rationale … The collection of ADRs created and maintained in a project constitute its *decision log*", and notes the practice extends to "design and other decisions ('any decision record')" (https://adr.github.io/). MADR, the most-used Markdown template, says: "Copy it into `docs/decisions`. For each ADR, copy the template to `nnnn-title.md`" (https://github.com/adr/madr) — i.e. `docs/decisions/NNNN-title.md` is as current as `doc/adr/NNNN-title.md`; the important invariant is the monotonic number and the append-only log, not the parent directory name. MADR's own site adds Jekyll front matter (`parent: Decisions`, `nav_order: 100`) to its template so the decisions render under a parent page, which is the index in practice (https://github.com/adr/madr).

**Index + supersession practice.** AWS Prescriptive Guidance (vendor documentation, treat as secondary) recommends: "Store ADRs in a central location … and reference them on the main page of your project documentation"; "Preserve ADR history … change the status of the old ADR to **Superseded**, note their changes in the change history of the new ADR, and keep the old ADR in the decision log" (https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/best-practices.html). That is the citation for both the README index and the never-delete rule.

---

## 3. Design docs and RFCs, and how they are dated

**Google's design-doc practice.** Design docs are "relatively informal documents that the primary author or authors … create before they embark on the coding project", documenting "the high level implementation strategy and key design decisions with emphasis on the trade-offs". Standard sections: context and scope, goals and non-goals, the design, alternatives considered, cross-cutting concerns; 10–20 pages for a large project, or a 1–3 page "mini design doc". Crucially for layout: most are written in Google Docs, not in the repo, and "if the designed system hasn't shipped yet, then definitely update the doc", while later changes "are often isolated into new documents … Links to such amendments from the original doc can be immensely helpful" (https://www.industrialempathy.com/posts/design-docs-at-google/ — practitioner blog by a Google engineer, secondary but detailed).

**Rust RFCs: numbered by PR, dated in the header, immutable once accepted.** "Copy `0000-template.md` to `text/0000-my-feature.md` … This is going to be the PR number and we'll rename the file accordingly if the RFC is accepted." The template's header block is:

```
- Feature Name: …
- Start Date: (fill me in with today's date, YYYY-MM-DD)
- RFC PR: [rust-lang/rfcs#0000](…)
- Rust Issue: [rust-lang/rust#0000](…)
```

(https://github.com/rust-lang/rfcs and https://raw.githubusercontent.com/rust-lang/rfcs/master/0000-template.md). Amendments are constrained: "once accepted, RFCs should not be substantially changed … More substantial changes should be new RFCs, with a note added to the original RFC" (https://github.com/rust-lang/rfcs). The tree is a dedicated top-level `text/` directory — the RFCs are not part of the rustc/user documentation tree (https://github.com/rust-lang/rfcs).

**Kubernetes KEPs: numbered by tracking issue, per-SIG directory, explicit metadata.** "Copy this template into the owning SIG's directory and name it `NNNN-short-descriptive-title`, where `NNNN` is the issue number (with no leading-zero padding)" (https://raw.githubusercontent.com/kubernetes/enhancements/master/keps/NNNN-kep-template/README.md). Each KEP is a directory with `README.md` plus `kep.yaml`, whose fields include `kep-number`, `status`, `creation-date`, `see-also`, `replaces`, `stage`, `latest-milestone` (https://raw.githubusercontent.com/kubernetes/enhancements/master/keps/NNNN-kep-template/kep.yaml). Lifecycle rule: "One KEP corresponds to one 'feature' … Once a feature has become 'implemented', major changes should get new KEPs" (KEP template README). The KEPs are explicitly "inspired by IETF RFCs, Python PEPs and Rust RFCs" (https://github.com/kubernetes/enhancements/tree/master/keps).

**Python PEPs: the canonical "design document" genre.** "A PEP is a design document providing information to the Python community, or describing a new feature … Because the PEPs are maintained as text files in a versioned repository, their revision history is the historical record of the feature proposal." Files are `pep-NNNN.rst`; the required header preamble carries `Created: <dd-mmm-yyyy>`, `Post-History`, `Replaces`, `Superseded-By`, `Status` (Draft | Active | Accepted | Provisional | Deferred | Rejected | Withdrawn | Final | Superseded). "In general, PEPs are no longer substantially modified after they have reached the Accepted, Final, Rejected or Superseded state" (https://peps.python.org/pep-0001/).

**Where they live relative to `docs/`.** Both large-scale examples put proposals in their *own* tree, and Kubernetes in its own repository (`kubernetes/enhancements`), not inside the product docs. Google's account likewise keeps design docs off the published doc site. If a design/RFC tree must live in the product repo, the safe shape is a dedicated subtree (`docs/rfc/` or `docs/design/`) that the docs build **excludes**; MkDocs provides `exclude_docs` and `draft_docs` patterns exactly for files "under `docs_dir`" that must not be "picked up into the built site" (https://www.mkdocs.org/user-guide/configuration/). That keeps the artefact versioned and reviewable without publishing half-finished thinking.

**Dating/versioning convention.** Two schemes dominate, and they answer different questions: a **monotonic number** (ADR, RFC, PEP, KEP) gives a stable permanent identifier that is never reused; a **date** records when the work started. All three proposal processes carry both — the number in the filename, the date in the metadata (`Start Date` for Rust, `creation-date` for KEP, `Created` for PEP). For date prefixes use ISO 8601 `YYYY-MM-DD` so that filenames sort chronologically; that profile is standardised as a W3C note (https://www.w3.org/TR/NOTE-datetime). W3C's older URI guidance makes the same point from the other direction: "The creation date of the document … is one thing which will not change", so a date is the one safe thing to put in a persistent name (https://www.w3.org/Provider/Style/URI).

---

## 4. Research notes, spike notes and investigation reports

**They are provider-side, not user-facing.** Google's engineering-documentation chapter draws the line explicitly: "documents intended for one [customer vs provider] should be kept apart … Implementation details are important to a team member for maintenance purposes; end users should not need to read such information", and design reasoning "belongs more appropriately in specific documents (design documents)" (https://abseil.io/resources/swe-book/html/ch10.html). A spike report is implementation detail by definition.

**Where.** Either a dedicated top-level `research/` or `notes/` tree, or `docs/research/` excluded from the published site. There is no cross-project standard name; what the credible sources agree on is *separation*: The Turing Way's research-compendium guidance requires that "Data, methods, and output should be clearly separated" and that files be "organized in a conventional folder structure", with human-generated material (code, paper, documentation) distinguished from project-generated output (clean data, figures) (https://the-turing-way.netlify.app/reproducible-research/compendia). Rust's RFCs and Kubernetes' KEPs are the committed-investigation precedent: proposals are versioned, numbered, and kept outside the user docs.

**Should they be committed at all?** Commit the ones that are *durable evidence*: a dated report that states the question, the method, the raw numbers or links to them, the conclusion, and what was decided as a result. Do not commit scratch notes, terminal dumps, screenshots of failures, model weights, datasets, or anything reproducible in one command — the Turing Way distinction above, plus GitHub's hard limits (files over 50 MiB warn, over 100 MiB are blocked, repositories should stay under 1 GB: https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github). A practical test: if a future maintainer would have to *trust* the note rather than re-run it, commit it; if they could regenerate it, ignore it.

**Keep them out of the built site.** Exclusion is a one-line config concern, not a directory debate: MkDocs `exclude_docs` / `draft_docs` (https://www.mkdocs.org/user-guide/configuration/). If a note later becomes genuinely explanatory for users, rewrite it as explanation and link it into the nav — do not promote the raw note.

---

## 5. Generated and artefact documentation

**API reference: generate, don't hand-maintain.** Diátaxis says "Some reference material (such as API documentation) can be generated automatically by the software it describes, which is a powerful way of ensuring that it remains faithfully accurate to the code", while warning that "too many software developers think that auto-generated reference material is all the documentation required" (https://diataxis.fr/reference/). Google's chapter is blunter: "reference documentation should be single-sourced as much as possible" (https://abseil.io/resources/swe-book/html/ch10.html). So: **one** machine-readable contract committed, the reference rendered from it at build time, plus hand-written explanation and how-tos around it.

**Where the OpenAPI document goes.** The OpenAPI document is the input to tooling, not a doc page: generators and validators take it as `-i <spec file>` — "location of the OpenAPI spec, as URL or file" (https://openapi-generator.tech/docs/usage/). Keep it at a stable, tool-referenced path outside the docs source tree (`openapi/openapi.yaml` or `api/openapi.yaml`), and have the docs build read it. Do not keep a second copy under `docs/`; a duplicated spec is a spec that will disagree with itself.

**What to gitignore.** MkDocs makes the rule explicit: `docs_dir` defaults to `docs`, `site_dir` defaults to `site`, and "If you are using source code control you will normally want to ensure that your *build output* files are not committed … `site/`" (https://www.mkdocs.org/user-guide/configuration/). Sphinx is the same shape with an explicit output directory (`sphinx-build -M html sourcedir outputdir`: https://www.sphinx-doc.org/en/master/usage/quickstart.html). Ignore the site build, generated API pages, coverage/HTML reports, and any cache the generator writes.

**Diagrams.** Prefer text-defined diagrams so the source diffs and versions with the prose: Mermaid renders "Markdown-inspired text definitions" and exists specifically so diagrams can live in the same workflow as code (https://mermaid.js.org/intro/). Commit the diagram source; commit a rendered SVG/PNG only when a published page must embed a raster and the renderer cannot run in the build.

**Exported reports.** Commit a small, stable export only if the docs link to it and it cannot be regenerated deterministically; otherwise publish it as a release asset ("If you need to distribute large files within your repository, you can create releases on GitHub.com instead of tracking the files" — https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github). Never commit generated PDFs that are rebuilt on every docs build.

---

## 6. Docs at root vs `docs/`, and the community-health files

**GitHub only recognises specific locations.** For community health files: "If you put your README file in your repository's hidden `.github`, root, or `docs` directory, GitHub will recognize and automatically surface your README"; with more than one, precedence is `.github`, then root, then `docs` (https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes). The same three locations and the same order apply to the other health files: "For supported files that can be stored in more than one location, GitHub uses the following order of precedence: The `.github` folder, The root of the repository, The `docs` folder" (https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file).

**Supported files and their constraints.** The supported set includes `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`, `ACCESSIBILITY.md`, plus `FUNDING.yml` and issue/PR templates; but "Store issue templates and their configuration file in `.github/ISSUE_TEMPLATE`" and "Store `FUNDING.yml` … in the `.github` folder" — those two are *not* free to move, and "You cannot create a default license file. License files must be added to individual repositories so the file will be included when a project is cloned, packaged, or downloaded" (same page).

**Recommendation.** Keep `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `SUPPORT.md` and `LICENSE` at the repository root. Root is recognised for all of them, survives packaging/cloning, and avoids the trap below.

**Why not put user docs at `docs/` *and* rely on it for health files.** GitHub Pages can only publish from "the root of the repository (`/`) on the source branch or a `/docs` folder on the source branch" (https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site). Combined with the health-file precedence above, `docs/` is doing three jobs at once: docs source, health-file fallback, and publish root. `docs/` is still the right home for the user documentation (it is MkDocs' default `docs_dir`), but health files should stay at root so that the doc tree stays free for documentation.

**Root README stays thin.** GitHub's own guidance: "A README should only contain information necessary for developers to get started using and contributing to your project" (https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes). Google's chapter gives the same failure mode for landing pages: if something "is doing more than being a traffic cop, it is *not* doing its job" (https://abseil.io/resources/swe-book/html/ch10.html).

---

## 7. Recommended docs tree

```
repo/
├── README.md                  # what/why/quickstart, links only
├── CONTRIBUTING.md            # root: GitHub-recognised
├── SECURITY.md                # root: GitHub-recognised
├── CODE_OF_CONDUCT.md         # root: GitHub-recognised
├── SUPPORT.md                 # optional, root or .github
├── LICENSE                    # must live in each repo
├── CHANGELOG.md
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
├── openapi/
│   └── openapi.yaml           # committed contract, single source for API ref
└── docs/                      # MkDocs/Sphinx source root
    ├── index.md               # docs landing page (traffic cop)
    ├── tutorials/             # learning-oriented
    ├── how-to/                # goal-oriented
    ├── reference/             # information-oriented
    │   ├── api/               # generated at build time -> gitignored
    │   └── cli.md
    ├── explanation/           # understanding-oriented (design rationale for users)
    ├── adr/
    │   ├── README.md          # index + status legend + how to add one
    │   └── 0001-record-architecture-decisions.md
    ├── design/                # RFCs, design docs; excluded from site build
    │   └── 2026-11-17-slug.md # or NNNN-slug.md
    ├── research/              # investigation/spike reports; excluded from build
    │   └── 2026-11-17-slug.md
    └── assets/                # images, diagram sources (.mmd, .drawio)
```

Rules that make the tree hold: one artefact per directory; `docs/adr/` is append-only; `docs/design/` and `docs/research/` are excluded in `mkdocs.yml`; `reference/api/` is written by the build and gitignored; `site/` (or `_build/`) is gitignored; every directory has an `index.md` so no path is a bare listing.

---

## 8. Anti-patterns

1. **`docs/` as a dumping ground.** The classic failure is one page mixing concepts, API tables, a tutorial and a status list: "monolithic wiki pages with bunches of links (many broken or obsolete), some conceptual information about how the system worked, an API reference, and so on, all sprinkled together. Such documents fail because they don't serve a single purpose" (https://abseil.io/resources/swe-book/html/ch10.html). Diátaxis calls the same thing "blur" and "collapse" of the four modes (https://diataxis.fr/map/). Enforce one mode per file; a file that needs two modes is two files.

2. **The same document maintained in two places.** "It is important to designate *canonical* documentation: determine the primary source and consolidate other associated documents into that primary source (or deprecate the duplicates)" (https://abseil.io/resources/swe-book/html/ch10.html). Google's own wiki case study records "7 to 10 documents … on setting up Borg … only a few of which seemed to be maintained" (same page). Practical rule: one canonical path per fact; everything else links.

3. **Docs that link to paths that moved.** "When you change a URI on your server, you can never completely tell who will have links to the old URI … When someone follows a link and it breaks, they generally lose confidence in the owner of the server" (https://www.w3.org/Provider/Style/URI). Mitigations are cheap: keep old paths as redirects, prefer relative links, and make the build fail on broken links — MkDocs reports `validation.links.not_found` ("Doc file 'example.md' contains a link '../foo/bar.md', but the target is not found") and `--strict` turns warnings into errors (https://www.mkdocs.org/user-guide/configuration/).

4. **Committing generated output.** Site builds, generated API pages and exports are rebuildable; MkDocs states the rule directly (https://www.mkdocs.org/user-guide/configuration/). Committed output creates two truths and a diff nobody reviews.

5. **Storing the OpenAPI document twice** (once for the generator, once "for the docs"). The spec is tooling input (`-i <spec file>`, https://openapi-generator.tech/docs/usage/); duplicate copies drift silently.

6. **Health files buried in a subdirectory.** GitHub only looks in `.github`, root, and `docs`, in that order (https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file); a `SECURITY.md` under `docs/meta/` is invisible to the community profile.

7. **Publishing the decision log in the user docs nav.** Provider-side records and user-facing documentation serve different audiences and "should be kept apart" (https://abseil.io/resources/swe-book/html/ch10.html). ADRs stay in `docs/adr/` with an index, out of the tutorials/how-to nav.

8. **Undated, unnumbered design notes.** Without a number or an ISO date (https://www.w3.org/TR/NOTE-datetime) and a status field, a reader cannot tell whether the doc describes the system or an abandoned plan; Rust, Kubernetes and Python all carry both (section 3). The related trap is editing an accepted record in place instead of superseding it — Nygard's rule is to keep the old one and mark it superseded (https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

9. **Nesting a second `docs/` inside `docs/`.** `docs/docs/` is not required by MkDocs (`docs_dir` default is `docs`), by Sphinx, or by Diátaxis, whose own repo uses `source/` (https://github.com/evildmp/diataxis-documentation-framework/tree/main/source). It only lengthens every relative link.

10. **Creating the four empty Diátaxis folders up front.** Explicitly warned against: "It certainly does not mean that you should create empty structures for tutorials/howto guides/reference/explanation with nothing in them. Don't do that." (https://diataxis.fr/how-to-use-diataxis/). Move material when it exists; empty scaffolding invites misfiling.

---

## Citations

Primary / official

1. https://diataxis.fr/ — Diátaxis
2. https://diataxis.fr/map/ — The map
3. https://diataxis.fr/start-here/ — Start here: Diátaxis in five minutes
4. https://diataxis.fr/tutorials/ — Tutorials
5. https://diataxis.fr/how-to-guides/ — How-to guides
6. https://diataxis.fr/reference/ — Reference
7. https://diataxis.fr/explanation/ — Explanation
8. https://diataxis.fr/how-to-use-diataxis/ — Diátaxis as a guide to work
9. https://github.com/evildmp/diataxis-documentation-framework/tree/main/source — Diátaxis source tree (`source/`, Sphinx)
10. https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions — Documenting Architecture Decisions (Michael Nygard, 2011)
11. https://github.com/npryce/adr-tools — ADR Tools (README; `doc/adr`, `adr new -s`)
12. https://adr.github.io/ — Architectural Decision Records (homepage, ADR GitHub org)
13. https://github.com/adr/madr — Markdown Architectural Decision Records (`docs/decisions`, `nnnn-title.md`)
14. https://github.com/rust-lang/rfcs — Rust RFCs (process README)
15. https://raw.githubusercontent.com/rust-lang/rfcs/master/0000-template.md — Rust RFC template
16. https://github.com/kubernetes/enhancements/tree/master/keps — Kubernetes Enhancement Proposals (README)
17. https://raw.githubusercontent.com/kubernetes/enhancements/master/keps/NNNN-kep-template/README.md — KEP template
18. https://raw.githubusercontent.com/kubernetes/enhancements/master/keps/NNNN-kep-template/kep.yaml — KEP metadata schema
19. https://peps.python.org/pep-0001/ — PEP 1 – PEP Purpose and Guidelines
20. https://www.mkdocs.org/user-guide/configuration/ — MkDocs configuration (`docs_dir`, `site_dir`, `exclude_docs`, link validation)
21. https://www.sphinx-doc.org/en/master/usage/quickstart.html — Sphinx: Getting started
22. https://openapi-generator.tech/docs/usage/ — OpenAPI Generator: Usage (`-i/--input-spec`)
23. https://mermaid.js.org/intro/ — About Mermaid
24. https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes — About the repository README file
25. https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file — Creating a default community health file
26. https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories — About community profiles for public repositories
27. https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site — Configuring a publishing source for your GitHub Pages site
28. https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github — About large files on GitHub
29. https://www.w3.org/Provider/Style/URI — Cool URIs don't change (Tim Berners-Lee, 1998)
30. https://www.w3.org/TR/NOTE-datetime — Date and Time Formats (W3C Note, ISO 8601 profile)
31. https://the-turing-way.netlify.app/reproducible-research/compendia — The Turing Way: Research Compendia
32. https://abseil.io/resources/swe-book/html/ch10.html — Software Engineering at Google, ch. 10 "Documentation" (Tom Manshreck)

Secondary (practitioner accounts, vendor guidance)

33. https://www.industrialempathy.com/posts/design-docs-at-google/ — Design Docs at Google (Malte Ubl)
34. https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/best-practices.html — Best practices for using architectural decision records (AWS Prescriptive Guidance)
