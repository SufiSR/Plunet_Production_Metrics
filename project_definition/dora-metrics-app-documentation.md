# DORA Metrics App - Documentation

- Source URL: https://plunet.atlassian.net/wiki/spaces/EN/pages/768933918/DORA+Metrics+App+-+Documentation
- Confluence Page ID: `768933918`

## Project Goal

Automated measurement and visualization of the 4 DORA core metrics for our software development, embedded in Confluence.

---

## DORA Metrics and Data Sources

| Metric | Data Source | Calculation Logic |
| --- | --- | --- |
| **Deployment Frequency**  | GitLab Tags  | Number of tags on protected branches (major branches) per time period  |
| **Lead Time for Changes**  | GitLab MRs + Tags  | Time from MR merged into Main until first tag containing the commit  |
| **Change Failure Rate**  | Jira Bugs + GitLab Tags  | Ratio of releases with production bugs (field "External Ticket Links" populated) based on "Affects Versions"  |
| **MTTR**  | Jira Bugs  | Time from bug created until status "Closed" (production bugs only)  |

---

## Constraints

### Source Systems

* GitLab Free (CI/CD)
* Jira Cloud (Bug Tracking)
* Confluence Cloud (Visualization)

### Branching Model

* Main branch for continuous integration
* Protected branches per major version (e.g. v2.x, v3.x)
* Tags for minor releases and patches (e.g. 2.1, 2.2, 2.2.1)
* Patches count as individual deployments

### Production Bugs

* Jira Issue Type: Bug or Bug Subtask
* Criterion: Field "External Ticket Links" is populated
* Resolved: Status "Closed"

---

## Technology Stack

| Component | Technology |
| --- | --- |
| Backend  | Java (Spring Boot)  |
| Database  | PostgreSQL  |
| Frontend  | Vue + Chart.js  |
| Deployment  | Docker Compose  |
| Integration  | iframe in Confluence  |

---

## Architecture

```
┌─────────────┐     ┌─────────────┐
│  GitLab API │     │  Jira API   │
└──────┬──────┘     └──────┬──────┘
       │                   │
       ▼                   ▼
┌─────────────────────────────────┐
│      Collector Service          │
│    (Daily Scheduled Job)        │
└───────────────┬─────────────────┘
                ▼
┌─────────────────────────────────┐
│      PostgreSQL Database        │
└───────────────┬─────────────────┘
                ▼
┌─────────────────────────────────┐
│    Web Dashboard (Vue.js)       │
│  (iframe in Confluence Cloud)   │
└─────────────────────────────────┘
```

---

## Operations

* **Hosting:** On-premise (Docker)
* **Update Frequency:** Daily (nightly job)
* **Historical Data:** Initial load from 2025
* **Access:** No authentication required (internal network)
* **Scope:** 26 repositories (dynamically expandable)

---

## MVP Roadmap

| Phase | Scope |
| --- | --- |
| Phase 1  | Aggregated value across all repos + time series (weeks/months)  |
| Phase 2  | Filtering per repository  |
| Phase 3  | Grouping by teams/products  |

