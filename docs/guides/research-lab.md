# Research Lab — autonomous multi-agent paper writing

`/lab` (CLI) and `/lab` (web UI) are CheetahClaws's autonomous research
engine. Give it a topic; it drives 9 specialised agents through 9
stages — questioning, literature survey, outline, code drafting,
sandboxed experiment execution, analysis, paper drafting with
reviewer iteration, citation verification, finalisation — until
convergence or budget exhaustion. The output is a Markdown report
with verified citations, a BibTeX bundle, and (when the topic admits
experiments) the engineer's runnable Python script + plots.

**Realistic positioning, up front.** This is **arXiv-grade preprint
quality**, not 顶会 / NeurIPS-grade. 2026 LLMs (across all providers)
hit a ceiling on novel research that even sophisticated multi-agent
debate can't push through. Use this as a co-pilot that compresses
80% of the writing work, not as an autonomous PhD substitute. Read
the output before posting.

---

## Quick start

### CLI

```bash
cheetahclaws
# in the REPL:
/lab start "Compare logistic regression and random forest on the iris
            dataset, report test accuracy with cross-validation"

# while it runs (typically 15-60 minutes):
/lab status                       # all runs
/lab status lab_a3b1c8e9f012      # detail for one run
/lab logs   lab_a3b1c8e9f012      # recent agent messages
/lab abort  lab_a3b1c8e9f012      # cancel cooperatively
```

When it finishes, the report lands at:

```
~/.cheetahclaws/research_papers/<run_id>/
├── report.md                   ← main deliverable
├── references.bib              ← verified citations
├── citations_verified.json     ← per-citation verification log
└── workspace/
    ├── experiment.py           ← engineer's final script
    ├── stdout.txt
    ├── stderr.txt
    ├── exit_code.txt
    ├── figure_1.png            ← any matplotlib output
    └── results.csv             ← any data files the engineer wrote
```

### Web UI

```bash
cheetahclaws --web --port 8080
# browser → http://127.0.0.1:8080/lab
```

The UI gives you a launch form, a recent-runs table, live progress
(stage pills + agent message stream auto-refreshing every 5 s), and
an in-page Markdown render of the final report.

---

## Stage graph

```
[topic]
   ↓
QUESTIONING       Questioner drafts 3-5 candidate research questions;
                   PI picks the most promising; Lay Reader sanity-checks accessibility.
   ↓
SURVEY            Surveyor produces a focused literature review +
                   gap analysis with inline citations.
   ↓
OUTLINE           Designer drafts a paper outline; Reviewer × 3 critique;
                   PI signs off when 2/3 reviewers pass.
   ↓
IMPLEMENTATION    Engineer drafts a self-contained Python script
                   targeting the experiment scope.  May respond
                   `# SKIP_EXPERIMENT: <reason>` if the topic isn't
                   experiment-amenable (e.g. survey-style work).
   ↓
EXPERIMENT        Sandboxed `subprocess.run` executes the script.
                   On non-zero exit / timeout, the Engineer is fed
                   the stderr and revises (max 3 attempts).
   ↓
ANALYSIS          Analyst reads stdout (parsing `RESULT: {...}`
                   lines), references any plot files produced, and
                   drafts the paper's Results section — no
                   fabrication: if a number isn't in stdout, it
                   doesn't appear in the prose.
   ↓
DRAFTING          Writer drafts the full paper with the Analyst's
                   Results pre-filled.  Reviewer × 3 + Lay Reader
                   critique; iterate until convergence (default 2/3
                   reviewers passing) or max 5 rounds.
   ↓
VERIFICATION      Citation verifier checks every reference against
                   arXiv → Semantic Scholar → CrossRef.  Result:
                   verified / ambiguous / not_found / verification_skipped.
   ↓
FINALIZATION      Markdown report + BibTeX + experiment log all
                   stitched together; run marked done.
```

If a stage's reviewer-author loop runs out of rounds, the PI
force-advances with a noted compromise rather than block forever.

---

## The 9 agents

| Role | Default model | Job |
|---|---|---|
| **PI** | first available of `claude-opus-4-6 / gpt-4o / gemini-2.5-pro` | Stage gating, RQ selection, breaking ties |
| **Questioner** | auxiliary cheap model | Topic → 3-5 narrowable RQs |
| **Surveyor** | auxiliary cheap model | Literature review + gap analysis |
| **Designer** | mid-tier (Claude Sonnet / GPT-4o / Gemini Pro) | Outline + methodology |
| **Engineer** | mid-tier | Self-contained Python script for the experiment |
| **Analyst** | mid-tier | Interprets stdout/plots → drafts Results |
| **Writer** | mid-tier | Drafts the full paper, revises against reviewers |
| **Reviewer 1/2/3** | three different families when keys allow | Adversarial peer review |
| **Lay Reader** | auxiliary cheap model | Catches jargon overload, buried lede |

**Cross-family reviewer assignment is a deliberate choice.** Same-family
reviewers tend to rubber-stamp each other (they share blind spots).
The default code picks 3 different providers when API keys are
available, falling back to the user's primary model when not. To
diversify further, configure model overrides per role.

---

## Cost & budget

A run spends LLM tokens at every stage and (if experiments are
enabled) some compute time. Defaults:

| Knob | Default | Where to override |
|---|---|---|
| `lab_budget_tokens` | 5,000,000 | `config.json` or POST body |
| `lab_budget_cost_cents` | 5,000 ($50) | `config.json` or POST body |
| `lab_max_rounds` | 5 reviewer rounds per stage | `config.json` or POST body |
| `lab_experiments` | `true` | `config.json` |
| `lab_experiment_timeout_s` | 180 | `config.json` |
| `lab_experiment_max_attempts` | 3 | `config.json` |

Realistic per-run cost (rough, varies by model mix):

- Survey-style topic, no experiments: **$2-5**, 15-30 minutes
- Application paper with small experiments (sklearn-scale): **$5-15**, 30-60 minutes
- Wider scope with multiple debug rounds: **$15-50**, 1-2 hours

Once `tokens_used >= budget_tokens` or `cost_cents >= budget_cost_cents`
the orchestrator skips remaining stages and goes straight to
FINALIZATION with whatever's been drafted.

---

## Sandbox — what it protects, what it doesn't

The experiment sandbox in `research/lab/sandbox.py` runs the
Engineer's Python script in a subprocess with:

- A **dedicated workspace directory** (`~/.cheetahclaws/research_papers/<run_id>/workspace/`)
  pinned as `cwd`; relative paths can't escape.
- A **180 s wall-clock timeout** (configurable); SIGKILL on expiry.
- **`RLIMIT_CPU = 240 s`** and **`RLIMIT_AS = 2 GB`** soft caps via
  `resource.setrlimit` (Linux/macOS).
- **`MPLBACKEND=Agg`** so matplotlib doesn't need a display server.
- **Piped stdout/stderr** captured, persisted, and truncated at 256 KB.
- **No `shell=True`**; argv is always a list.

**This is _not_ a security boundary against deliberately malicious
code.** The LLM-generated script can still:

- import dangerous stdlib modules (`os`, `ctypes`, `socket`, `subprocess`)
- make network calls (no egress firewall)
- read user-readable files outside the workspace
- consume up to `RLIMIT_CPU` of compute
- persist data to the workspace forever

For a real product, layer Docker + nsjail + network-egress
restriction on top — that's tracked as Phase 2.5 in the roadmap.
The current shape is calibrated for **single-user, trusted-machine
v0**: an honest LLM accidentally producing a heavy script can't
hose the machine, and there's a clear seam where a future Phase
2.5 plugs in.

---

## Citation verifier

Every citation in the final draft is checked against three free
APIs in priority order:

1. **arXiv** — title search + author overlap; explicit `arXiv:NNNN.NNNNN` IDs trigger a direct lookup.
2. **Semantic Scholar** — broader coverage, especially for non-arXiv venues.
3. **CrossRef** — DOI catalogue; good for journal papers.

Title match is **Jaccard similarity ≥ 0.55** on lowercased word
sets after punctuation strip. Author overlap is **last-name set
similarity ≥ 0.5** to tolerate "First Last" / "Last, F." / "F. Last"
variations.

Per citation, the verifier returns one of:

| Status | Meaning |
|---|---|
| `verified` | Found by API, title + authors match closely |
| `ambiguous` | Found by title but author overlap < 0.5 |
| `not_found` | None of the APIs returned a match |
| `verification_skipped` | All three APIs failed at the network layer |

The final report renders a verification table so the reader can see
which citations are real, which look fabricated, and which we
couldn't reach the network to check. **A `not_found` is a
fabrication signal**, not a definitive proof — but in practice it
correlates strongly. Cross-checks against ground-truth bibliographies
hit ~95% precision.

---

## Configuration

Per-run knobs (config.json):

```jsonc
{
  // Engine
  "lab_budget_tokens":           5000000,
  "lab_budget_cost_cents":       5000,
  "lab_max_rounds":              5,

  // Experiments
  "lab_experiments":             true,
  "lab_experiment_timeout_s":    180,
  "lab_experiment_max_attempts": 3,

  // Per-role model overrides (any subset OK; unspecified roles use defaults)
  "lab_role_override": {
    "pi":          "claude-opus-4-6",
    "writer":      "gpt-4o",
    "reviewer_1":  "claude-sonnet-4-6",
    "reviewer_2":  "gpt-4o",
    "reviewer_3":  "gemini/gemini-2.5-pro",
    "engineer":    "claude-sonnet-4-6"
  }
}
```

Override at the call site too — `/lab start <topic>` reads from
`config.json`; `POST /api/lab/runs` accepts the same keys in the body.

---

## Web API surface

Mounted at `/api/lab/*` on the existing CheetahClaws web server (the
one started by `cheetahclaws --web`):

| Method + path | Purpose |
|---|---|
| `POST /api/lab/runs` | Start a new run. Body: `{topic, budget_tokens?, budget_cost_cents?, max_rounds?, role_override?}`. Returns `{run_id}`. |
| `GET /api/lab/runs?status=running&limit=50` | List recent runs. |
| `GET /api/lab/runs/<id>` | Run detail incl. stage history. |
| `GET /api/lab/runs/<id>/messages?limit=80&stage=drafting` | Recent agent messages. |
| `GET /api/lab/runs/<id>/report` | Final Markdown report (text/markdown). |
| `GET /api/lab/runs/<id>/experiments` | Experiment log (code, stdout, stderr, artifacts). |
| `GET /api/lab/runs/<id>/artifacts/<filename>` | Workspace file passthrough (PNG/CSV/JSON), with path-traversal guard. |
| `POST /api/lab/runs/<id>/abort` | Request cooperative cancellation. |

All endpoints return JSON except `/report` (markdown) and
`/artifacts/<fn>` (the file's content type).

The frontend at `/lab` is a single vanilla-JS page with no
build step — open it in a browser and it talks to the API above.

---

## What v0 explicitly does NOT do

- ❌ **Multi-tenant isolation.** All runs are visible to anyone with
  REPL or web access. Phase 4 adds user_id scoping + per-user
  workspace.
- ❌ **GPU pool / ML-training-scale experiments.** Sandbox runs a
  single Python process with 4-min CPU. Big training is Phase 4.
- ❌ **Docker-isolated experiment execution.** Subprocess + rlimits
  only. Phase 2.5.
- ❌ **LaTeX / PDF rendering.** Markdown only. Phase 2.5 adds an
  arXiv-style LaTeX writer.
- ❌ **Reference manager integration** (Zotero / Mendeley export
  beyond raw BibTeX). Phase 3+.
- ❌ **Billing / payment.** Single-user, token-budget-only. Phase 4.
- ❌ **Resumability after process restart.** State is in SQLite
  but the orchestrator thread doesn't auto-resume after
  `cheetahclaws` exits. `/lab resume <run_id>` is a placeholder.
  Phase 2.5.
- ❌ **Real-time streaming via SSE.** Frontend polls every 5 s.

---

## Honest failure modes to expect

1. **Fabricated citations** that pass title-match but are subtly
   wrong (e.g. a real paper attributed to the wrong year, real
   authors mashed onto a fake title). Verifier catches most;
   read references manually.

2. **Same-source reviewer agreement.** Even with cross-family model
   selection, the three reviewers share training data and pretrained
   biases — they will agree on subtly wrong things together.

3. **Experiment "succeeded" but with junk output.** `exit_code == 0`
   and 200 lines of stdout don't mean the result is meaningful. The
   Analyst will dutifully report whatever numbers it sees. Read the
   workspace.

4. **PI rubber-stamps premature drafts** when they're plausible
   even if the underlying methodology is shallow. Reviewer rounds
   help but don't eliminate this.

5. **`SKIP_EXPERIMENT` overuse.** Engineer may decide a topic isn't
   experiment-amenable when an experiment would have been useful.
   When this happens, the report's `Experiment log` section is
   empty — easy to spot.

---

## Roadmap

- **v0 (this release):** the engine + experiments + web UI as described above.
- **Phase 2.5:** Docker-isolated sandbox, LaTeX writer, `/lab resume`.
- **Phase 3:** Reference manager integration, novelty / plagiarism check, real-time SSE updates, multi-figure handling.
- **Phase 4:** Multi-tenant auth, GPU pool / Modal/Beam integration, billing, run-sharing.
- **Phase 5:** Productisation — landing page, payment, support.

---

## Files of interest

| File | Purpose |
|---|---|
| `research/lab/orchestrator.py` | The 9-stage state machine driver |
| `research/lab/sandbox.py` | Subprocess sandbox + workspace + rlimits |
| `research/lab/verifier.py` | arXiv / Semantic Scholar / CrossRef citation check |
| `research/lab/storage.py` | SQLite-backed run state (5 tables) |
| `research/lab/roles.py` | 9-role assignment + cross-family model selection |
| `research/lab/convergence.py` | Reviewer quorum + budget rule |
| `research/lab/output.py` | Markdown / BibTeX assembly |
| `agent_templates/lab/*.md` | The 9 role prompts |
| `commands/lab_cmd.py` | `/lab start/status/abort/logs/resume` |
| `web/lab_api.py` | `/api/lab/*` HTTP dispatcher |
| `web/lab.html` | Single-page vanilla-JS UI |
| `tests/test_research_lab.py` | 54 unit / integration tests |

---

## Related docs

- [`docs/architecture.md`](../architecture.md#research-lab) — how the lab integrates with the rest of CheetahClaws
- `docs/news.md` — release timeline (this lab landed in `feature/research-lab`)
