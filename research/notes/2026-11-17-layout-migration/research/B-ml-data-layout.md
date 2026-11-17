STATUS: DONE

TL;DR
1. Cookiecutter Data Science v2 puts `data/` in `.gitignore` by default and treats raw data as immutable; the four buckets are `raw/` → `interim/`/`processed/`, plus `external/`.
2. The consistent, documented pattern is: heavy artifacts out of git (DVC `.dvc` pointer files or LFS pointers), only tiny fixtures committed, and a pointer/metadata file in git per artifact.
3. `data/` and `weights/` are *inputs and outputs*, never code: they stay unversioned in git and are either DVC-tracked, LFS-tracked, or fetched by URL.
4. Notebooks are for exploration; anything reused graduates into an importable package (`src/<pkg>/`), which is the shared guidance from CDS v2, Kedro and MLflow.
5. There is no single universal name for a weights directory (`checkpoints/`, `weights/`, `models--org--name/` all exist); pick one, gitignore it whole, and keep a manifest instead.

Research date: 2026-11-17. All URLs below were fetched on that date; version numbers named are the ones live at that time.

---

## 1. Cookiecutter Data Science v2 layout

CDS v2's documented default tree (https://cookiecutter-data-science.drivendata.org/) is:

```
data/{external,interim,processed,raw}
docs/        models/      notebooks/     references/
reports/figures          <module_name>/ (the Python package)
Makefile     pyproject.toml   requirements.txt
```

Purposes as stated on that page:

| Dir | Stated purpose |
|---|---|
| `data/external` | "Data from third party sources." |
| `data/interim` | "Intermediate data that has been transformed." |
| `data/processed` | "The final, canonical data sets for modeling." |
| `data/raw` | "The original, immutable data dump." |
| `models` | "Trained and serialized models, model predictions, or model summaries" |
| `notebooks` | "Jupyter notebooks. Naming convention is a number (for ordering), the creator's initials, and a short `-` delimited description, e.g. `1.0-jqp-initial-data-exploration`." |
| `references` | "Data dictionaries, manuals, and all other explanatory materials." |
| `reports` | "Generated analysis as HTML, PDF, LaTeX, etc." (`reports/figures` = generated graphics) |
| `<module_name>` | "Source code for use in this project" (`config.py`, `dataset.py`, `features.py`, `modeling/train.py`, `modeling/predict.py`, `plots.py`) |

**Stance on data/ being gitignored** — explicit, on the opinions page (https://cookiecutter-data-science.drivendata.org/opinions/):

> "by default, the `data/` folder is included in the `.gitignore` file. If you have a small amount of data that rarely changes, you *may* want to include the data in the repository. GitHub currently warns you if files are over 50MB and rejects any files over 100MB."

The reasoning given is the DAG argument: "**raw data must be treated as immutable**", "⛔ **Don't** overwrite your raw data with a newly processed or cleaned version", "⛔ **Don't** save multiple versions of the raw data", and consequently "data doesn't need source control in the same way that code does."

**Stance on data versioning** — CDS v2 does not mandate a tool. It offers a `dataset_storage` option at generation time (`none | azure | s3 | gcs`) and a `Makefile` recipe `make sync_data_up`; the opinions page recommends object storage plus a sync tool (awscli, s3cmd, s5cmd, azcopy, gcloud, cloudpathlib, fsspec) and mentions Git LFS as an alternative: "There is also the Git Large File Storage (LFS) extension which lets you track large files in git but stores the files on a separate server." (https://cookiecutter-data-science.drivendata.org/opinions/). The `using-the-template` guide adds: "Put these files into your `data/raw` folder and then run `make sync_data_up` to push the raw data to your cloud provider." (https://cookiecutter-data-science.drivendata.org/using-the-template/)

Also worth quoting, because it fixes the read-only rule: "it's okay to read and copy raw data to manipulate it into new outputs, but never okay to change it in place. This informs the design of the default `data/` directory subfolders in which data originates from `raw/` and `external/`, intermediate analytical outputs get serialized or cached in `interim/`, and final products end up in `processed/`."

---

## 2. DVC: data and weights live outside git

**What goes in git:** `.dvc/` internals (`.dvc/config`, optional git-ignored `.dvc/config.local`), the `*.dvc` pointer files, and `dvc.yaml`/`dvc.lock` for pipelines.

- `dvc init` creates `.dvc/config` and `.dvc/.gitignore`; the start guide shows `git status` staging `.dvc/.gitignore` and `.dvc/config` and committing them (https://dvc.org/doc/start/data-management/data-versioning).
- `dvc add data/data.xml` writes `data/data.xml.dvc`, a small human-readable YAML placeholder: "This small, human-readable metadata file acts as a placeholder for the original data for the purpose of Git tracking." The same page: "Now the *metadata about your data* is versioned alongside your source code, while the original data file was added to `.gitignore`." (https://dvc.org/doc/start/data-management/data-versioning)
- `.dvc` file schema (`outs` → `path`, `md5`, `size`, `nfiles`, `remote`, …) is documented at https://dvc.org/doc/user-guide/project-structure/dvc-files.

**The explicit "never commit data" statement** is in the internal-files page (https://dvc.org/doc/user-guide/project-structure/internal-files):

> "Note that DVC includes the cache directory in `.gitignore` during initialization. **No data tracked by DVC should ever be pushed to the Git repository, only the DVC files** that are needed to download or reproduce that data."

That page also documents the cache as content-addressable storage under `.dvc/cache` (`files/md5/<2-char>/<rest>` for files, `.dir` JSON manifests for directories), plus `.dvc/cache/runs`, `.dvc/tmp`, `.dvc/plots`.

**Remote storage** is the third leg: `dvc remote add -d storage s3://mybucket/dvcstore`, then `dvc push` / `dvc pull` (https://dvc.org/doc/start/data-management/data-versioning, https://dvc.org/doc/user-guide/data-management/remote-storage). The versioning overview frames the payoff as: "Use a familiar and cost-effective storage solution for your data and models … — free from Git hosting constraints", and "the original data file was added to `.gitignore`" (https://dvc.org/doc/example-scenarios/versioning-data-and-models).

Practical takeaway for a repo with app code: DVC is additive — it needs no server, and `.dvc` files sit next to the data directory so the tree still reads naturally.

---

## 3. Git LFS: what belongs in it, and what should not be tracked at all

**What LFS is for.** "Git Large File Storage (LFS) replaces large files such as audio samples, videos, datasets, and graphics with text pointers inside Git, while storing the file contents on a remote server" (https://git-lfs.com/). Setup is `git lfs install` once, `git lfs track "*.psd"` (or edit `.gitattributes`), and `.gitattributes` must itself be committed.

**What should not be tracked at all** — GitHub's own guidance pushes away from committing large things even via LFS (https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github):

- "If you need to distribute large files within your repository, you can create releases on GitHub.com instead of tracking the files."
- "Git is not designed to handle large SQL files. To share large databases with other developers, we recommend using a file sharing service."
- "Git is not designed to serve as a backup tool."
- For dependencies: "we recommend you use a package manager."

**Hard numbers.**
- Git (not LFS): warning above **50 MiB**, "GitHub blocks files larger than **100 MiB**" (about-large-files).
- Repo size: "We recommend repositories remain small, ideally less than **1 GB**, and less than **5 GB is strongly recommended**" (about-large-files).
- LFS per-file cap by plan: Free/Pro **2 GB**, Team **4 GB**, Enterprise Cloud **5 GB** (https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage).
- Free LFS quota: **10 GiB storage + 10 GiB bandwidth/month** on Free/Pro/Free-for-orgs; 250/250 on Team and Enterprise Cloud. Exceeding storage without a payment method means you "will not be able to push new files back up"; exceeding bandwidth means "Git LFS support is disabled on your account until the next month" (https://docs.github.com/en/billing/concepts/product-billing/git-lfs).

**Warnings that matter operationally** (billing page, same URL): every push of a changed LFS file pushes the *entire* file and counts against storage; "If you push a 500 MB file to Git LFS, you'll use 500 MB of the repository owner's storage… If you make a 1 byte change and push the file again, you'll use another 500 MB". Downloads, including GitHub Actions downloads, count as bandwidth. So a checkpoint you re-push on every training run is the worst case for LFS, and the reason to keep checkpoints out of git entirely.

**LFS tooling caveats** (https://github.com/git-lfs/git-lfs/blob/main/docs/man/git-lfs-faq.adoc): LFS "doesn't [track] by size" — `.gitattributes` is pattern-based only, and the docs "recommend using patterns rather than `--above`"; GitHub "rejects large files anywhere in the history of your repository, not just in the latest commit", so retro-fitting needs `git lfs migrate import --everything`; and adding patterns to files already committed requires `git add --renormalize .`.

**Verdict from the sources:** LFS is for assets that are genuinely versioned alongside code and individually small-ish (a few hundred MB). Model checkpoints and raw datasets belong in object storage or a model hub, not in git and usually not in LFS.

---

## 4. The read-only rule: immutable inputs vs generated outputs

**Immutable inputs.** CDS v2 states the rule directly: "**Raw data is immutable**—it's okay to read and copy raw data to manipulate it into new outputs, but never okay to change it in place" and "⛔ **Don't** *ever* edit your raw data, especially not manually, and *especially* not in Excel. This includes changing file formats or fixing errors" (https://cookiecutter-data-science.drivendata.org/opinions/). The pipeline framing is "Data analysis is a directed acyclic graph": "each step of your analysis is a node in a directed graph with no loops", and each step should be reproducible from code + `data/raw` (+ `data/external`) alone.

**Naming that makes the distinction obvious.** The recommended vocabulary is CDS's four buckets, and the docs are explicit that the flow matters more than the exact names: "the number or names of these folders is less important than flow of data between them". Concretely:

| Bucket | Kind | Rule |
|---|---|---|
| `data/raw` | input | immutable, never overwritten, never re-saved as a new version |
| `data/external` | input (third-party) | treat as read-only; record source/version in `references/` |
| `data/interim` | generated | safe to delete and regenerate; cache for long steps |
| `data/processed` | generated | canonical model-ready output; regenerable |
| `models/` | generated | "Trained and serialized models, model predictions, or model summaries" |
| `reports/` | generated | "Generated analysis as HTML, PDF, LaTeX, etc." |

**`inputs/` vs `outputs/`** is not the vocabulary CDS uses; CDS uses *provenance* names (`raw`/`external` = inputs, `interim`/`processed`/`reports` = outputs). Kedro uses the same provenance-ish idea but only names the input end explicitly: "We recommend you put raw data into `raw` and move processed data to other subfolders" (https://docs.kedro.org/en/stable/get_started/kedro_concepts.html). The test that generalises across both: *if deleting the directory loses information that cannot be recomputed, it is an input and must be preserved elsewhere; if it can be recomputed from code + inputs, it is an output and belongs in `.gitignore`.*

**DVC's own statement of the same rule:** raw data is added to `.gitignore` on `dvc add`, and the cache holds the bytes while git holds only the pointer (https://dvc.org/doc/start/data-management/data-versioning).

---

## 5. Weights and checkpoints: conventions that exist

There is **no single standard directory name**. The three documented conventions are:

1. **`checkpoints/`** — PyTorch Lightning. "Without a logger, checkpoints are saved to the `default_root_dir`… saves checkpoints to `'some/path/checkpoints/'`"; with a logger they go to the logger's dir: `logs/my_experiment/version_0/checkpoints/`. Location can be pinned explicitly with `ModelCheckpoint(dirpath=...)` (https://lightning.ai/docs/pytorch/stable/common/checkpointing_basic.html). Note the run-scoped shape: `<logger dir>/<experiment>/<version_N>/checkpoints/`.

2. **`models--<org>--<name>/`** — Hugging Face cache. Root is `~/.cache/huggingface/hub` by default, overridable via `cache_dir`, `HF_HOME` or `HF_HUB_CACHE`. Per-repo skeleton is `refs/`, `blobs/` (content-hashed), `snapshots/<commit>/` (symlinks), `trees/<commit>.json`, plus `.no_exist/`. Also: "`huggingface_hub` automatically creates a `CACHEDIR.TAG` file inside the cache directory… tells backup tools (e.g. Borg, restic, rsync) that the directory contains re-downloadable cache data and can be safely excluded from backups" (https://huggingface.co/docs/huggingface_hub/guides/manage-cache). Two consequences: HF caches are explicitly *regenerable*, so they must never be committed; and on Windows without symlink support or Developer Mode the blobs/snapshots layout degrades to direct copies ("the cache-system is less efficient as a single file might be downloaded several times").

3. **Run-scoped output dirs** — Ultralytics writes all run artefacts under a run directory, not a repo-level folder: `project` = "Name of the project directory where training outputs are saved. A relative path is placed under `runs_dir/<task>`", `name` = "Name of the training run. Used for creating a subdirectory within the project folder", and `save_dir` overrides both (https://docs.ultralytics.com/modes/train/). Predictions follow the same shape with `project`/`name`/`save_dir` (https://docs.ultralytics.com/modes/predict/).

**What this means for `.gitignore`:** whatever name you choose, ignore the *whole* directory rather than patterns for individual extensions, because checkpoints, optimizer state, and partial `.incomplete` downloads all appear next to each other, and HF/Lightning both nest by run or revision. Commit a small text manifest instead (run id → source weights URL or DVC hash → metrics), which is what CDS recommends when there is no tracker: "it's fine to start with homegrown tracking using file formats like JSON that are both human- and machine-readable" (https://cookiecutter-data-science.drivendata.org/opinions/).

**Third-party pretrained weights** are inputs, not outputs: download them at a pinned revision. HF documents the mechanism — `resolve_revision()` returns a `ResolvedRevision`, and "Every file is guaranteed to come from the same commit" (https://huggingface.co/docs/huggingface_hub/guides/manage-cache).

---

## 6. Notebooks: where they live, how they relate to `src/`

CDS v2's position is a heading, not a nuance: "**Notebooks are for exploration and communication, source files are for repetition**", with the justification "Source code is superior for replicability because it is more portable, can be tested more easily, and is easier to code review" (https://cookiecutter-data-science.drivendata.org/opinions/).

Placement and naming:
- Top-level `notebooks/`, named `<step>-<ghuser>-<description>.ipynb`, "e.g., `0.3-bull-visualize-distributions.ipynb`" (opinions page).
- Subdivide when it grows: "`notebooks/exploratory/` contains initial explorations, whereas `notebooks/reports/` is more polished work that can be exported as html to the `reports/` directory" (opinions page).
- Phased numbering: `PHASE.NOTEBOOK`, phases `0` data exploration, `1` cleaning/feature creation (writes `data/processed` or `data/interim`), `2` visualisations (writes `reports`), `3` modelling, `4` publication (https://cookiecutter-data-science.drivendata.org/using-the-template/).
- Do not co-author notebooks: "notebooks are challenging objects for source control (e.g., diffs of the `json` are often not human-readable and merging is near impossible), we recommended not collaborating directly with others on Jupyter notebooks." Mitigation offered: `nbautoexport`, which "automatically exports a `.py` version of your Jupyter notebook every time you save it", so reviewers can comment line-by-line.

**The graduation rule**, verbatim: "Don't write code to do the same task in multiple notebooks. If it's a data preprocessing task, put it in the pipeline at `<module>/data/make_dataset.py` and load data from `data/interim/`. If it's useful utility code, refactor it to `<module>`." And the tell-tale signs of when to graduate: "duplicating old notebooks to start new ones, copy/pasting functions between notebooks, and creating object-oriented classes within notebooks."

The mechanism is that the template makes the project an installed Python package, so notebooks import it:

```python
%load_ext autoreload
%autoreload 2
from <module_name>.data import make_dataset
```

Kedro states the same relationship for its own tree: "`notebooks` — Project-related Jupyter notebooks (can be used for experimental code before moving the code to `src`)" (https://docs.kedro.org/en/stable/get_started/kedro_concepts.html).

---

## 7. Research notebooks → production training pipeline

The documented path is **notebook → function → module → entry point**, and every major framework encodes it:

- **CDS v2**: `src`-equivalent is the installed package at repo root (`config.py`, `dataset.py`, `features.py`, `modeling/train.py`, `modeling/predict.py`), driven by `make data` / `make train` from the `Makefile` (https://cookiecutter-data-science.drivendata.org/, plus https://cookiecutter-data-science.drivendata.org/opinions/ on `make` as the DAG runner). For repo growth the docs suggest promoting experiment code to a top-level `research/` folder with per-experiment subfolders "(and a corresponding `data/research` data folder) that contains sub-folders for individual experiments. These sub-folders can contain their own notebooks, code, and even their own Makefiles that inherit from the parent project `Makefile`." — that is CDS's own sanctioned way to keep research sandboxes inside a project.
- **Kedro**: `src/` is the only code location; notebooks are pre-`src` scratch. Pipelines are assembled from nodes registered via `pipeline_registry.py`/`settings.py` under `src/<project>` (https://docs.kedro.org/en/stable/get_started/kedro_concepts.html).
- **MLflow Projects**: a runnable unit is a directory with `MLproject` (or just `.py`/`.sh` entry points) declaring `entry_points` with typed `parameters` and an `environment` (`python_env.yaml` / `conda.yaml` / Docker). Its documented "Project Organization" best practice is:
  ```
  ml-project/
  ├── MLproject      ├── python_env.yaml
  ├── src/           # train.py, evaluate.py, utils/
  ├── data/          # Sample/test data
  ├── configs/       ├── tests/
  ```
  (https://mlflow.org/docs/latest/ml/projects/). Note MLflow labels `data/` as "Sample/test data" — i.e. what lives in git there is a fixture, not the dataset.

**Practical rule the sources support:** a notebook cell becomes production the moment a second notebook needs it. At that point it moves into the package as a function with a CLI entry point (`train.py`/`predict.py`), and the notebook either imports it or is deleted. Nothing in the docs suggests keeping a parallel `scripts/` graveyard — CDS explicitly says "If it's in the template but you don't need it, delete it!"

---

## 8. Recommended ML-side tree

Generic shape for one repo that holds both product code and research code. Product code stays where it already is; everything below is the ML side.

```
repo/
├── .dvc/                          # committed: config; .dvc/.gitignore, .dvc/cache auto-ignored
├── .gitignore
├── apps/                          # product/app code, independent of research
├── research/                      # experiment sandbox (CDS "Example 3: Re-organizing")
│   └── 2026-11-label-quality/     # one folder per experiment: notes, plots, its own Makefile
├── notebooks/                     # 0.01-abc-explore.ipynb, 3.02-abc-baseline.ipynb
├── src/<pkg>/                     # the only code that ships: data.py, features.py, train.py, predict.py
├── data/                          # GITIGNORED (DVC-tracked); fixtures are the exception
│   ├── raw/          raw.dvc      # immutable inputs
│   ├── external/     external.dvc # third-party inputs, read-only
│   ├── interim/                   # generated, disposable
│   ├── processed/    processed.dvc
│   └── fixtures/                  # <= a few MB, committed: 2 images + label json for tests
├── weights/                       # GITIGNORED entirely
│   ├── pretrained/                # downloaded at a pinned HF revision; re-downloadable
│   └── checkpoints/<run-id>/      # best.pt / last.pt, optimizer state
├── models/                        # DVC-tracked model artefacts + committed metrics/*.json
├── reports/figures/               # generated plots
└── references/                    # data dictionaries, label specs, third-party licences
```

Rationale per line: `data/` split and immutability rules from CDS (§1, §4); `.dvc` pointers and cache-from-git exclusion from DVC (§2); `weights/` ignored wholesale because checkpoints are regenerable and LFS punishes re-pushes (§3, §5); `data/fixtures` is the CDS-sanctioned exception — "If you have a small amount of data that rarely changes, you *may* want to include the data in the repository" (§1); `research/` is CDS's own expansion pattern for congested `notebooks/` (§7); `src/<pkg>/` is where graduated notebook code goes, per CDS, Kedro and MLflow (§6, §7).

### `.gitignore` patterns and their justification

```gitignore
# --- data: everything is regenerable or tracked out-of-band (CDS §1, DVC §2)
data/raw/
data/external/
data/interim/
data/processed/
data/research/
!data/fixtures/            # tiny, rarely changing, committed on purpose (CDS opinions)
!data/**/*.dvc             # keep DVC pointers tracked

# --- DVC internals that must never be committed (dvc.org internal-files)
.dvc/cache/
.dvc/tmp/
.dvc/config.local          # may hold credentials

# --- weights and checkpoints (GitHub 100 MiB block; LFS storage/bandwidth)
weights/
models/**/*.pt
models/**/*.ckpt
models/**/*.safetensors
models/**/*.onnx
*.pth

# --- framework run artefacts and caches
runs/                      # Ultralytics runs_dir/<task>/...
mlruns/                    # MLflow tracking store
lightning_logs/            # Lightning default logger dir
logs/
.cache/
hub/                       # if HF_HOME is pointed inside the repo
**/.incomplete             # HF partial downloads

# --- generated reports (CDS: reports = "Generated analysis")
reports/figures/*
!reports/figures/.gitkeep

# --- secrets and notebook noise (CDS "Keep secrets and configuration out of version control")
.env
.ipynb_checkpoints/
```

Notes: `!data/fixtures/` must come after the `data/*` ignores, and if you ignore `data/` as a whole you cannot re-include a subdirectory in git — so ignore the subdirectories, not the parent. Committed `.dvc` files (`data/raw.dvc`) are the pointer that makes the ignored bytes reproducible; commit them with `git add data/raw.dvc data/.gitignore`, exactly as the DVC quickstart shows.

---

## Citations

Primary — official documentation (all fetched 2026-11-17)

1. https://cookiecutter-data-science.drivendata.org/ — "Cookiecutter Data Science" (home; directory structure)
2. https://cookiecutter-data-science.drivendata.org/opinions/ — "Opinions" (immutable raw data, data/ gitignored, notebooks vs source, modeling organisation)
3. https://cookiecutter-data-science.drivendata.org/using-the-template/ — "Using the template" (notebook phase naming, adding data, refactoring into modules)
4. https://dvc.org/doc/start/data-management/data-versioning — "Get Started with DVC"
5. https://dvc.org/doc/user-guide/project-structure/dvc-files — "`.dvc` Files"
6. https://dvc.org/doc/user-guide/project-structure/internal-files — "Internal Directories and Files" (cache, "No data tracked by DVC should ever be pushed to the Git repository")
7. https://dvc.org/doc/example-scenarios/versioning-data-and-models — "Versioning Data and Models"
8. https://dvc.org/doc/user-guide/data-management/remote-storage — "Remote Storage"
9. https://git-lfs.com/ — "Git Large File Storage" (home; what LFS replaces, setup)
10. https://github.com/git-lfs/git-lfs/blob/main/docs/man/git-lfs-faq.adoc — "git-lfs-faq(7)"
11. https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github — "About large files on GitHub" (50 MiB warning, 100 MiB block, 1 GB/5 GB repo guidance)
12. https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage — "About Git Large File Storage" (per-plan per-file caps, pointer format)
13. https://docs.github.com/en/billing/concepts/product-billing/git-lfs — "Git Large File Storage billing" (10 GiB / 250 GiB quotas, re-push accounting)
14. https://huggingface.co/docs/huggingface_hub/guides/manage-cache — "Understand caching" (HF hub cache layout, CACHEDIR.TAG, revision pinning)
15. https://lightning.ai/docs/pytorch/stable/common/checkpointing_basic.html — "Saving and loading checkpoints (basic)" (checkpoints/ location)
16. https://docs.ultralytics.com/modes/train/ — "Model Training with Ultralytics YOLO" (`project`/`name`/`save_dir`, runs_dir)
17. https://docs.ultralytics.com/modes/predict/ — "Model Prediction with Ultralytics YOLO" (same run-dir convention for prediction outputs)
18. https://mlflow.org/docs/latest/ml/projects/ — "MLflow Projects" (MLproject entry points, project-organisation best practice)
19. https://docs.kedro.org/en/stable/get_started/kedro_concepts.html — "Kedro concepts" (data/ not committed, notebooks precede src/)

Secondary

20. https://drivendata.co/blog/ccds-v2 — "CCDS V2 announcement" (linked from the CDS home page as the v2 change note; not relied on for any claim above)
