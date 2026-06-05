# Content Capture Setup

Enabling and controlling capture of GenAI message content — prompts, responses, tool
arguments, and tool results. Required for debugging tool call failures, excessive
planning loops, and agent deadlocks.

## Auto-Instrumentation (Python)

Set one environment variable before starting the application:

```bash
export OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true
```

This enables capture of:
- `gen_ai.input.messages` — user prompts, tool call arguments, tool results
- `gen_ai.output.messages` — model responses, tool call requests
- `gen_ai.system_instructions` — system prompts
- `gen_ai.tool.definitions` — tool schemas

Must be set **before** calling `Instrumentor().instrument()`.

## Manual Instrumentation

For languages without auto-instrumentation, or when you need fine-grained control.

### Setting Content on Inference Spans

```python
import json

with tracer.start_as_current_span("chat gpt-4", kind=SpanKind.CLIENT) as span:
    # Set input messages (opt-in)
    span.set_attribute("gen_ai.input.messages", json.dumps([
        {
            "role": "system",
            "parts": [{"type": "text", "text": "You are a helpful assistant."}]
        },
        {
            "role": "user",
            "parts": [{"type": "text", "text": "What's the weather in NYC?"}]
        }
    ]))

    response = client.chat.completions.create(model="gpt-4", messages=messages)

    # Set output messages (opt-in)
    span.set_attribute("gen_ai.output.messages", json.dumps([
        {
            "role": "assistant",
            "parts": [
                {
                    "type": "tool_call",
                    "id": "call_abc123",
                    "name": "get_weather",
                    "arguments": '{"city": "NYC"}'
                }
            ]
        }
    ]))
```

### Node.js

```javascript
span.setAttribute("gen_ai.input.messages", JSON.stringify([
  {
    role: "user",
    parts: [{ type: "text", text: "What's the weather in NYC?" }],
  },
]));

// After response
span.setAttribute("gen_ai.output.messages", JSON.stringify([
  {
    role: "assistant",
    parts: [{ type: "text", text: "It's 72°F in NYC." }],
  },
]));
```

### Go

```go
inputJSON, _ := json.Marshal([]Message{
    {Role: "user", Parts: []Part{{Type: "text", Text: "What's the weather?"}}},
})
span.SetAttributes(attribute.String("gen_ai.input.messages", string(inputJSON)))

// After response
outputJSON, _ := json.Marshal([]Message{
    {Role: "assistant", Parts: []Part{{Type: "text", Text: "It's 72°F."}}},
})
span.SetAttributes(attribute.String("gen_ai.output.messages", string(outputJSON)))
```

### Setting Content on Tool Spans

```python
with tracer.start_as_current_span("execute_tool get_weather") as span:
    span.set_attribute("gen_ai.tool.call.arguments", json.dumps({
        "city": "NYC"
    }))

    result = get_weather(city="NYC")

    span.set_attribute("gen_ai.tool.call.result", json.dumps(result))
```

## Message JSON Schema

All content attributes use a JSON array of message objects:

```json
[
  {
    "role": "system" | "user" | "assistant" | "tool",
    "parts": [
      {"type": "text", "text": "..."},
      {"type": "tool_call", "id": "call_123", "name": "fn_name", "arguments": "{}"},
      {"type": "tool_call_response", "id": "call_123", "response": "{}"},
      {"type": "reasoning", "text": "..."}
    ]
  }
]
```

### Part Types

| Type | Used In | Description |
| :--- | :--- | :--- |
| `text` | input/output | Plain text content |
| `tool_call` | output | Model requesting a tool call |
| `tool_call_response` | input | Tool result fed back to model |
| `reasoning` | output | Model's chain-of-thought (if exposed) |

### Tool Call Part Fields

```json
{
  "type": "tool_call",
  "id": "call_abc123",
  "name": "get_weather",
  "arguments": "{\"city\": \"NYC\"}"
}
```

### Tool Call Response Part Fields

```json
{
  "type": "tool_call_response",
  "id": "call_abc123",
  "response": "{\"temperature\": 72, \"unit\": \"F\"}"
}
```

## Privacy Controls

Content capture includes sensitive data (user prompts, model outputs). Apply these
controls based on environment.

### Filtering: Select Which Messages to Capture

```python
def filter_messages(messages):
    """Capture tool calls but redact user content."""
    filtered = []
    for msg in messages:
        if msg["role"] == "user":
            filtered.append({
                "role": "user",
                "parts": [{"type": "text", "text": "[REDACTED]"}]
            })
        else:
            filtered.append(msg)
    return filtered

# Use filtered content
span.set_attribute("gen_ai.input.messages", json.dumps(filter_messages(messages)))
```

### Truncation: Limit Content Size

```python
MAX_CONTENT_LENGTH = 4096  # bytes

def truncate_content(content_json):
    """Truncate content to prevent oversized spans."""
    if len(content_json) > MAX_CONTENT_LENGTH:
        return content_json[:MAX_CONTENT_LENGTH] + '...[truncated]"'
    return content_json

span.set_attribute("gen_ai.input.messages", truncate_content(json.dumps(messages)))
```

### Hooks: Route to Separate Storage

Use an OTel SpanProcessor to intercept content attributes and route them to
access-controlled storage:

```python
from opentelemetry.sdk.trace import SpanProcessor

CONTENT_ATTRS = {
    "gen_ai.input.messages",
    "gen_ai.output.messages",
    "gen_ai.system_instructions",
    "gen_ai.tool.definitions",
    "gen_ai.tool.call.arguments",
    "gen_ai.tool.call.result",
}

class ContentRedactionProcessor(SpanProcessor):
    def __init__(self, content_store):
        self.content_store = content_store

    def on_end(self, span):
        attrs = span.attributes or {}
        content = {}
        for key in CONTENT_ATTRS:
            if key in attrs:
                content[key] = attrs[key]

        if content:
            # Store content separately with access controls
            ref = self.content_store.store(
                trace_id=span.context.trace_id,
                span_id=span.context.span_id,
                content=content,
            )
            # Replace content with reference
            # Note: span attributes are immutable after export;
            # this processor runs before the exporter
```

### Environment-Based Strategy

| Environment | Strategy |
| :--- | :--- |
| Development | Full content capture — all fields enabled |
| Staging | Full content capture — matches production behavior |
| Production | Filtered capture — redact PII, truncate large payloads |
| Regulated (HIPAA/SOC2) | Separate storage — content routed to access-controlled store |

**Recommendation**: Enable content capture everywhere. Use filtering in production,
full content in non-prod. The debugging value of content capture far outweighs the
cost when failures occur.

## Provider-Specific Notes

### OpenAI

```python
# OpenAI auto-instrumentation captures tool_calls in finish_reason
# and includes function call details in output messages automatically
OpenAIInstrumentor().instrument()
```

### Anthropic

```python
# Anthropic responses include tool_use blocks
# Auto-instrumentation maps these to tool_call parts
AnthropicInstrumentor().instrument()
```

Cache tokens appear as `gen_ai.usage.cache_creation_input_tokens` and
`gen_ai.usage.cache_read_input_tokens` — these are captured regardless of content
capture settings (they're usage attributes, not content).

## Troubleshooting

**Content fields empty with auto-instrumentation:**
- Verify `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` is set
- Must be set before `Instrumentor().instrument()` is called
- Check env var is visible to the process (not just the shell)

**Content too large:**
- Span attribute size limits vary by exporter (OTLP default: 128KB)
- Use truncation for large prompts/responses
- Consider storing large content separately and referencing by ID

**JSON parsing errors in Honeycomb:**
- Ensure content is valid JSON when setting attributes
- Use `json.dumps()` / `JSON.stringify()` — don't manually construct JSON strings
