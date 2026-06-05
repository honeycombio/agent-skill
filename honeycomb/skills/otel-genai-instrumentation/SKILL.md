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
(currently v1.40.0, Development status). For conceptual foundations, see
the **observability-fundamentals** skill.

## Base OTEL Setup (Required First)

**BEFORE implementing GenAI instrumentation, ensure your base OpenTelemetry configuration is complete.**

Use the **otel-instrumentation** skill to configure all standard OTEL environment variables
(OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_EXPORTER_OTLP_HEADERS, OTEL_EXPORTER_OTLP_PROTOCOL,
signal-specific endpoints, etc.) and verify basic spans are flowing to Honeycomb.

GenAI instrumentation adds GenAI-specific configuration on top of that base setup.

## Critical Requirements (Non-Negotiable)

**BEFORE implementing any GenAI instrumentation, complete these steps in order:**

### Step 1: Ask About Content Capture (FIRST!)

**Stop and ask the user this question BEFORE writing any code or configuration:**

> "Do you want to capture the actual prompts and model responses in your traces?
>
> **Enabling content capture:**
> - ✅ Helps debug tool call failures, planning loops, and agent deadlocks
> - ✅ Lets you see why the model made specific decisions
> - ❌ Captures potentially sensitive content (user prompts, model responses)
> - ❌ May contain PII, proprietary data, or confidential information
>
> **Recommended for:** debugging/development, non-sensitive data, or if you have filtering
>
> **Not recommended for:** production with sensitive data, PII/health/financial info"

**Record their answer** — you'll need it when configuring instrumentation.

### Step 2: Enable GenAI Conventions (REQUIRED)

```bash
export OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental
```

Without this, GenAI spans will not be created.

### Step 3: Set Required Attributes on EVERY Span (REQUIRED)

- `gen_ai.operation.name` — e.g., `chat`, `execute_tool`, `invoke_agent`
- `gen_ai.conversation.id` — same value for all spans in a conversation

**Impact if missing**: Spans won't be recognized as GenAI operations and cannot be queried by session.

### Step 4: Implement force_flush() (REQUIRED)

GenAI apps often exit early (crash, Ctrl+C, CLI). Force flush after each top-level invocation
to prevent silent span loss.

For OTLP configuration, environment variables, and Honeycomb authentication (including the
silent-rejection pitfall), see the **otel-instrumentation** skill.

## Prerequisites

**This skill assumes your agent application is already sending telemetry to Honeycomb.** You should have:
- OpenTelemetry SDK installed and initialized
- All standard OTEL environment variables configured (see **Base OTEL Setup** section above)
- OTLP exporter configured with your Honeycomb API key
- Basic spans flowing to Honeycomb

**If you haven't set this up yet, use the otel-instrumentation skill first** for:
- SDK setup and dependencies
- OTEL environment variables (OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_*, etc.)
- OTLP configuration and Honeycomb authentication
- Verification that spans are flowing

Once base telemetry is working, return here to add GenAI-specific instrumentation.

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

### Required Attributes on All GenAI Spans

**CRITICAL: Every GenAI span MUST include these two attributes. This is non-negotiable.**

1. **`gen_ai.operation.name`** — Identifies the operation type (`chat`, `embeddings`, `execute_tool`, `invoke_agent`, etc.).
   - **Without this**: The span is not recognized as a GenAI operation and will be excluded from GenAI-specific queries and visualizations in Honeycomb
   - **Set on EVERY span**: chat, execute_tool, invoke_agent, embeddings, retrieval, etc.

2. **`gen_ai.conversation.id`** — Ties operations together within a conversation or session.
   - **Without this**: Spans cannot be queried as part of a multi-operation workflow, breaking session-level analysis
   - **Use the SAME value** across all operations in a conversation thread (user request → agent invocation → chat calls → tool executions → responses)
   - Generate once at the start of a conversation, propagate to all operations

**When to set:** When creating the span (in the span attributes), not after.

**How to propagate conversation_id:**
- In-process: Pass as parameter or store in context
- HTTP/A2A: Include in request payload or propagate via headers

**Impact of missing these attributes:**
- Missing `gen_ai.operation.name` → Span not recognized as GenAI operation, excluded from GenAI-specific queries and visualizations
- Missing `gen_ai.conversation.id` → Span excluded from session queries, cannot correlate operations within a conversation, breaks multi-turn analysis

**What is a conversation?**

A conversation is a **customer session or user interaction**, NOT a single LLM call. One conversation contains:
- Multiple user turns/messages
- All LLM calls handling those turns
- All tool executions triggered by those LLM calls
- All agent invocations within that session

See the [OTel GenAI spec](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/#conversation-id) for the definition. Key principle: use the same conversation.id when conversation history/context is maintained across operations.

**When to use the same conversation_id:**
- All operations within a single customer session
- All turns in a multi-turn interaction
- All LLM calls handling those turns
- All tool executions and agent invocations within that session
- Multiple agents participating in the same session

**Example:** User starts a support session. Over the next 10 minutes they send 5 messages. The assistant makes 15 LLM calls and executes 8 tools to handle those messages. ALL of these spans share the SAME conversation.id because they're part of one customer session.

**Common mistake:** Generating a new conversation_id for each LLM call. This breaks session-level analysis. Generate conversation_id ONCE at session start, reuse for all operations until session ends.

For trace structures showing how these spans compose (tool-calling loops, multi-turn
conversations, nested agents, workflows), see
`${CLAUDE_PLUGIN_ROOT}/skills/otel-genai-instrumentation/references/agent-and-tool-patterns.md`.

**A2A / HTTP-based agent delegation:** When agents communicate over HTTP (A2A protocol,
REST delegation), manually propagate both trace context (via headers) AND conversation.id
(via payload). Client: `propagation.inject()` + include conversation.id in request body.
Server: `propagation.extract()` + `context.with()` + extract conversation.id from payload
and pass to all operations. See the "A2A (Agent-to-Agent) HTTP Context Propagation"
section in the reference file above.

## Generating and Propagating Conversation ID

Generate conversation_id at your application's **session boundary**:
- Chat apps: when user opens new chat/thread
- Support systems: when customer starts session
- CLI tools: at command invocation
- HTTP APIs: when session/conversation is created
- Bots: when user starts thread/DM

Pass the SAME conversation_id to all operations within that session — all user turns, all LLM calls handling those turns, all tool executions, all agent invocations.

**Propagation methods:**
- In-process: store in session object, pass as parameter
- HTTP/microservices: include in request payload or header (`X-Conversation-ID`)
- Bots: store in state (Redis, DB), retrieve using thread/DM ID

## Attribute Completeness

**Set all attributes for which you have data available.** The OTel GenAI semantic conventions define comprehensive attributes for each operation type — if your application has the data (model name, tokens, tool arguments, etc.), set the corresponding attribute.

**Critical principle**: Don't selectively omit attributes. Incomplete instrumentation limits your ability to:
- Identify which models and agents were involved in a trace
- Track token usage and costs across operations
- Debug tool call failures (missing arguments/results)
- Understand conversation flow (missing messages)
- Correlate agent behavior with configuration (missing request parameters)

For the full attribute definitions by operation type, see the upstream semantic conventions:
- Model operations (chat, embeddings): https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/
- Agent operations (invoke_agent, execute_tool): https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/
- Local reference: `${CLAUDE_PLUGIN_ROOT}/skills/otel-genai-instrumentation/references/genai-attributes-catalog.md`

**What "data available" means**:
- API response fields → set corresponding response attributes (model, tokens, finish_reasons, response_id)
- Request parameters → set request attributes (temperature, max_tokens, top_p, etc.)
- Agent metadata → set agent attributes (name, id, description, version)
- Tool execution → set tool attributes (name, call_id, arguments, result)
- Conversation context → set conversation_id on ALL GenAI spans (required, not optional) — use the same ID across all operations in a conversation thread

The code examples in this skill show core attributes for each operation type. For complete coverage, consult the upstream spec and instrument every attribute your application can populate.

**Impact of incomplete instrumentation**:

- Missing `gen_ai.operation.name` → span not recognized as GenAI operation, excluded from GenAI queries
- Missing `gen_ai.conversation.id` → span excluded from session queries, cannot correlate operations within a conversation
- Missing `gen_ai.request.model` / `gen_ai.response.model` → can't identify which model was used
- Missing `gen_ai.usage.*` tokens → can't track costs or identify expensive operations
- Missing `gen_ai.tool.call.arguments` / `gen_ai.tool.call.result` → can't debug why tools failed or returned unexpected results
- Missing `gen_ai.input.messages` / `gen_ai.output.messages` → can't see what prompted a response, can't debug planning loops or hallucinations
- Missing agent attributes → can't distinguish between agents in multi-agent systems
- Missing request parameters → can't correlate behavior with temperature, top_p, etc.

**Best practice**: Instrument completely from the start. Adding attributes later requires code changes, redeployment, and waiting for new traces to arrive.

## Telemetry by Failure Mode

For each failure mode, the listed telemetry enables effective debugging. Items marked
**[Content Capture]** require enabling content capture — ask the user before enabling these.

### Tool Call Failures

- **Span** `execute_tool`: `gen_ai.tool.name`, `gen_ai.tool.call.id`,
  `gen_ai.agent.name`, `gen_ai.conversation.id`, `error.type`,
  `status.code=ERROR`, duration, `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result`
- **Metric**: `gen_ai.client.operation.duration`
- **[Content Capture]**: `gen_ai.input.messages` (tool_call + tool_call_response parts) —
  shows full context of tool calls (optional, requires user consent)

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
- **Children** `execute_tool`: `gen_ai.tool.name`, `gen_ai.tool.call.arguments`,
  `gen_ai.tool.call.result`
- **Metric**: `gen_ai.client.token.usage`
- **[Content Capture]**: `gen_ai.output.messages` — model reasoning reveals loop cause
  (optional but very helpful, requires user consent)

### Slow Retrieval

- **Span** `retrieval`: `gen_ai.data_source.id`, `server.address`, `server.port`,
  `status.code=OK`, duration
- **Metric**: `gen_ai.client.operation.duration`

### Agent Deadlocks

- **Span** `invoke_agent`: `gen_ai.agent.name`, `gen_ai.agent.id`,
  `gen_ai.conversation.id`, `error.type=TimeoutError`, span links, duration
- **Metric**: `gen_ai.client.operation.duration`
- **[Content Capture]**: `gen_ai.output.messages` (tool_call parts) — reveals circular
  delegation (optional but very helpful, requires user consent)

## Content Capture (Ask User First)

**CRITICAL: Do NOT enable content capture without asking the user first.**

### Step 1: Ask the User

Before providing any configuration, **ask this question**:

> "Do you want to capture the actual prompts and model responses in your traces?
>
> **Enabling content capture:**
> - ✅ Helps debug tool call failures, planning loops, and agent deadlocks
> - ✅ Lets you see why the model made specific decisions
> - ❌ Captures potentially sensitive content (user prompts, model responses)
> - ❌ May contain PII, proprietary data, or confidential information
>
> Recommended if: debugging/development, non-sensitive data, or you have filtering in place
>
> Not recommended if: production with sensitive data, PII/health/financial info, no filtering"

### Step 2: Configure Based on Answer

**If user says YES** to content capture:

For auto-instrumentation (Python), set the capture mode:

```bash
# Recommended for Honeycomb: Capture as span attributes (fully queryable)
export OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=span_only
```

**Why `span_only` for Honeycomb:**
- Content stored as span attributes → fully queryable in Honeycomb
- Can filter, group, and visualize by message content
- Lower overhead than `span_and_event`

**Alternative modes (less common):**
```bash
# Events only - for high-volume scenarios where you want content in logs but not queryable
export OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=event_only

# Both spans and events - most complete but higher overhead
export OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=span_and_event

# Legacy boolean - deprecated, use span_only instead
export OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true
```

**Mode comparison:**
- `span_only` → Content in span attributes (queryable, recommended for Honeycomb)
- `event_only` → Content in events (logging, not queryable)
- `span_and_event` → Both (most complete, 2x overhead)
- `true` → Legacy (maps to old behavior, deprecated)

For manual instrumentation:
- Set `gen_ai.input.messages` on chat spans (before the call)
- Set `gen_ai.output.messages` on chat spans (after the call)

**If user says NO** to content capture:

Do NOT set `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` (leave unset).

Do NOT include `gen_ai.input.messages` or `gen_ai.output.messages` in manual instrumentation.

**ALWAYS include regardless of content capture setting:**
- `gen_ai.tool.call.arguments` on execute_tool spans
- `gen_ai.tool.call.result` on execute_tool spans

Tool arguments/results are essential for debugging and are typically less sensitive than
full conversation content.

### What Content Capture Provides

When enabled, `gen_ai.input.messages` and `gen_ai.output.messages` show the full
conversation — what the user sent, what the model returned, and how tool results were
fed back. Without them, you can see that a chat span happened but not *why* the model
made a particular decision.

### Example: .env Configuration

**If user wants content capture:**
```bash
# .env

# Base OTEL setup - see otel-instrumentation skill for:
#   OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_ENDPOINT,
#   OTEL_EXPORTER_OTLP_HEADERS, OTEL_EXPORTER_OTLP_PROTOCOL, etc.

# GenAI-specific configuration (REQUIRED)
OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental

# Content capture (OPTIONAL - ask user first)
# Recommended for Honeycomb: span attributes (queryable)
OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=span_only

# Other content capture options (uncomment one if needed):
# OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=event_only  # Events only, not queryable
# OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=span_and_event  # Both (2x overhead)
# OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true  # Legacy (deprecated)
```

**If user does NOT want content capture:**
```bash
# .env

# Base OTEL setup - see otel-instrumentation skill for:
#   OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_ENDPOINT,
#   OTEL_EXPORTER_OTLP_HEADERS, OTEL_EXPORTER_OTLP_PROTOCOL, etc.

# GenAI-specific configuration (REQUIRED)
OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental
# OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT not set (disabled by default)
```

### What Gets Captured

**Content capture enabled** (span_only, event_only, or span_and_event):
- `gen_ai.input.messages` — Full prompts sent to model
- `gen_ai.output.messages` — Full model responses
- `gen_ai.system_instructions` — System prompts
- `gen_ai.tool.definitions` — Available tools

**Capture mode determines where content is stored:**
- `span_only` → Span attributes (queryable in Honeycomb, recommended)
- `event_only` → Event attributes (logging/archival, not queryable in Honeycomb)
- `span_and_event` → Both locations (most complete, double storage/overhead)
- `true` → Legacy mode (deprecated, use `span_only`)

**Content capture disabled** (default):
- Model name, tokens, finish_reasons, timing — YES (always captured)
- Prompt/response content — NO
- Tool arguments/results — YES (always recommended)

Message JSON schema: `role` + `parts` (text, tool_call, tool_call_response, reasoning);
`tool_call_response` uses `response` field (not `content`) for the tool result.

### Privacy Controls (If Content Capture Enabled)

If the user enables content capture, recommend these additional safeguards:

- **Filtering**: Capture selectively (e.g., exclude messages with PII)
- **Truncation**: Limit content size (e.g., first 500 chars only)
- **Hooks**: Route to separate access-controlled storage
- **Access control**: Restrict who can query message content in Honeycomb
- **Environment-based**: Full content in dev/test, disabled or filtered in prod

Example filtering pattern (Python):
```python
# Only capture if no PII detected
if not contains_pii(message_content):
    span.set_attribute("gen_ai.input.messages", json.dumps(messages))
```

Example truncation (any language):
```python
# Limit to first 500 characters
truncated = json.dumps(messages)[:500]
span.set_attribute("gen_ai.input.messages", truncated)
```

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
- **BEFORE using this skill**: Use **otel-instrumentation** for base SDK setup, all OTEL environment variables (OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_*, OTEL_EXPORTER_OTLP_HEADERS, etc.), OTLP config, collector, and sampling
- For conceptual foundations of wide events and high cardinality: **observability-fundamentals** skill
- After instrumenting, use the **query-patterns** skill to verify GenAI data in Honeycomb
