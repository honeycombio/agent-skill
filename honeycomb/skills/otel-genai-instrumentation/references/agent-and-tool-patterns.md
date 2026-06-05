# Agent and Tool Trace Patterns

Trace structures for common GenAI agent architectures. These diagrams show how spans
compose to create observable agent systems.

## Tool-Calling Loop

The most common pattern: model requests tool calls, results feed back into the next
inference.

```
invoke_agent research-agent          (CLIENT, root)
├── chat gpt-4                       (CLIENT, inference #1)
├── execute_tool search_web          (INTERNAL)
├── chat gpt-4                       (CLIENT, inference #2 with tool results)
├── execute_tool read_page           (INTERNAL)
├── chat gpt-4                       (CLIENT, inference #3 with tool results)
└── [final response — no more tool calls]
```

Key attributes on `invoke_agent`:
- `gen_ai.agent.name`: `"research-agent"`
- `gen_ai.conversation.id`: ties together multi-turn context
- `gen_ai.usage.input_tokens`: total across all child inferences
- `gen_ai.usage.output_tokens`: total across all child inferences

Key attributes on each `chat`:
- `gen_ai.request.model`, `gen_ai.response.finish_reasons`
- `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` per call

Key attributes on each `execute_tool`:
- `gen_ai.tool.name`, `gen_ai.tool.call.id`
- `gen_ai.agent.name`, `gen_ai.conversation.id` (correlate tool with parent agent)
- `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result` (opt-in)
- `error.type` on failure (exception class name or `"ToolExecutionError"` for error results)

**Detecting retry loops**: If `invoke_agent` has many `execute_tool` children with the
same `gen_ai.tool.name`, the model may be stuck. Query: GROUP BY `gen_ai.tool.name`,
COUNT, WHERE parent span is `invoke_agent` with high child count.

## Multi-Turn Conversation

Each user turn triggers a new `invoke_agent` or `chat` span. The
`gen_ai.conversation.id` ties turns together.

```
[Turn 1]
invoke_agent assistant                (CLIENT)
├── chat claude-sonnet-4-5-20250929              (CLIENT)
└── execute_tool calculator           (INTERNAL)

[Turn 2 — same conversation.id]
invoke_agent assistant                (CLIENT)
├── chat claude-sonnet-4-5-20250929              (CLIENT)
└── [direct response, no tools]

[Turn 3 — same conversation.id]
invoke_agent assistant                (CLIENT)
├── chat claude-sonnet-4-5-20250929              (CLIENT)
├── execute_tool search_db            (INTERNAL)
└── chat claude-sonnet-4-5-20250929              (CLIENT, with tool results)
```

Correlate across turns: GROUP BY `gen_ai.conversation.id` to see full conversation
cost, latency, and tool usage patterns.

## Nested Agents (Delegation)

An agent delegates sub-tasks to specialized agents. Parent `invoke_agent` contains
child `invoke_agent` spans.

```
invoke_agent orchestrator             (CLIENT, root)
├── chat gpt-4                        (CLIENT, decides to delegate)
├── invoke_agent researcher           (INTERNAL, sub-agent)
│   ├── chat gpt-4                    (CLIENT)
│   ├── execute_tool search_web       (INTERNAL)
│   └── chat gpt-4                    (CLIENT)
├── invoke_agent writer               (INTERNAL, sub-agent)
│   ├── chat gpt-4                    (CLIENT)
│   └── [generates content]
└── chat gpt-4                        (CLIENT, final synthesis)
```

**Detecting deadlocks**: If two `invoke_agent` spans at the same level have span links
to each other and one times out (`error.type=TimeoutError`), agents may be waiting on
each other. Check `gen_ai.output.messages` for circular delegation patterns.

## A2A (Agent-to-Agent) HTTP Context Propagation

When agents communicate over HTTP (e.g., the A2A protocol or any REST-based delegation),
you must propagate two things:

1. **Trace context** (traceparent/tracestate) via HTTP headers — connects spans into one trace
2. **conversation.id** via request payload — ensures all agents use the SAME conversation.id

**Common symptoms:**
- Missing trace propagation: `invoke_agent orchestrator` and `invoke_agent sub-agent` appear in separate traces
- Missing conversation.id propagation: each agent generates new conversation.id, breaking session analysis

### The Problem

Standard `fetch()` / `http.request()` calls do **not** automatically inject trace context.
OTel's `HttpInstrumentation` patches `http.request`/`http.get` but does **not** patch
the global `fetch()` in Node.js. On the server side, Express middleware doesn't
automatically extract trace context from incoming headers either.

### Client: Inject trace context and pass conversation.id

Use `propagation.inject()` to write `traceparent` into headers. Include conversation.id in the payload so the sub-agent uses the SAME conversation.id.

#### Node.js

```typescript
import { propagation, context } from "@opentelemetry/api";

const headers: Record<string, string> = { "Content-Type": "application/json" };
propagation.inject(context.active(), headers);

const response = await fetch(agentUrl, {
  method: "POST",
  headers,
  body: JSON.stringify({
    ...payload,
    conversation_id: conversationId,  // Pass to sub-agent
  }),
});
```

#### Python

```python
from opentelemetry import context
from opentelemetry.propagate import inject

headers = {"Content-Type": "application/json"}
inject(headers)

payload = {
    **payload,
    "conversation_id": conversation_id  # Pass to sub-agent
}
response = requests.post(agent_url, headers=headers, json=payload)
```

### Server: Extract context and use conversation.id from payload

Use `propagation.extract()` on incoming headers. Extract conversation.id from the payload and pass it to all operations — the sub-agent must use the SAME conversation.id, not generate a new one.

#### Node.js (Express)

```typescript
import { propagation, context } from "@opentelemetry/api";

app.post("/agents/:name/a2a", async (req, res) => {
  const extractedContext = propagation.extract(context.active(), req.headers);
  const conversationId = req.body.conversation_id;  // From payload

  const result = await context.with(extractedContext, () =>
    executor.execute(task, message, conversationId),  // Pass to operations
  );
  res.json(result);
});
```

#### Python (Flask / FastAPI)

```python
from opentelemetry import context as otel_context
from opentelemetry.propagate import extract

@app.post("/agents/{name}/a2a")
async def handle_task(request: Request):
    body = await request.json()
    conversation_id = body["conversation_id"]  # From payload

    ctx = extract(carrier=dict(request.headers))
    token = otel_context.attach(ctx)
    try:
        result = await executor.execute(task, message, conversation_id)  # Pass to operations
    finally:
        otel_context.detach(token)
    return result
```

### Result: Connected Trace with Shared Conversation ID

After propagation, the trace nests correctly and all spans share the same conversation.id:

```
invoke_agent orchestrator             (CLIENT, root, conversation.id=abc-123)
├── chat claude-sonnet-4-5-20250929              (CLIENT, conversation.id=abc-123)
├── execute_tool send_to_researcher   (INTERNAL, conversation.id=abc-123)
│   └── POST /agents/researcher/a2a  (CLIENT, headers: traceparent, body: conversation_id=abc-123)
│       └── invoke_agent researcher   (CLIENT, same trace, conversation.id=abc-123)
│           ├── chat claude-sonnet-4-5-20250929  (CLIENT, conversation.id=abc-123)
│           └── execute_tool search   (INTERNAL, conversation.id=abc-123)
├── execute_tool send_to_writer       (INTERNAL, conversation.id=abc-123)
│   └── POST /agents/writer/a2a      (CLIENT, headers: traceparent, body: conversation_id=abc-123)
│       └── invoke_agent writer       (CLIENT, same trace, conversation.id=abc-123)
│           └── chat claude-sonnet-4-5-20250929  (CLIENT, conversation.id=abc-123)
└── chat claude-sonnet-4-5-20250929              (CLIENT, conversation.id=abc-123)
```

### Checklist

- [ ] `@opentelemetry/api` imported on both client and server
- [ ] `propagation.inject()` called before every outgoing HTTP request to another agent
- [ ] `conversation.id` included in request payload (client-side)
- [ ] `propagation.extract()` + `context.with()` wraps handler on the receiving side
- [ ] `conversation.id` extracted from payload and passed to all operations (server-side)
- [ ] `W3CTraceContextPropagator` registered (NodeSDK does this by default)
- [ ] Verify in Honeycomb: sub-agent spans nest under orchestrator's trace with same conversation.id

## Workflow Pattern

Deterministic steps with GenAI calls at specific points.

```
invoke_workflow content-pipeline      (INTERNAL, root)
├── retrieval knowledge-base          (CLIENT, fetch context)
├── chat gpt-4                        (CLIENT, generate draft)
├── invoke_agent reviewer             (INTERNAL, quality check)
│   ├── chat gpt-4                    (CLIENT)
│   └── [evaluation result event]
└── chat gpt-4                        (CLIENT, final edit)
```

Workflows differ from agents: the orchestration is code-driven (deterministic), not
model-driven (stochastic). The `invoke_workflow` span is INTERNAL because the code
controls execution flow.

## RAG Pattern

Retrieval-Augmented Generation: retrieve context, then generate.

```
chat gpt-4                            (CLIENT, root — or invoke_agent)
├── retrieval product-docs            (CLIENT, vector search)
├── retrieval faq-database            (CLIENT, second data source)
└── [generation uses retrieved context]
```

Key attributes on `retrieval`:
- `gen_ai.data_source.id`: identifies which data source
- `server.address`, `server.port`: vector DB connection
- Custom: `gen_ai.retrieval.result_count` for number of chunks returned

## Parallel Tool Execution

Model requests multiple tools simultaneously.

```
invoke_agent assistant                (CLIENT)
├── chat gpt-4                        (CLIENT, requests 3 tools)
├── execute_tool get_weather          (INTERNAL, concurrent)
├── execute_tool get_stock_price      (INTERNAL, concurrent)
├── execute_tool get_news             (INTERNAL, concurrent)
└── chat gpt-4                        (CLIENT, with tool results)
```

All three `execute_tool` spans share the same parent (`invoke_agent`) and may overlap
in time. The trace waterfall shows them running in parallel.

## Agent with Evaluation

Agent output gets scored before returning to user.

```
invoke_agent qa-assistant             (CLIENT, root)
├── retrieval knowledge-base          (CLIENT)
├── chat gpt-4                        (CLIENT, generate answer)
├── gen_ai.evaluation.result          (EVENT on chat span)
│   name: "relevance"
│   score.value: 0.92
│   score.label: "pass"
└── [return answer if evaluation passes]
```

If evaluation fails, the agent may re-query or refine — creating additional child spans.
