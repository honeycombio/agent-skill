# Auto-Instrumentation Setup (Python Only)

Python is the only language with official OpenTelemetry auto-instrumentation packages
for GenAI providers. For all other languages, use manual instrumentation.

## Prerequisites

1. Base OTel SDK configured and sending to Honeycomb (see **otel-instrumentation** skill)
2. Opt into GenAI semantic conventions:
```bash
export OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental
```

## OpenAI

```bash
pip install opentelemetry-instrumentation-openai-v2
```

### Programmatic Setup
```python
from opentelemetry.instrumentation.openai import OpenAIInstrumentor

OpenAIInstrumentor().instrument()
```

### CLI Setup
```bash
opentelemetry-instrument python app.py
```

- **Min SDK version**: openai >= v1.26.0
- Instruments: `ChatCompletion.create`, `Completion.create`, `Embedding.create`
- Streaming: automatically tracks stream lifecycle and token usage

## Anthropic

```bash
pip install opentelemetry-instrumentation-anthropic
```

### Programmatic Setup
```python
from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor

AnthropicInstrumentor().instrument()
```

- **Min SDK version**: anthropic >= v0.16.0
- Instruments: `Messages.create`, `Completions.create`
- Cache tokens: tracks `gen_ai.usage.cache_creation_input_tokens` and
  `gen_ai.usage.cache_read_input_tokens`

## Claude Agent SDK

```bash
pip install opentelemetry-instrumentation-claude-agent-sdk
```

### Programmatic Setup
```python
from opentelemetry.instrumentation.claude_agent_sdk import ClaudeAgentSDKInstrumentor

ClaudeAgentSDKInstrumentor().instrument()
```

- **Min SDK version**: claude-agent-sdk >= v0.1.14
- Instruments: agent invocations, tool calls, multi-turn conversations
- Creates `invoke_agent` and `execute_tool` spans automatically

## Google GenAI

```bash
pip install opentelemetry-instrumentation-google-genai
```

### Programmatic Setup
```python
from opentelemetry.instrumentation.google_genai import GoogleGenAiInstrumentor

GoogleGenAiInstrumentor().instrument()
```

- **Min SDK version**: google-genai >= v1.32.0
- Instruments: `generate_content`, embeddings

## Vertex AI

```bash
pip install opentelemetry-instrumentation-vertexai
```

### Programmatic Setup
```python
from opentelemetry.instrumentation.vertexai import VertexAIInstrumentor

VertexAIInstrumentor().instrument()
```

- **Min SDK version**: google-cloud-aiplatform >= v1.64
- Instruments: Vertex AI prediction and generation calls

## LangChain

```bash
pip install opentelemetry-instrumentation-langchain
```

### Programmatic Setup
```python
from opentelemetry.instrumentation.langchain import LangchainInstrumentor

LangchainInstrumentor().instrument()
```

- **Min SDK version**: langchain >= v0.3.21
- Instruments: chains, agents, tools, retrievers, LLM calls
- Creates nested span hierarchies reflecting chain/agent structure

## OpenAI Agents

```bash
pip install opentelemetry-instrumentation-openai-agents-v2
```

### Programmatic Setup
```python
from opentelemetry.instrumentation.openai_agents import OpenAIAgentsInstrumentor

OpenAIAgentsInstrumentor().instrument()
```

- **Min SDK version**: openai-agents >= v0.3.3
- Instruments: agent runs, handoffs, tool calls, guardrails

## Weaviate

```bash
pip install opentelemetry-instrumentation-weaviate
```

### Programmatic Setup
```python
from opentelemetry.instrumentation.weaviate import WeaviateInstrumentor

WeaviateInstrumentor().instrument()
```

- **Min SDK version**: weaviate-client >= v3.0.0, < v5.0.0
- Instruments: vector search, object operations

## Enabling Content Capture

By default, auto-instrumentation does **not** capture prompt/response content. Enable:

```bash
export OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true
```

This enables capture of:
- `gen_ai.input.messages` — prompts and tool call arguments
- `gen_ai.output.messages` — model responses and tool call results
- `gen_ai.system_instructions` — system prompts
- `gen_ai.tool.definitions` — tool schemas

**Privacy**: See content-capture-setup.md for filtering and truncation controls.

## Complete Example

Full setup combining base OTel SDK + GenAI auto-instrumentation:

```python
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.openai import OpenAIInstrumentor

# Environment
os.environ["OTEL_SEMCONV_STABILITY_OPT_IN"] = "gen_ai_latest_experimental"
os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

# SDK setup
resource = Resource.create({"service.name": "my-genai-service"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)

# GenAI instrumentation
OpenAIInstrumentor().instrument()

# Now all OpenAI calls produce spans automatically
import openai
client = openai.OpenAI()
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)
```

## Troubleshooting

**No spans appearing:**
- Verify `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` is set
- Verify base OTel SDK is configured (check with a manual test span)
- Check SDK version meets minimum requirement

**Content fields empty:**
- Set `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true`
- Must be set before `Instrumentor().instrument()` is called

**Version conflicts:**
- Some instrumentors pin specific SDK versions; check compatibility
- Use `pip install --dry-run` to detect conflicts before installing
