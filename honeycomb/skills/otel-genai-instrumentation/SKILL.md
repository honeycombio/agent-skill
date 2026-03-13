---
name: otel-genai-instrumentation
description: >
  Guides instrumentation of GenAI/LLM applications with OpenTelemetry
  for Honeycomb, including content capture and agent failure detection.
  Trigger phrases: "instrument my GenAI app", "add tracing to LLM calls",
  "trace AI agent", "instrument OpenAI", "instrument Anthropic",
  "GenAI observability", "trace tool calling", "LLM token usage",
  "instrument embeddings", "trace MCP", "GenAI metrics",
  "instrument LangChain", "add GenAI spans", "capture prompts",
  "capture LLM responses", "enable GenAI content capture",
  "streaming tracing", "trace streaming responses",
  or any request about instrumenting GenAI/LLM applications.
metadata:
  version: "1.0.0"
  semconv_version: "v1.40.0"
---

# GenAI Instrumentation for Honeycomb

Instrumenting LLM and agent applications using OTel Semantic Conventions for GenAI
(currently v1.40.0, Development status). For base SDK setup, OTLP config, and collector
configuration, see the **otel-instrumentation** skill. For conceptual foundations, see
the **observability-fundamentals** skill.

**Important:** All `gen_ai.*` conventions require opt-in:
```bash
export OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental
```

For Honeycomb OTLP authentication setup (including the silent-rejection pitfall), see the **otel-instrumentation** skill.

## Auto-Instrumentation (Python and Node.js)

Python and Node.js have official OTel auto-instrumentation packages for GenAI providers.
Go, Java, etc. require manual instrumentation (section below).

### Python

| Package | Provider | Min SDK Version |
| :--- | :--- | :--- |
| `opentelemetry-instrumentation-openai-v2` | OpenAI | openai >= v1.26.0 |
| `opentelemetry-instrumentation-anthropic` | Anthropic | anthropic >= v0.16.0 |
| `opentelemetry-instrumentation-claude-agent-sdk` | Claude Agent SDK | claude-agent-sdk >= v0.1.14 |
| `opentelemetry-instrumentation-google-genai` | Google GenAI | google-genai >= v1.32.0 |
| `opentelemetry-instrumentation-vertexai` | Vertex AI | google-cloud-aiplatform >= v1.64 |
| `opentelemetry-instrumentation-langchain` | LangChain | langchain >= v0.3.21 |
| `opentelemetry-instrumentation-openai-agents-v2` | OpenAI Agents | openai-agents >= v0.3.3 |
| `opentelemetry-instrumentation-weaviate` | Weaviate | weaviate-client >= v3.0.0, < v5.0.0 |

Setup: `pip install <package>` + `Instrumentor().instrument()` or CLI
`opentelemetry-instrument`.

### Node.js

| Package | Provider | Min SDK Version |
| :--- | :--- | :--- |
| `@opentelemetry/instrumentation-openai` | OpenAI | openai >= 4.19.0 |
| `@opentelemetry/instrumentation-langchain` | LangChain | langchain >= 1.0.0 (not yet published to npm) |

Setup: `npm install <package>` + register via OTel Node SDK.

For per-provider install commands, upstream README links, and supported version
details, see
`${CLAUDE_PLUGIN_ROOT}/skills/otel-genai-instrumentation/references/auto-instrumentation-setup.md`.

## Manual Instrumentation

For languages without auto-instrumentation (Go, Java, etc.) or when
auto-instrumentation doesn't cover your needs.

Key patterns:
- Creating inference spans (`chat`, `text_completion`, `generate_content`)
- Creating embedding and retrieval spans
- Setting request attributes before the call, response/usage attributes after
- Error handling with `error.type` and span status

For code examples in Python, Node.js, and Go, see
`${CLAUDE_PLUGIN_ROOT}/skills/otel-genai-instrumentation/references/manual-instrumentation.md`.

## Span Flushing for GenAI Apps

**Critical for GenAI applications.** The `BatchSpanProcessor` buffers spans (default
5 s schedule delay). GenAI agent runs are long-lived but may exit before the batch
flushes — crash, Ctrl+C, short CLI invocations — causing **silent span loss**.

**Rule: force-flush after every top-level agent invocation.** Expose the span
processor and call `forceFlush()` without tearing down the SDK, so subsequent
invocations continue producing spans.

### Why `shutdown()` is wrong here

`sdk.shutdown()` tears down the entire pipeline — after shutdown, no new spans are
recorded. For apps that run multiple agent invocations (polling loops, HTTP servers,
CLI batch modes), you need spans to keep flowing. Use `forceFlush()` instead.

### Python

```python
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

span_processor = BatchSpanProcessor(exporter)
provider = TracerProvider()
provider.add_span_processor(span_processor)

async def flush_telemetry():
    """Flush pending spans without shutting down."""
    span_processor.force_flush()
```

### Node.js

```typescript
import { BatchSpanProcessor } from "@opentelemetry/sdk-trace-base";

let spanProcessor: BatchSpanProcessor | null = null;

export function initTelemetry(): void {
  // ... exporter setup ...
  spanProcessor = new BatchSpanProcessor(traceExporter);
  sdk = new NodeSDK({ spanProcessors: [spanProcessor], /* ... */ });
  sdk.start();
}

export async function flushTelemetry(): Promise<void> {
  if (spanProcessor) {
    await spanProcessor.forceFlush();
  }
}
```

### Go

```go
var spanProcessor *sdktrace.BatchSpanProcessor

func InitTelemetry() {
    spanProcessor = sdktrace.NewBatchSpanProcessor(exporter)
    // ... provider setup ...
}

func FlushTelemetry(ctx context.Context) error {
    return spanProcessor.ForceFlush(ctx)
}
```

### Where to call `flushTelemetry()`

- **After each agent invocation** — ensures the full trace (agent + chat + tool spans)
  is exported before moving to the next task
- **In polling/server loops** — flush after processing each request or ticket
- **Before `process.exit()`** — as a safety net alongside `shutdownTelemetry()`
- **NOT inside the agent loop** — flushing per-chat-turn adds latency; flush once at
  the outer boundary

Example integration:
```typescript
for (const ticket of tickets) {
  await triageIssue(ticket);   // produces invoke_agent + chat + tool spans
  await flushTelemetry();      // ensure spans are exported before next ticket
}
```

For complete code examples showing flush integration with tool-calling loops, see
`${CLAUDE_PLUGIN_ROOT}/skills/otel-genai-instrumentation/references/manual-instrumentation.md`.

## GenAI Span Types

**Span names MUST follow the pattern `"{operation} {identifier}"`.** The `gen_ai.operation.name`
attribute and the span name prefix must match. For example, a span with
`gen_ai.operation.name = "invoke_agent"` must be named `"invoke_agent {agent_name}"`,
not `"mypackage.DoSomething"`.

| Operation | `gen_ai.operation.name` | SpanKind | Span Name |
| :--- | :--- | :--- | :--- |
| Chat/completion | `chat` | CLIENT | `chat {model}` |
| Text completion | `text_completion` | CLIENT | `text_completion {model}` |
| Content generation | `generate_content` | CLIENT | `generate_content {model}` |
| Embeddings | `embeddings` | CLIENT | `embeddings {model}` |
| RAG retrieval | `retrieval` | CLIENT | `retrieval {data_source}` |
| Tool execution | `execute_tool` | INTERNAL | `execute_tool {tool_name}` |
| Agent creation | `create_agent` | CLIENT | `create_agent {agent_name}` |
| Agent invocation | `invoke_agent` | CLIENT/INTERNAL | `invoke_agent {agent_name}` |
| Workflow step | `invoke_workflow` | INTERNAL | `invoke_workflow {workflow_name}` |

For trace structures showing how these spans compose (tool-calling loops, multi-turn
conversations, nested agents, workflows), see
`${CLAUDE_PLUGIN_ROOT}/skills/otel-genai-instrumentation/references/agent-and-tool-patterns.md`.

**A2A / HTTP-based agent delegation:** When agents communicate over HTTP (A2A protocol,
REST delegation), `fetch()` does NOT auto-inject trace context — sub-agent spans appear
as disconnected root traces. Fix: manually call `propagation.inject()` on the client and
`propagation.extract()` + `context.with()` on the server. See the "A2A (Agent-to-Agent)
HTTP Context Propagation" section in the reference file above.

## Required Telemetry by Failure Mode

Core Honeycomb section. For each failure mode, **all listed telemetry is required** —
including opt-in content capture fields.

### Tool Call Failures

- **Span** `execute_tool`: `gen_ai.tool.name`, `gen_ai.tool.call.id`,
  `gen_ai.agent.name`, `gen_ai.conversation.id`, `error.type`,
  `status.code=ERROR`, duration
- **Metric**: `gen_ai.client.operation.duration`
- **Enable**: `gen_ai.input.messages` (tool_call + tool_call_response parts) — shows
  arguments sent and error received

### Network Failures During Retrieval

- **Span** `retrieval`: `gen_ai.data_source.id`, `server.address`, `server.port`,
  `error.type`, `status.code=ERROR`, duration
- **Metric**: `gen_ai.client.operation.duration`

### Long Time-to-First-Token

- **Span** `chat`: `gen_ai.request.model`, `gen_ai.usage.input_tokens`,
  `server.address`, duration
- **Metrics**: `gen_ai.client.operation.time_to_first_chunk` (hosted APIs) or
  `gen_ai.server.time_to_first_token` (self-hosted)
- Also: `gen_ai.server.time_per_output_token`, `gen_ai.agent.name`

### Excessive Planning / Retry Loops

- **Parent** `invoke_agent`: `gen_ai.agent.name`, `gen_ai.usage.input_tokens`, duration
- **Children** `execute_tool`: `gen_ai.tool.name` + `gen_ai.tool.call.arguments` +
  `gen_ai.tool.call.result`
- **Metric**: `gen_ai.client.token.usage`
- **Enable**: `gen_ai.output.messages` — model reasoning reveals loop cause

### Slow Retrieval

- **Span** `retrieval`: `gen_ai.data_source.id`, `server.address`, `server.port`,
  `status.code=OK`, duration
- **Metric**: `gen_ai.client.operation.duration`

### Agent Deadlocks

- **Span** `invoke_agent`: `gen_ai.agent.name`, `gen_ai.agent.id`,
  `gen_ai.conversation.id`, `error.type=TimeoutError`, span links, duration
- **Metric**: `gen_ai.client.operation.duration`
- **Enable**: `gen_ai.output.messages` (tool_call parts) — reveals circular delegation

## Enabling Content Capture

**Not optional** — required for failure modes: tool call failures, excessive planning,
agent deadlocks.

**Always add `gen_ai.input.messages` and `gen_ai.output.messages` on chat spans.**
These attributes provide visibility into the full conversation — what the user sent,
what the model returned, and how tool results were fed back. Without them, you can see
that a chat span happened but not *why* the model made a particular decision.

### Auto-instrumentation (Python)

```bash
export OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true
```

Enables: `gen_ai.input.messages`, `gen_ai.output.messages`,
`gen_ai.system_instructions`, `gen_ai.tool.definitions`.

### Manual instrumentation (any language)

On every `chat` span:
- **Before the call**: set `gen_ai.input.messages` — the messages array sent to the model
- **After the call**: set `gen_ai.output.messages` — the model's response content

On every `execute_tool` span:
- Set `gen_ai.tool.call.arguments` / `gen_ai.tool.call.result`

Message JSON schema: `role` + `parts` (text, tool_call, tool_call_response, reasoning);
`tool_call_response` uses `response` field (not `content`) for the tool result.

### Privacy controls

- **Filtering**: select which messages to capture
- **Truncation**: limit content size
- **Hooks**: route to separate access-controlled storage
- **Recommendation**: enable everywhere with filtering; full content in non-prod,
  filtered in prod

For complete setup including message JSON schemas, per-provider examples, and privacy
patterns, see
`${CLAUDE_PLUGIN_ROOT}/skills/otel-genai-instrumentation/references/content-capture-setup.md`.

## Streaming Instrumentation

Streaming (SSE, chunked responses) requires dedicated metrics and span patterns.

Key metrics:
- `gen_ai.client.operation.time_to_first_chunk` — client-observed time until first
  streamed chunk (includes network latency); use for hosted APIs
- `gen_ai.server.time_to_first_token` — server-side TTFT (queue + prefill); use for
  self-hosted (vLLM, TGI)
- `gen_ai.server.time_per_output_token` — decode speed after first token
- `gen_ai.client.operation.time_per_output_chunk` — client-observed inter-chunk time

The span covers the full stream lifetime. Set usage attributes after stream completes.
Handle mid-stream errors by recording the error and setting span status before closing.

For streaming span lifecycle, code examples, and error handling patterns, see
`${CLAUDE_PLUGIN_ROOT}/skills/otel-genai-instrumentation/references/streaming-instrumentation.md`.

## Evaluation Events

`gen_ai.evaluation.result` event captures scoring/evaluation of GenAI output.

| Attribute | Requirement | Description |
| :--- | :--- | :--- |
| `gen_ai.evaluation.name` | Required | Evaluation name (e.g., "relevance", "faithfulness") |
| `gen_ai.evaluation.score.value` | Recommended | Numeric score |
| `gen_ai.evaluation.score.label` | Recommended | Categorical label (e.g., "pass", "fail") |
| `gen_ai.evaluation.explanation` | Recommended | Why this score was given |
| `gen_ai.response.id` | Recommended | Links evaluation to the inference it scored |

Use cases: RAG relevance scoring, hallucination detection, output quality gates.

## Metrics

| Metric | Type | Unit | Purpose |
| :--- | :--- | :--- | :--- |
| `gen_ai.client.operation.duration` | Histogram | s | End-to-end latency |
| `gen_ai.client.token.usage` | Histogram | {token} | Input/output token counts |
| `gen_ai.client.operation.time_to_first_chunk` | Histogram | s | Streaming TTFC |
| `gen_ai.client.operation.time_per_output_chunk` | Histogram | s | Streaming inter-chunk |
| `gen_ai.server.request.duration` | Histogram | s | Server-side latency |
| `gen_ai.server.time_to_first_token` | Histogram | s | Server TTFT |
| `gen_ai.server.time_per_output_token` | Histogram | s | Server decode speed |
| `mcp.client.operation.duration` | Histogram | s | MCP client latency |
| `mcp.server.operation.duration` | Histogram | s | MCP server latency |

For the required `x-honeycomb-dataset` metrics header, see the **otel-instrumentation** skill.

## MCP Instrumentation

Model Context Protocol instrumentation uses OTel context propagation via
`params._meta` (W3C traceparent/tracestate).

- Client spans (CLIENT) for MCP calls, server spans (SERVER) for MCP handlers
- Key attributes: `mcp.method.name`, `mcp.session.id`, `mcp.protocol.version`
- Metrics: `mcp.client.operation.duration`, `mcp.server.operation.duration`

For context propagation details, well-known method names, and code examples, see
`${CLAUDE_PLUGIN_ROOT}/skills/otel-genai-instrumentation/references/mcp-instrumentation.md`.

## Known Gaps & Workarounds

| Gap | Workaround |
| :--- | :--- |
| No retry/loop count attribute | Count child spans or diff `tool.call.arguments` across siblings |
| No inter-agent dependency (in-process) | Span links + `gen_ai.conversation.id` |
| No inter-agent dependency (HTTP/A2A) | Manual `propagation.inject()` / `extract()` — see agent-and-tool-patterns ref |
| No retrieval sub-metrics | Custom attributes on retrieval spans |
| `error.type` is only error signal | Custom attributes for severity/category |

## Provider-Specific Notes

- **Anthropic**: cache token accounting, `gen_ai.provider.name = "anthropic"`
- **OpenAI**: `system_fingerprint`, service tier, `gen_ai.provider.name = "openai"`
- **AWS Bedrock**: `aws.bedrock.guardrail.id`, knowledge base attributes
- **Azure AI**: `azure.resource_provider.namespace`

## Additional Resources

### Reference Files
- **`${CLAUDE_PLUGIN_ROOT}/skills/otel-genai-instrumentation/references/auto-instrumentation-setup.md`** — Python + Node.js: per-provider install, upstream README links, supported versions
- **`${CLAUDE_PLUGIN_ROOT}/skills/otel-genai-instrumentation/references/manual-instrumentation.md`** — Code examples in Python/Node.js/Go for all span types
- **`${CLAUDE_PLUGIN_ROOT}/skills/otel-genai-instrumentation/references/genai-attributes-catalog.md`** — Upstream semconv links + message JSON schema gotchas
- **`${CLAUDE_PLUGIN_ROOT}/skills/otel-genai-instrumentation/references/agent-and-tool-patterns.md`** — Trace diagrams: tool-calling loop, multi-turn, nested agents, workflow
- **`${CLAUDE_PLUGIN_ROOT}/skills/otel-genai-instrumentation/references/mcp-instrumentation.md`** — MCP context propagation, span conventions, method names, metrics
- **`${CLAUDE_PLUGIN_ROOT}/skills/otel-genai-instrumentation/references/streaming-instrumentation.md`** — Streaming span lifecycle, TTFT/TTFC metrics, mid-stream errors, code examples
- **`${CLAUDE_PLUGIN_ROOT}/skills/otel-genai-instrumentation/references/content-capture-setup.md`** — Env var + manual setup, message JSON schemas, privacy controls

### Cross-References
- For base SDK setup, OTLP config, collector, and sampling: **otel-instrumentation** skill
- For conceptual foundations of wide events and high cardinality: **observability-fundamentals** skill
- After instrumenting, use the **query-patterns** skill to verify GenAI data in Honeycomb
