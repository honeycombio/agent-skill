# GenAI Attributes Catalog

Complete reference of `gen_ai.*` semantic convention attributes organized by category.
Based on OTel Semantic Conventions v1.40.0 (Development status).

## Request Attributes

Set before the GenAI API call on the inference span.

| Attribute | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `gen_ai.operation.name` | string | Operation type | `"chat"`, `"embeddings"` |
| `gen_ai.system` | string | GenAI system identifier | `"openai"`, `"anthropic"` |
| `gen_ai.request.model` | string | Requested model name | `"gpt-4"`, `"claude-sonnet-4-5-20250929"` |
| `gen_ai.request.max_tokens` | int | Max tokens to generate | `1024` |
| `gen_ai.request.temperature` | float | Sampling temperature | `0.7` |
| `gen_ai.request.top_p` | float | Nucleus sampling | `0.9` |
| `gen_ai.request.top_k` | int | Top-k sampling | `40` |
| `gen_ai.request.stop_sequences` | string[] | Stop sequences | `["\n\n"]` |
| `gen_ai.request.frequency_penalty` | float | Frequency penalty | `0.5` |
| `gen_ai.request.presence_penalty` | float | Presence penalty | `0.5` |
| `gen_ai.request.encoding_formats` | string[] | Embedding encoding formats | `["float"]` |
| `gen_ai.request.seed` | int | Random seed for reproducibility | `42` |

## Response Attributes

Set after the GenAI API call completes.

| Attribute | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `gen_ai.response.id` | string | Provider response ID | `"chatcmpl-abc123"` |
| `gen_ai.response.model` | string | Actual model used | `"gpt-4-0613"` |
| `gen_ai.response.finish_reasons` | string[] | Why generation stopped | `["stop"]`, `["tool_calls"]` |

## Usage Attributes

Token consumption metrics, set after the call.

| Attribute | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `gen_ai.usage.input_tokens` | int | Tokens in prompt | `150` |
| `gen_ai.usage.output_tokens` | int | Tokens generated | `500` |
| `gen_ai.usage.cache_creation_input_tokens` | int | Tokens written to cache | `1000` |
| `gen_ai.usage.cache_read_input_tokens` | int | Tokens read from cache | `800` |

## Content Attributes (Opt-in)

Require `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` for auto-instrumentation,
or manual setting for manual instrumentation.

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `gen_ai.input.messages` | string (JSON) | Input messages array |
| `gen_ai.output.messages` | string (JSON) | Output messages array |
| `gen_ai.system_instructions` | string (JSON) | System prompt messages |
| `gen_ai.tool.definitions` | string (JSON) | Tool/function schemas |

## Tool Attributes

Set on `execute_tool` spans.

| Attribute | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `gen_ai.tool.name` | string | Tool/function name | `"get_weather"` |
| `gen_ai.tool.call.id` | string | Provider's call ID | `"call_abc123"` |
| `gen_ai.tool.call.arguments` | string (JSON) | Arguments passed (opt-in) | `'{"city":"NYC"}'` |
| `gen_ai.tool.call.result` | string (JSON) | Result returned (opt-in) | `'{"temp":72}'` |

## Agent Attributes

Set on `invoke_agent`, `create_agent` spans.

| Attribute | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `gen_ai.agent.name` | string | Agent name | `"research-agent"` |
| `gen_ai.agent.id` | string | Agent instance ID | `"agent-xyz-789"` |
| `gen_ai.agent.description` | string | Agent description | `"Researches topics"` |
| `gen_ai.conversation.id` | string | Conversation/session ID | `"conv-abc-123"` |

## Retrieval Attributes

Set on `retrieval` spans (RAG).

| Attribute | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `gen_ai.data_source.id` | string | Data source identifier | `"knowledge-base-v2"` |

## Provider Attributes

| Attribute | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `gen_ai.provider.name` | string | Provider name | `"openai"`, `"anthropic"` |

## Server Attributes

Standard OTel server attributes used on GenAI inference spans.

| Attribute | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `server.address` | string | API host | `"api.openai.com"` |
| `server.port` | int | API port | `443` |

## Error Attributes

| Attribute | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `error.type` | string | Error class name | `"RateLimitError"` |

## Evaluation Attributes

Set on `gen_ai.evaluation.result` events.

| Attribute | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `gen_ai.evaluation.name` | string | Evaluation name | `"relevance"` |
| `gen_ai.evaluation.score.value` | float | Numeric score | `0.85` |
| `gen_ai.evaluation.score.label` | string | Categorical label | `"pass"` |
| `gen_ai.evaluation.explanation` | string | Reasoning for score | `"Answer matches query"` |
| `gen_ai.response.id` | string | Links to scored inference | `"chatcmpl-abc123"` |

## Provider-Specific Attributes

### OpenAI
| Attribute | Type | Description |
| :--- | :--- | :--- |
| `gen_ai.openai.response.system_fingerprint` | string | System fingerprint for reproducibility |
| `gen_ai.openai.response.service_tier` | string | Service tier used |

### AWS Bedrock
| Attribute | Type | Description |
| :--- | :--- | :--- |
| `aws.bedrock.guardrail.id` | string | Guardrail identifier |
| `aws.bedrock.knowledge_base.id` | string | Knowledge base identifier |

### Azure AI
| Attribute | Type | Description |
| :--- | :--- | :--- |
| `azure.resource_provider.namespace` | string | Azure resource provider |

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
      {"type": "tool_call_response", "id": "call_123", "content": "{\"temp\":72}"}
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
