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

Guide to configuring and monitoring reliability in Honeycomb. Covers SLOs
(error budgets, burn rates, burn alerts) and Triggers (threshold-based alerts).

**Availability**: SLOs require Pro or Enterprise plan. Triggers available on all plans.

## MCP Tools for Reliability Monitoring

- **`get_slos`** — List all SLOs (with status, compliance, budget remaining) or get detailed view of a single SLO (with burn rate analysis, budget burndown graph, historical compliance graph, and burn alerts)
- **`get_triggers`** — List all triggers (with status) or get detailed view of a single trigger
- **`run_query`** — Build and test SLI queries, check threshold-based conditions
- **`get_workspace_context`** — Discover environments and datasets
- **`find_columns`** — Discover fields available for SLI calculations
- **`create_board`** — Create a Board to track SLOs and key queries together

### Checking SLO Status

**List all SLOs** (optionally filter by environment or tags):
```
get_slos(environment_slug: "production")
```
Returns a table with: Name, Target, Time Period, Status (Normal/Triggered/No Events), Compliance %, Budget Remaining %, Burn Alerts status, Tags.

**Get detailed SLO view**:
```
get_slos(slo_id: "SLO-abc123")
```
Returns: configuration, current status with explanation, budget burndown graph, historical compliance graph, burn rate analysis, and configured burn alerts.

**Filter by tags**:
```
get_slos(tags: ["team:platform", "tier:critical"])
```

### Checking Trigger Status

**List all triggers** (optionally filter by environment or tags):
```
get_triggers(environment_slug: "production")
```

**Get detailed trigger view**:
```
get_triggers(trigger_id: "TRIG-abc123")
```

## Core Concepts

### SLO Components
- **SLI (Service Level Indicator)**: Per-event boolean — was this event successful? Defined as a calculated field returning 1 (success) or 0 (failure).
- **SLO**: Target percentage of successful SLIs over a rolling time window (e.g., "99.9% successful over 30 days").
- **Error Budget**: The allowed failure rate. A 99.9% SLO over 30 days allows ~43 minutes of downtime.
- **Burn Rate**: How fast the error budget is being consumed. 1.0 = even burn. >1.0 = consuming faster than planned.
- **Burn Alert**: Fires when error budget is consumed at an unsustainable rate.

### SLO vs Trigger — When to Use Which

| Use Case | SLO | Trigger |
|----------|-----|---------|
| Track reliability over time | Yes | No |
| Alert on budget consumption speed | Yes (burn alerts) | No |
| Alert on immediate threshold crossing | No | Yes |
| Real-time error spike notification | No | Yes |
| Measure customer experience | Yes | Sometimes |
| Monitor infrastructure metrics | No | Yes |

**Rule of thumb**: SLOs measure reliability against commitments. Triggers catch immediate operational issues.

## Designing Effective SLOs

### Step 1: Define the SLI
Create a calculated field that returns success (1) or failure (0):

**Latency SLI** (requests faster than threshold):
```
Calculated field: "is_fast" = LTE(duration_ms, 500)
```

**Availability SLI** (non-error responses):
```
Calculated field: "is_successful" = LTE(http.status_code, 499)
```

**Custom SLI** (business logic success):
```
Calculated field: "checkout_success" = IF(EQUALS(checkout.status, "completed"), 1, 0)
```

### Step 2: Set the Target
- Start conservative (e.g., 99% rather than 99.99%)
- Measure current baseline first: `VISUALIZE P50(duration_ms), P99(duration_ms)`
- Set target slightly above current performance
- Consider: What reliability do users actually need?

### Step 3: Configure Burn Alerts
Create at least two alerts:
- **Fast burn**: Exhaustion time = 4 hours -> pages on-call (PagerDuty)
- **Slow burn**: Budget rate over 24h window -> notifies team (Slack)
- **Budget depleted**: Exhaustion time = 0 -> escalation

### Best Practices
- Measure close to the user (at the edge, not deep in the stack)
- Design around user workflows, not team boundaries
- Favor broad SLOs over many narrow ones
- Iterate: start with one SLO, reduce noise, then add more
- Document exceptions and known issues in SLO description

## Multi-Service SLOs
Share a single error budget across up to 10 services.
- SLI must be an environment-level calculated field
- Events from included services are weighted equally
- Use cases: multiple edge services, monolith-to-microservices migration

For detailed multi-service SLO configuration, consult `references/slo-design-guide.md`.

## Configuring Triggers

### Trigger Components
- **Query**: What to evaluate (VISUALIZE + WHERE + GROUP BY)
- **Threshold**: Value that triggers the alert (above or below)
- **Duration**: Time window of data evaluated (e.g., last 5 minutes)
- **Frequency**: How often the trigger runs (e.g., every 2 minutes)
- **Notification**: Where to send (PagerDuty, Slack, Teams, webhook, email)

### Common Trigger Patterns

**Error rate spike:**
```
VISUALIZE COUNT WHERE error = true AND is_root
Threshold: > 100 in 5 minutes
```

**Latency degradation (count-based, recommended):**
```
VISUALIZE COUNT WHERE duration_ms > 2000 AND is_root
Threshold: > 50 in 5 minutes
```

**Why count-based over P99**: "50 slow requests" is more actionable than "P99 is 2100ms."

For a complete trigger library, consult `references/trigger-examples.md`.

### Trigger Best Practices
- **Name**: What the alert is. **Description**: What to do about it (link to runbook).
- For latency: Use `COUNT WHERE duration_ms > threshold` instead of P99
- For errors: Allow known-good values rather than looking for bad ones
- Set duration long enough to avoid flapping (5-10 min minimum)
- Start with less-sensitive thresholds, tighten based on false positive rate

## Notification Methods
- **PagerDuty**: For urgent, on-call alerting
- **Slack**: For team awareness and non-urgent alerts
- **Microsoft Teams**: Alternative to Slack
- **Webhooks**: For custom integrations
- **Email**: For low-urgency or summary alerts

All notifications include a direct link to the triggering graph in Honeycomb.

## Additional Resources

### Reference Files
- **`references/slo-design-guide.md`** — Detailed SLO design methodology, multi-service SLOs, error budget math
- **`references/trigger-examples.md`** — Complete trigger example library organized by use case
- **`references/alerting-strategy.md`** — How to combine SLO burn alerts and triggers into a cohesive alerting strategy

### Cross-References
- For constructing SLI queries and calculated fields, see the **query-patterns** skill
- For investigating SLO budget burn, see the **production-investigation** skill
