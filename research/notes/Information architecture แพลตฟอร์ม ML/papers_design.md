# Papers on designing ML/data platforms and tools for practitioners (implications for a CV platform)

## 1. Interview studies of ML practitioner workflows and pain points

### Takeaway
Interview studies agree that the pain sits in data quality, cross-role handoffs, and post-deployment validation and monitoring, not in model training. A CV platform's information architecture should centre on the dataset/data-quality loop and make versions, validation and monitoring first-class.

### Cited Findings
- Sambasivan, Kapania, Highfill, Akrong, Paritosh, Aroyo, "Everyone wants to do the model work, not the data work: Data Cascades in High-Stakes AI", CHI 2021. Interviews with 53 AI practitioners (India, East/West Africa, USA); 92% experienced data cascades, defined as compounding events where data issues cause downstream negative effects. Cascades are pervasive, invisible, delayed but often avoidable. Authors call for treating data excellence as first-class. — [Google Research](https://research.google/pubs/everyone-wants-to-do-the-model-work-not-the-data-work-data-cascades-in-high-stakes-ai/)
  - Requirement: surface label/data-quality issues early and visibly (dataset health panel, label-error flags, annotator agreement) and carry data-quality status forward to training and deployment views, so problems are not invisible until late.
- Shankar, Garcia, Hellerstein, Parameswaran, "Operationalizing Machine Learning: An Interview Study", arXiv 2209.09125 (Sept 2022; no venue listed on arXiv page). 18 MLEs interviewed. Success depends on Velocity, Validation, Versioning. Documents pain points, anti-patterns and tooling implications. — [arXiv](https://arxiv.org/abs/2209.09125)
  - Requirement: fast experiment loops (quick train/eval on subsets), staged validation before promote, and versioning of datasets, labels, models and configs linked together.
- Nahar, Zhou, Lewis, Kästner, "Collaboration Challenges in Building ML-Enabled Systems: Communication, Documentation, Engineering, and Process", ICSE 2022 (Distinguished Paper). Interviews with 45 practitioners from 28 organizations; collaboration points around requirements, data and integration; smaller or newer-to-ML organizations struggle more. — [arXiv](https://arxiv.org/pdf/2110.10234), [ICSE page](https://conf.researchr.org/details/icse-2022/icse-2022-papers/153/Collaboration-Challenges-in-Building-ML-Enabled-Systems-Communication-Documentation)
  - Requirement: shared artifacts (data spec, model card, requirements/target metrics) that annotators, ML engineers and product owners all see; role-appropriate views over the same project.
- Sculley et al., "Hidden Technical Debt in Machine Learning Systems", NeurIPS 2015. Hidden maintenance costs: entanglement, hidden feedback loops, undeclared consumers. — [NeurIPS](https://neurips.cc/virtual/2015/poster/5680)
  - Requirement: show downstream consumers of each dataset/model version (lineage) before allowing edits or deletion.
- Shankar and Parameswaran, "Towards Observability for Production Machine Learning Pipelines", PVLDB 15(13), 2022 (vision); proposes end-to-end observability with assisted detection, diagnosis, reaction, built as a "bolt-on" over existing tools. Related CIDR 2022 paper (MLTRACE) is separate. — [arXiv](https://arxiv.org/pdf/2108.13557), [CIDR 2022](https://mail.vldb.org/cidrdb/2022/towards-observability-for-machine-learning-pipelines.html)
  - Requirement: monitoring should link a detected drift or failure to its cause (data slice, dataset version, model version), not just alert.

### Inferences
- For a CV labeling-to-deployment platform the primary navigation spine is probably Data -> Labels/Quality -> Train/Evaluate -> Deploy/Monitor, with versioning cutting across all of it.
- The "invisible and delayed" finding argues for proactive indicators (badges, health scores) in navigation rather than burying quality in a separate report page.

### Gaps
- Did not retrieve the full Sambasivan cause taxonomy (page gave only the headline numbers).
- The Shankar interview paper's venue is not stated on the arXiv page (I did not verify a later publication).
- No CV-specific interview study was found.

## 2. Platform papers (TFX, Michelangelo, Overton, Ease.ml, MLflow)

### Takeaway
Production platforms converge on an end-to-end lifecycle with standardized components, declarative specs, tracked experiments and CI-style gates for models. They are mostly engineer/infrastructure-facing, so UI-level information architecture is largely left to us.

### Cited Findings
- Baylor et al., "TFX: A TensorFlow-Based Production-Scale Machine Learning Platform", KDD 2017. General-purpose platform at Google; integrating components cut time to production from months to weeks; Google Play case study with continuously refreshed models. (Author list differs across sources; first authors Baylor, Breck, Cheng, Fiedel.) — [Google Research](https://research.google/pubs/tfx-a-tensorflow-based-production-scale-machine-learning-platform/)
  - Requirement: pipeline as the unit (ingest -> validate -> train -> evaluate -> push) with automatic data validation and a continuous retrain path.
- Uber, "Meet Michelangelo: Uber's Machine Learning Platform", Uber Engineering blog, Sept 2017 (not peer reviewed). ML-as-a-service to standardize workflows; covers manage data, train, evaluate, deploy, predict, monitor; motivated by fragmented tools and no standard path to production. — [Uber blog](https://www.uber.com/en-UA/blog/michelangelo-machine-learning-platform/)
  - Requirement: one consistent path from dataset to deployed endpoint with the same objects (project, dataset, model, deployment) everywhere.
- Ré, Niu, Gudipati, Srisuwananukorn, "Overton: A Data System for Monitoring and Improving Machine-Learned Products", CIDR 2020. Declarative abstractions; supervision separated from model definition; schema describes payloads and tasks, not architecture; monitors fine-grained quality, diagnoses errors, handles conflicting supervision; abstract reports 1.7-2.9x error reduction vs. production systems. — [CIDR](https://vldb.org/cidrdb/2020/overton-a-data-system-for-monitoring-and-improving-machine-learned-products.html), [arXiv](https://arxiv.org/pdf/1909.05372)
  - Requirement: let users improve a product by editing data/supervision and slices (label sources, weak labels, auto-label provenance) rather than model code; track quality per slice/tag.
- Renggli et al., "Continuous Integration of Machine Learning Models with ease.ml/ci", MLSys 2019 (arXiv 1903.00278; no VLDB version found). DSL for CI conditions with statistical guarantees; ~2K labels per test for 1-point tolerance at 0.999 reliability; up to two orders of magnitude label savings; alarms when test set needs refreshing. — [MLSys](https://proceedings.mlsys.org/paper_files/paper/2019/hash/4284d31e68c0a4a39dcdad167ac4bd72-Abstract.html)
  - Requirement: model promotion gates ("do not deploy if mAP on holdout drops > x") and a warning when the held-out test set is stale or overused.
- Zaharia et al., "Accelerating the Machine Learning Lifecycle with MLflow", IEEE Data Eng. Bull. 41(4), 2018. Experiment tracking, reproducible runs, model packaging/deployment. — [PDF](https://www.cs.berkeley.edu/~alig/papers/mlflow.pdf)
  - Requirement: every training run is a record with params, dataset version, metrics, artifacts; runs comparable side-by-side; one-click reproduce.

### Inferences
- Michelangelo, TFX and MLflow are the reference for the "Runs/Models/Deployments" object model; Overton is the reference for data-centric improvement loops, which fits an auto-labeling product.
- Ease.ml/ci's label-budget framing maps directly onto how many labeled images are needed to trust a model comparison.

### Gaps
- Michelangelo has no peer-reviewed paper that I found; only blog posts.
- None of these papers report UI usability studies.

## 3. Visual analytics for model evaluation and slice discovery

### Takeaway
Evaluation tools converge on slices (subgroups) as the central object, with programmatic or natural-language slice definition, side-by-side model comparison and exportable reports. Automatic slice discovery is feasible for images.

### Cited Findings
- Wexler, Pushkarna, Bolukbasi, Wattenberg, Viegas, Wilson, "The What-If Tool: Interactive Probing of Machine Learning Models", arXiv 1907.04135 (2019), IEEE VIS/VAST 2019 (TVCG). Open-source, minimal-coding probing of hypothetical inputs, feature importance, comparing models and data subsets, fairness metrics; reports usage at organizations. — [arXiv](https://arxiv.org/abs/1907.04135)
  - Requirement: per-example inspector with edit-and-re-predict and compare-two-models views, with no code needed.
- Wu, Ribeiro, Heer, Weld, "Errudite: Scalable, Reproducible, and Testable Error Analysis", ACL 2019, pp. 747-763. Error hypotheses formalized reproducibly, applied to all instances rather than samples, and tested via counterfactual analysis; query DSL; user study with experts. — [IDL](https://idl.uw.edu/papers/errudite), [PDF](https://homes.cs.washington.edu/~marcotcr/acl19_errudite.pdf)
  - Requirement: saved, named, re-runnable error queries over the full eval set (e.g. "small objects, night, class=scratch") instead of ad hoc scrolling.
- Cabrera, Fu, Bertucci, Holstein, Talwalkar, Hong, Perer, "Zeno: An Interactive Framework for Behavioral Evaluation of Machine Learning", CHI 2023. 18 semi-structured interviews found behavioral evaluation is collaborative and use-case-first and poorly supported by task-specific tools; Zeno offers Python API plus UI, slice creation, exportable reports, test suites. — [arXiv 2302.04732](https://arxiv.org/pdf/2302.04732), [CMU](https://www.hcii.cmu.edu/news/cmu-researchers-release-zeno-machine-learning-model-evaluation)
  - Requirement: slices defined from metadata/tags, shareable report links, regression test suites that run on each new model.
- Eyuboglu et al., "Domino: Discovering Systematic Errors with Cross-Modal Embeddings", ICLR 2022. Cross-modal embeddings and error-aware mixture model discover underperforming slices and name them in natural language; evaluated across 1,235 settings; names correct in 35% of settings; +17 points precision-at-10 over unimodal in one setting. — [arXiv](https://arxiv.org/pdf/2203.14960), [ICLR](https://iclr.cc/virtual/2022/poster/6148)
  - Requirement: an "Suggested weak slices" panel for detection/segmentation models, each with text description, size, metric gap and a link to the images and a "send to relabel" action.

### Inferences
- Slice discovery output is only trusted if the text description is verified by the user; the suggestion list should be labelled as hypotheses (35% exact-name rate).
- Closing the loop (slice -> relabel/active-learn queue -> retrain -> re-evaluate) is the product differentiator for a labeling platform; the papers cover only the diagnosis half.

### Gaps
- Domino and Zeno results are not CV-detection specific (Domino covers classification-style settings); transfer to detection/segmentation is untested here.
- Did not read full papers' user-study numbers for What-If Tool.

## 4. Information architecture and navigation for complex enterprise software

### Takeaway
The solid evidence found concerns progressive disclosure/training wheels and adaptive vs. adaptable menus; I found no peer-reviewed command-palette study. Design guidance below is therefore derived partly from secondary sources and flagged as such.

### Cited Findings
- Progressive disclosure: defers advanced or rarely used features to a secondary display so apps are easier to learn and less error-prone; attributed to Nielsen (1995) with roots in Carroll and colleagues at IBM in the 1980s (secondary summaries, NN/g page itself not retrieved). — [Nielsen newsletter post](https://jakobnielsenphd.substack.com/p/progressive-disclosure), [Wikipedia](https://en.wikipedia.org/wiki/Progressive_disclosure)
- Training wheels: reduced-function system blocks common learner error states (Carroll and Carrithers, 1984, CACM and Human Factors); Carroll and Catrambone found trained subjects did better on advanced full-system tasks. — [ACM record](https://www.springerpflege.de/doi/10.1145/29933.275625)
- Findlater and McGrenere, CHI 2004: compared static, adaptive and adaptable split menus; adaptable (user-controlled) is the alternative to system-driven adaptation. — [PDF](https://www.cs.ubc.ca/labs/edapt/papers/findlater2004.pdf)
- Scarr, Cockburn, Gutwin, Bunt, "Improving Command Selection with CommandMaps", CHI 2012 (best paper): flattened, spatially stable command layout; novices no different from menus, experts significantly faster than menus and Ribbon. Follow-up CHI 2014 tested in Word and Pinta. — [Manitoba HCI](https://hci.cs.umanitoba.ca/publications/details/improving-command-selection-with-commandmaps)
  - Requirements: (a) default to a small role-based set of nav items (annotator vs. ML engineer vs. admin) with "More" for advanced items; (b) keep item positions stable, avoid auto-reordering that breaks spatial memory, prefer user-controlled pinning/favourites; (c) provide a global keyboard-searchable command/search palette so experts can jump to any project, dataset, run, or action without walking the menu (no direct empirical CV/ML evidence found; justified by the CommandMaps expert-speed result and general command-selection research).

### Inferences
- Role-based views are best implemented as defaults plus progressive disclosure, not hard permissions-based hiding, so users can still discover advanced features.
- A command palette serves experts; novices still need visible navigation, as CommandMaps showed no novice gain from expert-oriented layouts.

### Gaps
- No CHI/CSCW paper specifically on command palettes found; searched once with no relevant hits.
- No paper found on role-based views in ML platforms specifically.
- NN/g progressive disclosure article not directly fetched; the claims come from secondary summaries.
