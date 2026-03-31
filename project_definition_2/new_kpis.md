> **Project implementation:** `README.md` and `dora-metrics-app-documentation.md` in this folder. Operational **daily refresh** is specified there and in `backend-components-documentation.md`. **Lead Post-Production** (Ready for QA → merge) and **Jira worklogs** are **first-release scope** (see `jira-backlog-dora-metrics-app.md`). Python deps: **`requirements.txt` + pip** (kein Poetry).

**MTTR Alpha (DEV responsibility only)**
- Issue created (Critical+) - first patch release containing commit to fix

**MTTR Beta (Full Cycle)** (NOT TO BE DONE NOW)
- Incident created (ServiceDesk) - Incident ready to be closed (ServiceDesk)

**Deployment Frequency**:
- Count of `customer_release = true` tags per time period (RC/Beta tags excluded by name pattern) |

**Rework Rate**
Anzahl der Patches je Minor im Vergleich - Visualisierung ausstehend
Normale Releases im Vergleich zu Patches


**Change Failure Rate** 
- Jira Bugs + GitLab Tags | Ratio of `customer_release` tags that have at least one associated `healthy = true` production bug (matched via `affects_version` ↔ tag name); bugs with `healthy = false` are excluded from the count as data-quality unresolved

**Release Wait time**
- merged_at → release_tag
👉 How long “ready” code sits before customers get it
Feature stream (master): Shows: batching, release cadence, QA gating
Patch stream (x.x): Shows: incident responsiveness

**Lead Time for Changes**
Lead Time for Changes = time from first commit of a change until the first customer release that contains that change, measured separately by target branch / delivery stream.

**Lead Post-Production Time for Changes
Features - Time from Ready for QA Merged into Master
Bugs - Time from Ready for QA merged into Branch 9.x 10.x 11.x und auch Master

### Track separately, not just as a global aggregate:
#### master → feature lead time
first_commit_timestamp → first customer release on the feature delivery stream that contains the MR commit
- target_branch = master
- change_stream = feature

### 9.x, 10.x, 11.x → patch / maintenance lead time
first_commit_timestamp → first customer release tag on that same maintenance branch that contains the MR commit

- master measures feature delivery
- x.x branches measure maintenance / hotfix delivery

Details:

Recommended Output Fields

Per change:

mr_id
target_branch
change_stream
first_commit_timestamp
merged_at
release_tag
release_branch
release_timestamp
lead_time_hours
Recommended Dashboard Views
1. Overall
median lead time
p75 / p90
2. By branch
master
9.x
10.x
11.x
3. By stream
feature
patch
4. Split view

Also break lead time into:

first_commit → merged_at = development/review time
merged_at → release_tag = release wait time
Concise Instruction

Track Lead Time for Changes from the first commit in an MR to the first customer release tag containing that change.
Measure and report this separately by target branch:

master = feature lead time
9.x, 10.x, 11.x = patch / maintenance lead time
Required meta fields: mr_id, target_branch, first_commit_timestamp, merged_at, effective_commit_sha, release_tag, release_branch, release_timestamp, change_stream, lead_time_hours.
Exclude non-customer tags such as rc and beta.
Dashboard must show aggregate, per-branch, and feature-vs-patch views.

That’s the version you should use.