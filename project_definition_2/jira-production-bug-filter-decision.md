# Jira Production-Bug Filter (CFR/MTTR) – Entscheidung

## Problem
Für **CFR** und **MTTR** brauchen wir in Jira eine stabile Definition von „Production Bug".
Nur nach IssueType `Bug` zu filtern ist zu unscharf (würde interne/QA-Bugs mitzählen).  
Nur ServiceDesk/Exalate zu nehmen ist zu eng (Incidents ohne ServiceDesk-Ticket fehlen).

## Entscheidung (Filter)
Ein Jira-Issue wird geholt, wenn:
- `issuetype in ("Bug","Bug Subtask")`
- innerhalb Lookback (z.B. 2 Jahre)

Ob es sich um einen Production Bug handelt, wird **nicht per JQL gefiltert**, sondern per Health-Tag im Export bestimmt.
Kriterien: `Affects Versions`, `cf[10114]` (EXALATE), `cf[10123]` (CUSTOMERNAME), Parent-Kontext, Fix Versions.

## Konsequenz (Interpretation)
- `healthy = true` + `healthmemo = "post-production ..."` -> extern sichtbarer Production Bug
- `healthy = true` + `healthmemo = "pre-production ..."` -> internes/QA-Issue, kein Production Bug
- `healthy = false` -> fehlende Daten, nicht sicher zuzuordnen (muss bereinigt werden)

## Health-Felder im Export
- `healthy` (boolean): `true` = gesund, `false` = ungesund
- `healthmemo` (string): Begründung/Klassifikation (z.B. `post-production`, `pre-production ...`, `unhealthy - ...`)

## Data-Hygiene Regeln (damit es zuverlässig bleibt)
- **Prod-Incident?** Dann **mindestens eins** von `cf[10114]` (EXALATE) / `cf[10123]` (CUSTOMERNAME) befüllen.
- **Kein ServiceDesk-Ticket?** Dann `cf[10123]` (CUSTOMERNAME) mit Kundennamen befüllen (nicht leer, nicht "n/a").
- **Immer `Affects Versions` setzen** (muss zum GitLab-Tag passen), sonst fällt das Issue aus CFR/Release-Zuordnung.
- **Sauber schließen** (Resolution/Status konsistent), sonst verfälscht MTTR.
- **Mehrere Tickets = ein Incident?** Dann einen "Master"/Labeling nutzen, damit CFR später sauber dedupliziert werden kann.

## (Optional) Bessere Lösung langfristig
Ein eigenes, strukturiertes Incident-Modell (IssueType "Incident", Severity, „caused by release") wäre robuster als Freitext-Customfields - oder ein Label.


## Vollständige Entscheidungslogik

```
IF issue_type NOT IN ("Bug", "Bug Subtask"):
    EXCLUDE issue
ELSE IF created < lookback_from:
    EXCLUDE issue
ELSE:
    INCLUDE issue

    # --- Primary health check on the issue itself ---
    unhealthy_reasons = []

    IF affects_versions is empty:
        unhealthy_reasons += "unhealthy - affected_version missing"

    IF cf[10114] (EXALATE) is empty AND cf[10123] (CUSTOMERNAME) is empty AND fix_versions is empty:
        unhealthy_reasons += "unhealthy - customer missing and fix_version missing"

    IF cf[10114] (EXALATE) is empty
       AND cf[10123] (CUSTOMERNAME) has value(s)
       AND ALL cf[10123] values contain "plunet":
        unhealthy_reasons += "unhealthy - Customer set to Plunet only"

    # --- If healthy (no unhealthy reasons): done ---
    IF unhealthy_reasons is empty:
        healthy = true
        healthmemo = "post-production"
        DONE

    # --- Overrides (only when unhealthy) ---

    # Override 1: parent type/summary rescue
    IF parent_summary contains "test"
       OR parent_type IN ("techsupport","new feature","analysis","epic","improvement"):
        healthy = true
        healthmemo = "pre-production - parent is [parent_type]"
        DONE

    # Override 2: fix_version higher than affects_version
    IF max(fix_versions) > max(affects_versions):
        healthy = true
        healthmemo = "post-production due to higher fix_version"
        DONE

    # No override matched -> stays unhealthy
    healthy = false
    healthmemo = join(unhealthy_reasons, " and ")

    # --- Second pass: parent-based correction ---
    # Only for still-unhealthy Bug/Bug Subtask with a Bug parent.
    # Re-evaluates health using the parent's data (primary rules only,
    # no grandparent context).
    IF healthy = false
       AND issue_type IN ("Bug", "Bug Subtask")
       AND parent_type = "Bug"
       AND parent_key exists:

        FETCH parent_affects_versions
        FETCH parent_fix_versions
        FETCH parent_cf[10114] (EXALATE)
        FETCH parent_cf[10123] (CUSTOMERNAME)

        # Run the same primary check on the parent's data
        parent_unhealthy_reasons = []

        IF parent_affects_versions is empty:
            parent_unhealthy_reasons += "unhealthy - affected_version missing"

        IF parent_cf[10114] is empty AND parent_cf[10123] is empty AND parent_fix_versions is empty:
            parent_unhealthy_reasons += "unhealthy - customer missing and fix_version missing"

        IF parent_cf[10114] is empty
           AND parent_cf[10123] has value(s)
           AND ALL parent_cf[10123] values contain "plunet":
            parent_unhealthy_reasons += "unhealthy - Customer set to Plunet only"

        IF parent_unhealthy_reasons is empty:
            # Parent is healthy -> child becomes healthy too
            healthy = true
            healthmemo = "post-production due to parent"
            DONE

        # Parent is also unhealthy -> check fix_version overrides on parent
        IF max(parent_fix_versions) > max(parent_affects_versions):
            healthy = true
            healthmemo = "post-production due to parent"
            DONE

        # Parent also unhealthy and no override -> child stays unhealthy

    # --- Final pass (global override on remaining unhealthy issues) ---
    IF healthy = false
       AND ANY version value in (
            affects_versions,
            fix_versions,
            parent_affects_versions,
            parent_fix_versions
       ) contains "next minor - please branch from master":
        healthy = true
        healthmemo = "post-production - next minor stated"
```

### Erläuterung der Custom Fields
- **cf[10114] (EXALATE)**: Freitextfeld, befüllt von der Exalate-Integration mit dem Link zum ServiceDesk-Ticket (z.B. `"Acme Corp:\nhttps://plunethelp.atlassian.net/browse/CS-12345"`)
- **cf[10123] (CUSTOMERNAME)**: Manueller Eintrag des Kundennamens durch Mitarbeiter, Fallback wenn kein ServiceDesk-Ticket existiert
