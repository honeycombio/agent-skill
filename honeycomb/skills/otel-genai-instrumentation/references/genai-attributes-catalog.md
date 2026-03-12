# GenAI Attributes Catalog

Upstream reference for `gen_ai.*` semantic convention attributes (OTel Semantic
Conventions v1.40.0, Development status). For full attribute definitions, types, and
examples, see the upstream docs linked below.

## Upstream Semantic Convention Pages

- **Attribute registry**: https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/
- **Model spans (chat, embeddings, etc.)**: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/
- **Agent spans (invoke_agent, execute_tool)**: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/
- **Events (input/output messages, tool calls)**: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-events/
- **Metrics**: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/
- **MCP spans and metrics**: https://opentelemetry.io/docs/specs/semconv/gen-ai/mcp/

### Provider-Specific Extensions

- **Anthropic**: https://opentelemetry.io/docs/specs/semconv/gen-ai/anthropic/
- **OpenAI**: https://opentelemetry.io/docs/specs/semconv/gen-ai/openai/
- **AWS Bedrock**: https://opentelemetry.io/docs/specs/semconv/gen-ai/aws-bedrock/
- **Azure AI**: https://opentelemetry.io/docs/specs/semconv/gen-ai/azure-ai-inference/

## Message JSON Schema

Content attributes (`gen_ai.input.messages`, `gen_ai.output.messages`) use this JSON
structure:

```json
[
  {
    "role": "user",
    "parts": [
      {"type": "text", "text": "What's the weather?"}
    ]
  },
  {
    "role": "assistant",
    "parts": [
      {"type": "tool_call", "id": "call_123", "name": "get_weather", "arguments": "{\"city\":\"NYC\"}"}
    ]
  },
  {
    "role": "tool",
    "parts": [
      {"type": "tool_call_response", "id": "call_123", "response": "{\"temp\":72}"}
    ]
  },
  {
    "role": "assistant",
    "parts": [
      {"type": "text", "text": "It's 72°F in NYC."}
    ]
  }
]
```

Part types: `text`, `tool_call`, `tool_call_response`, `reasoning`.

**Note on `tool_call_response`**: Use the `response` field (not `content`) for the tool
result. The `content` field is reserved for `text` parts.
