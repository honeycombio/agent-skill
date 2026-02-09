---
name: Honeycomb SLOs and Triggers
description: >
  This skill should be used when the user asks to "create an SLO", "set up a trigger",
  "configure alerts", "define error budgets", "set up burn alerts", "monitor reliability",
  "create a Service Level Objective", "configure alerting", "set up PagerDuty notifications",
  "design an SLI", "check burn rate", "set up Slack alerts for Honeycomb",
  "define thresholds for alerts", "create a latency SLO", "check SLO status",
  "check trigger status", "view my SLOs", "view my alerts",
  "monitor my service", "set up monitoring", "check error budget",
  or needs guidance on SLOs, triggers, alerting strategy, or notification configuration in Honeycomb.
  SLIs use calculated fields described in the query-patterns skill.
version: 1.0.0
---

# Honeycomb SLOs and Triggers

Guidance for configuring and reasoning about reliability in Honeycomb. The `get_slos`
and `get_triggers` tools document their own parameters — this skill focuses on
*designing* effective SLOs, *choosing* between SLOs and triggers, and *interpreting*
what the numbers mean.

**Availability**: SLOs require Pro or Enterprise plan. Triggers available on all plans.

## SLO vs Trigger — When to Use Which

| Question | SLO | Trigger |
|----------|-----|---------|
| "Are we meeting our reliability commitments?" | Yes | No |
| "Is something broken right now?" | No | Yes |
| "How fast are we burning our error budget?" | Yes (burn alerts) | No |
| "Did error count exceed a threshold?" | No | Yes |
| "Should we slow down deploys?" | Yes (budget remaining) | No |

**Rule of thumb**: SLOs measure reliability against commitments over time. Triggers catch immediate operational issues.

## Designing Effective SLOs

### Define the SLI
An SLI is a per-event boolean: was this event successful? Implemented as a calculated field returning 1 (success) or 0 (failure).

- **Latency SLI**: `LTE(duration_ms, 500)` — requests faster than 500ms
- **Availability SLI**: `LTE(http.status_code, 499)` — non-5xx responses
- **Business logic SLI**: `EQUALS(checkout.status, "completed")` — successful checkouts

### Set the Target
- Start conservative (99% before 99.99%)
- Measure current baseline first with P50/P99 queries
- Set target slightly above current performance
- Ask: what reliability do users actually need?

### Configure Burn Alerts
At minimum, two alerts:
- **Fast burn** (exhaustion time ~4h): pages on-call via PagerDuty
- **Slow burn** (budget rate over 24h): notifies team via Slack

### Best Practices
- Measure close to the user (at the edge, not deep in the stack)
- Design around user workflows, not team boundaries
- Favor broad SLOs over many narrow ones
- Start with one SLO, reduce noise, then expand

## Interpreting SLO Status

When reviewing SLOs with `get_slos`:
- **Budget remaining > 50%**: Healthy — room for risk
- **Budget remaining 10-50%**: Caution — slow down changes
- **Budget remaining < 10%**: At risk — freeze non-critical deploys
- **Budget negative**: Breached — investigate immediately with the production-investigation skill
- **Compliance at 0%**: Likely misconfigured SLI (wrong column, inverted logic, no matching events) — check the SLI definition

## Configuring Triggers

### Prefer Count-Based Over Percentile-Based
"50 requests slower than 2s" is more actionable than "P99 is 2100ms."
Use `COUNT WHERE duration_ms > threshold` instead of P99 triggers.

### Common Patterns
- **Error spike**: COUNT WHERE error = true, threshold > N in 5 min
- **Slow requests**: COUNT WHERE duration_ms > 2000, threshold > N in 5 min
- **Traffic drop**: COUNT WHERE is_root, threshold < N in 10 min (below normal)

### Best Practices
- **Name**: What the alert is. **Description**: What to do (link to runbook).
- Set duration 5-10 min minimum to avoid flapping
- Start less sensitive, tighten based on false positive rate

## Multi-Service SLOs

Share a single error budget across up to 10 services.
- SLI must be an environment-level calculated field
- Events from included services weighted equally
- Use cases: multiple edge services, monolith-to-microservices migration

## Additional Resources

### Reference Files
- **`references/slo-design-guide.md`** — Detailed SLO design methodology, multi-service SLOs, error budget math
- **`references/trigger-examples.md`** — Complete trigger example library organized by use case
- **`references/alerting-strategy.md`** — How to combine SLO burn alerts and triggers into a cohesive alerting strategy

### Cross-References
- For constructing SLI queries and calculated fields, see the **query-patterns** skill
- For investigating SLO budget burn, see the **production-investigation** skill
