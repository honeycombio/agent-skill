# MCP Instrumentation

Instrumenting Model Context Protocol (MCP) clients and servers using OTel semantic
conventions.

## Context Propagation

MCP propagates trace context via `params._meta` using W3C format:

```json
{
  "method": "tools/call",
  "params": {
    "name": "get_weather",
    "arguments": {"city": "NYC"},
    "_meta": {
      "traceparent": "00-abcdef1234567890abcdef1234567890-1234567890abcdef-01",
      "tracestate": "honeycomb=abc123"
    }
  }
}
```

This links client and server spans into a single distributed trace.

## Client Spans

MCP clients create CLIENT spans for each method call.

### Python

```python
from opentelemetry import trace, context
from opentelemetry.trace import SpanKind
from opentelemetry.trace.propagation import get_current_span

tracer = trace.get_tracer("mcp-client")

async def call_tool(session, tool_name, arguments):
    with tracer.start_as_current_span(
        f"tools/call",
        kind=SpanKind.CLIENT,
        attributes={
            "mcp.method.name": "tools/call",
            "mcp.session.id": session.id,
            "mcp.protocol.version": "2025-03-26",
            "mcp.tool.name": tool_name,
            "server.address": session.server_address,
        },
    ) as span:
        # Inject trace context into _meta
        meta = {}
        propagator = trace.get_tracer_provider()
        # Use W3C propagator to inject traceparent
        from opentelemetry.propagators import inject
        inject(meta)

        result = await session.call_tool(
            tool_name, arguments, _meta=meta
        )
        return result
```

### Node.js

```javascript
const { trace, SpanKind, propagation } = require("@opentelemetry/api");

const tracer = trace.getTracer("mcp-client");

async function callTool(session, toolName, args) {
  return tracer.startActiveSpan(
    "tools/call",
    {
      kind: SpanKind.CLIENT,
      attributes: {
        "mcp.method.name": "tools/call",
        "mcp.session.id": session.id,
        "mcp.protocol.version": "2025-03-26",
        "mcp.tool.name": toolName,
        "server.address": session.serverAddress,
      },
    },
    async (span) => {
      try {
        // Inject trace context
        const meta = {};
        propagation.inject(trace.context.active(), meta);

        const result = await session.callTool(toolName, args, { _meta: meta });
        return result;
      } finally {
        span.end();
      }
    }
  );
}
```

## Server Spans

MCP servers create SERVER spans for incoming requests, extracting context from
`params._meta`.

### Python

```python
from opentelemetry import trace, context
from opentelemetry.trace import SpanKind
from opentelemetry.propagators import extract

tracer = trace.get_tracer("mcp-server")

async def handle_tool_call(request):
    # Extract trace context from _meta
    meta = request.params.get("_meta", {})
    ctx = extract(meta)

    with tracer.start_as_current_span(
        "tools/call",
        context=ctx,
        kind=SpanKind.SERVER,
        attributes={
            "mcp.method.name": "tools/call",
            "mcp.session.id": request.session_id,
            "mcp.protocol.version": "2025-03-26",
            "mcp.tool.name": request.params["name"],
        },
    ) as span:
        result = await execute_tool(request.params["name"], request.params["arguments"])
        return result
```

## Span Attributes

| Attribute | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `mcp.method.name` | string | MCP method | `"tools/call"` |
| `mcp.session.id` | string | Session identifier | `"sess-abc-123"` |
| `mcp.protocol.version` | string | MCP protocol version | `"2025-03-26"` |
| `mcp.tool.name` | string | Tool being called | `"get_weather"` |
| `mcp.resource.uri` | string | Resource URI | `"file:///data.json"` |
| `mcp.prompt.name` | string | Prompt template name | `"summarize"` |
| `server.address` | string | Server hostname | `"localhost"` |
| `server.port` | int | Server port | `3000` |

## Well-Known Method Names

| Method | Direction | Description |
| :--- | :--- | :--- |
| `initialize` | Client → Server | Session initialization |
| `tools/list` | Client → Server | List available tools |
| `tools/call` | Client → Server | Execute a tool |
| `resources/list` | Client → Server | List available resources |
| `resources/read` | Client → Server | Read a resource |
| `prompts/list` | Client → Server | List available prompts |
| `prompts/get` | Client → Server | Get a prompt template |
| `notifications/tools/list_changed` | Server → Client | Tools changed notification |
| `notifications/resources/list_changed` | Server → Client | Resources changed notification |

## Metrics

| Metric | Type | Unit | Description |
| :--- | :--- | :--- | :--- |
| `mcp.client.operation.duration` | Histogram | s | Client-observed latency per method |
| `mcp.server.operation.duration` | Histogram | s | Server-side processing time per method |

## Integration with GenAI Spans

MCP tool calls typically appear as children of `execute_tool` spans in GenAI traces:

```
invoke_agent assistant                (CLIENT)
├── chat claude-sonnet-4-5-20250929              (CLIENT)
├── execute_tool get_data             (INTERNAL, GenAI layer)
│   └── tools/call                    (CLIENT, MCP layer)
│       └── tools/call                (SERVER, MCP server)
│           └── [actual tool work]
└── chat claude-sonnet-4-5-20250929              (CLIENT, with tool results)
```

The `execute_tool` span captures GenAI-level semantics (tool name, call ID, arguments),
while the nested MCP spans capture transport-level semantics (session, protocol version,
server address).
