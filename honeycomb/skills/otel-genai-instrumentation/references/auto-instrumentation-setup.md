# Auto-Instrumentation Setup

Python and Node.js have official OpenTelemetry auto-instrumentation packages for GenAI
providers. For all other languages, use manual instrumentation.

## Prerequisites

1. Base OTel SDK configured and sending to Honeycomb (see **otel-instrumentation** skill)
2. Opt into GenAI semantic conventions:
```bash
export OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental
```

## Python Packages

Setup: `pip install <package>` + `Instrumentor().instrument()` or CLI `opentelemetry-instrument`.

| Package | Provider | Min SDK Version | Upstream README |
| :--- | :--- | :--- | :--- |
| `opentelemetry-instrumentation-openai-v2` | OpenAI | openai >= v1.26.0 | [README](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation-genai/opentelemetry-instrumentation-openai-v2) |
| `opentelemetry-instrumentation-anthropic` | Anthropic | anthropic >= v0.16.0 | [README](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation-genai/opentelemetry-instrumentation-anthropic) |
| `opentelemetry-instrumentation-claude-agent-sdk` | Claude Agent SDK | claude-agent-sdk >= v0.1.14 | [README](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation-genai/opentelemetry-instrumentation-claude-agent-sdk) |
| `opentelemetry-instrumentation-google-genai` | Google GenAI | google-genai >= v1.32.0 | [README](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation-genai/opentelemetry-instrumentation-google-genai) |
| `opentelemetry-instrumentation-vertexai` | Vertex AI | google-cloud-aiplatform >= v1.64 | [README](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation-genai/opentelemetry-instrumentation-vertexai) |
| `opentelemetry-instrumentation-langchain` | LangChain | langchain >= v0.3.21 | [README](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation-genai/opentelemetry-instrumentation-langchain) |
| `opentelemetry-instrumentation-openai-agents-v2` | OpenAI Agents | openai-agents >= v0.3.3 | [README](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation-genai/opentelemetry-instrumentation-openai-agents-v2) |
| `opentelemetry-instrumentation-weaviate` | Weaviate | weaviate-client >= v3.0.0, < v5.0.0 | [README](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation-genai/opentelemetry-instrumentation-weaviate) |

## Node.js Packages

Setup: `npm install <package>` + register via OTel Node SDK.

| Package | Provider | Min SDK Version | Upstream README |
| :--- | :--- | :--- | :--- |
| `@opentelemetry/instrumentation-openai` | OpenAI | openai >= 4.19.0 | [README](https://github.com/open-telemetry/opentelemetry-js-contrib/tree/main/packages/instrumentation-openai) |
| `@opentelemetry/instrumentation-langchain` | LangChain | langchain >= 1.0.0 | [README](https://github.com/open-telemetry/opentelemetry-js-contrib/tree/main/packages/instrumentation-langchain) |

**Note**: `@opentelemetry/instrumentation-langchain` is not yet published to npm.

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

**Important**: Must be set before `Instrumentor().instrument()` is called.

**Privacy**: See content-capture-setup.md for filtering and truncation controls.

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
