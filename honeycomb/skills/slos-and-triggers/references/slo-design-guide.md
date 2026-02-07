# SLO Design Guide

## Error Budget Math

For a 99.9% SLO over a 30-day rolling window:
- **Error budget**: 0.1% of events can fail
- **In time terms**: ~43.2 minutes of complete outage (if outage = 100% failure)
- **In event terms**: If 1M requests/day, 1,000 failures/day are within budget

### Burn Rate
- **1.0**: Budget consumed evenly over the window (sustainable)
- **2.0**: Budget consumed at 2x rate (will exhaust in 15 days instead of 30)
- **10.0**: Budget consumed at 10x rate (will exhaust in 3 days)
- **720.0**: Budget consumed in 1 hour (critical)

### Burn Alert Configuration

**Exhaustion Time alerts** (recommended starting point):
| Exhaustion Time | Meaning | Notification |
|----------------|---------|--------------|
| 0 hours | Budget depleted | Escalation |
| 4 hours | Will exhaust in 4h | Page on-call |
| 72 hours | Will exhaust in 3 days | Slack notification |

**Budget Rate alerts** (for detecting slow burns):
| Window | Rate | Meaning |
|--------|------|---------|
| 1 hour | > 14.4 | Fast burn — 100% budget in ~1 hour |
| 6 hours | > 6 | Medium burn — budget in ~5 hours |
| 24 hours | > 3 | Slow burn — budget in ~10 days |

## Designing SLIs

### Good SLIs
- **Latency**: `LTE(duration_ms, <threshold>)` — Events faster than threshold
- **Availability**: `LTE(http.status_code, 499)` — Non-server-error responses
- **Correctness**: Business logic that validates expected outcomes

### SLI Design Rules
- SLI must be a per-event boolean (success or failure)
- Cannot use cross-event relationships
- Must be a calculated field (regular or environment-level)
- For multi-service SLOs: must be environment-level calculated field

### Choosing Thresholds
1. Measure current performance: `VISUALIZE P50(duration_ms), P99(duration_ms)`
2. Decide what users need (not what you can achieve)
3. Set SLI threshold between P90 and P99 (typical starting point)
4. Set SLO target to current achievement minus a small margin

## Multi-Service SLOs

### When to Use
- Multiple API gateways or edge services serving same users
- Monolith being split into microservices (share budget during migration)
- Critical path through multiple services

### Configuration
1. Create environment-level calculated field for the SLI
2. Select up to 10 datasets to include
3. Events from all datasets weighted equally
4. Single error budget shared across all included services

### Limitations
- SLI must classify each event independently
- Cannot correlate events across services
- All included datasets must have the fields used in the SLI calculated field

## Monitoring SLOs with MCP

Use `get_slos` to monitor SLO health:

**Regular checks**: `get_slos(environment_slug: "production")` for an overview table
- Status column shows: Normal, Triggered, or No Events
- Budget Remaining shows percentage left
- Burn Alerts shows if any alerts are firing

**Deep dive**: `get_slos(slo_id: "SLO-abc123")` for:
- Budget burndown graph (error budget consumption over time)
- Historical compliance graph (SLI success rate over time)
- Burn rate analysis with current rates
- Configured burn alerts and their status

**When budget is burning**: Switch to the production-investigation skill's
SLO Budget Burn playbook to identify contributing failures.
