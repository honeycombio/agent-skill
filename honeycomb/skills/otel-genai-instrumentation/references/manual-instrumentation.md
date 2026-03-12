# Manual GenAI Instrumentation

Code examples for instrumenting GenAI operations when auto-instrumentation is not
available (Node.js, Go, Java) or when you need custom control.

## Prerequisites

Base OTel SDK configured. Enable GenAI conventions:
```bash
export OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental
```

## Span Naming Rule

All GenAI span names MUST follow `"{operation} {identifier}"` — the span name prefix
must match `gen_ai.operation.name`. Examples: `"chat gpt-4"`, `"execute_tool get_weather"`,
`"invoke_agent research-agent"`.

## Chat/Completion Spans

SpanKind: CLIENT. Span name: `chat {model}`.

### Python

```python
from opentelemetry import trace
from opentelemetry.trace import SpanKind, StatusCode

tracer = trace.get_tracer("genai-client")

def chat(client, model, messages):
    with tracer.start_as_current_span(
        f"chat {model}",
        kind=SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "chat",
            "gen_ai.system": "openai",
            "gen_ai.request.model": model,
            "gen_ai.request.max_tokens": 1024,
            "gen_ai.request.temperature": 0.7,
            "server.address": "api.openai.com",
            "server.port": 443,
        },
    ) as span:
        try:
            response = client.chat.completions.create(
                model=model, messages=messages, max_tokens=1024, temperature=0.7
            )
            span.set_attribute("gen_ai.response.id", response.id)
            span.set_attribute("gen_ai.response.model", response.model)
            span.set_attribute("gen_ai.response.finish_reasons", [response.choices[0].finish_reason])
            span.set_attribute("gen_ai.usage.input_tokens", response.usage.prompt_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", response.usage.completion_tokens)
            return response
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            span.set_attribute("error.type", type(e).__name__)
            raise
```

### Node.js

```javascript
const { trace, SpanKind, SpanStatusCode } = require("@opentelemetry/api");

const tracer = trace.getTracer("genai-client");

async function chat(client, model, messages) {
  return tracer.startActiveSpan(
    `chat ${model}`,
    {
      kind: SpanKind.CLIENT,
      attributes: {
        "gen_ai.operation.name": "chat",
        "gen_ai.system": "openai",
        "gen_ai.request.model": model,
        "gen_ai.request.max_tokens": 1024,
        "gen_ai.request.temperature": 0.7,
        "server.address": "api.openai.com",
        "server.port": 443,
      },
    },
    async (span) => {
      try {
        const response = await client.chat.completions.create({
          model,
          messages,
          max_tokens: 1024,
          temperature: 0.7,
        });
        span.setAttributes({
          "gen_ai.response.id": response.id,
          "gen_ai.response.model": response.model,
          "gen_ai.response.finish_reasons": [response.choices[0].finish_reason],
          "gen_ai.usage.input_tokens": response.usage.prompt_tokens,
          "gen_ai.usage.output_tokens": response.usage.completion_tokens,
        });
        return response;
      } catch (e) {
        span.setStatus({ code: SpanStatusCode.ERROR, message: e.message });
        span.setAttribute("error.type", e.constructor.name);
        throw e;
      } finally {
        span.end();
      }
    }
  );
}
```

### Go

```go
package genai

import (
    "context"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/codes"
    "go.opentelemetry.io/otel/trace"
)

var tracer = otel.Tracer("genai-client")

func Chat(ctx context.Context, client *openai.Client, model string, messages []Message) (*Response, error) {
    ctx, span := tracer.Start(ctx, "chat "+model,
        trace.WithSpanKind(trace.SpanKindClient),
        trace.WithAttributes(
            attribute.String("gen_ai.operation.name", "chat"),
            attribute.String("gen_ai.system", "openai"),
            attribute.String("gen_ai.request.model", model),
            attribute.Int("gen_ai.request.max_tokens", 1024),
            attribute.Float64("gen_ai.request.temperature", 0.7),
            attribute.String("server.address", "api.openai.com"),
            attribute.Int("server.port", 443),
        ),
    )
    defer span.End()

    resp, err := client.Chat(ctx, model, messages)
    if err != nil {
        span.SetStatus(codes.Error, err.Error())
        span.SetAttributes(attribute.String("error.type", fmt.Sprintf("%T", err)))
        return nil, err
    }

    span.SetAttributes(
        attribute.String("gen_ai.response.id", resp.ID),
        attribute.String("gen_ai.response.model", resp.Model),
        attribute.StringSlice("gen_ai.response.finish_reasons", []string{resp.FinishReason}),
        attribute.Int("gen_ai.usage.input_tokens", resp.Usage.InputTokens),
        attribute.Int("gen_ai.usage.output_tokens", resp.Usage.OutputTokens),
    )
    return resp, nil
}
```

## Embedding Spans

SpanKind: CLIENT. Span name: `embeddings {model}`.

### Python

```python
def embed(client, model, texts):
    with tracer.start_as_current_span(
        f"embeddings {model}",
        kind=SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "embeddings",
            "gen_ai.system": "openai",
            "gen_ai.request.model": model,
            "gen_ai.request.encoding_formats": ["float"],
            "server.address": "api.openai.com",
            "server.port": 443,
        },
    ) as span:
        try:
            response = client.embeddings.create(model=model, input=texts)
            span.set_attribute("gen_ai.response.model", response.model)
            span.set_attribute("gen_ai.usage.input_tokens", response.usage.prompt_tokens)
            return response
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            span.set_attribute("error.type", type(e).__name__)
            raise
```

### Node.js

```javascript
async function embed(client, model, texts) {
  return tracer.startActiveSpan(
    `embeddings ${model}`,
    {
      kind: SpanKind.CLIENT,
      attributes: {
        "gen_ai.operation.name": "embeddings",
        "gen_ai.system": "openai",
        "gen_ai.request.model": model,
        "gen_ai.request.encoding_formats": ["float"],
        "server.address": "api.openai.com",
        "server.port": 443,
      },
    },
    async (span) => {
      try {
        const response = await client.embeddings.create({ model, input: texts });
        span.setAttributes({
          "gen_ai.response.model": response.model,
          "gen_ai.usage.input_tokens": response.usage.prompt_tokens,
        });
        return response;
      } catch (e) {
        span.setStatus({ code: SpanStatusCode.ERROR, message: e.message });
        span.setAttribute("error.type", e.constructor.name);
        throw e;
      } finally {
        span.end();
      }
    }
  );
}
```

## Retrieval Spans

SpanKind: CLIENT. Span name: `retrieval {data_source}`.

### Python

```python
def retrieve(vector_db, data_source, query, top_k=10):
    with tracer.start_as_current_span(
        f"retrieval {data_source}",
        kind=SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "retrieval",
            "gen_ai.data_source.id": data_source,
            "server.address": vector_db.host,
            "server.port": vector_db.port,
        },
    ) as span:
        try:
            results = vector_db.query(query, top_k=top_k)
            span.set_attribute("gen_ai.retrieval.result_count", len(results))
            return results
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            span.set_attribute("error.type", type(e).__name__)
            raise
```

## Tool Execution Spans

SpanKind: INTERNAL. Span name: `execute_tool {tool_name}`.

### Python

```python
def execute_tool(tool_name, tool_call_id, arguments):
    with tracer.start_as_current_span(
        f"execute_tool {tool_name}",
        kind=SpanKind.INTERNAL,
        attributes={
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": tool_name,
            "gen_ai.tool.call.id": tool_call_id,
        },
    ) as span:
        try:
            # Opt-in: capture tool arguments
            span.set_attribute("gen_ai.tool.call.arguments", json.dumps(arguments))

            result = tools[tool_name](**arguments)

            # Opt-in: capture tool result
            span.set_attribute("gen_ai.tool.call.result", json.dumps(result))
            return result
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            span.set_attribute("error.type", type(e).__name__)
            raise
```

### Node.js

```javascript
async function executeTool(toolName, toolCallId, args) {
  return tracer.startActiveSpan(
    `execute_tool ${toolName}`,
    {
      kind: SpanKind.INTERNAL,
      attributes: {
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": toolName,
        "gen_ai.tool.call.id": toolCallId,
      },
    },
    async (span) => {
      try {
        span.setAttribute("gen_ai.tool.call.arguments", JSON.stringify(args));
        const result = await tools[toolName](args);
        span.setAttribute("gen_ai.tool.call.result", JSON.stringify(result));
        return result;
      } catch (e) {
        span.setStatus({ code: SpanStatusCode.ERROR, message: e.message });
        span.setAttribute("error.type", e.constructor.name);
        throw e;
      } finally {
        span.end();
      }
    }
  );
}
```

### Go

```go
func ExecuteTool(ctx context.Context, toolName, callID string, args map[string]any) (any, error) {
    ctx, span := tracer.Start(ctx, "execute_tool "+toolName,
        trace.WithSpanKind(trace.SpanKindInternal),
        trace.WithAttributes(
            attribute.String("gen_ai.operation.name", "execute_tool"),
            attribute.String("gen_ai.tool.name", toolName),
            attribute.String("gen_ai.tool.call.id", callID),
        ),
    )
    defer span.End()

    argsJSON, _ := json.Marshal(args)
    span.SetAttributes(attribute.String("gen_ai.tool.call.arguments", string(argsJSON)))

    result, err := tools[toolName](ctx, args)
    if err != nil {
        span.SetStatus(codes.Error, err.Error())
        span.SetAttributes(attribute.String("error.type", fmt.Sprintf("%T", err)))
        return nil, err
    }

    resultJSON, _ := json.Marshal(result)
    span.SetAttributes(attribute.String("gen_ai.tool.call.result", string(resultJSON)))
    return result, nil
}
```

## Agent Invocation Spans

SpanKind: CLIENT or INTERNAL. Span name: `invoke_agent {agent_name}`.

### Python

```python
def invoke_agent(agent_name, agent_id, conversation_id, input_messages):
    with tracer.start_as_current_span(
        f"invoke_agent {agent_name}",
        kind=SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": agent_name,
            "gen_ai.agent.id": agent_id,
            "gen_ai.conversation.id": conversation_id,
        },
    ) as span:
        try:
            result = agent.run(input_messages)

            span.set_attribute("gen_ai.usage.input_tokens", result.usage.input_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", result.usage.output_tokens)
            return result
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            span.set_attribute("error.type", type(e).__name__)
            raise
```

## Pattern: Request Attributes Before, Response Attributes After

The general pattern for all GenAI spans:

1. **Before the call** — set on span creation:
   - `gen_ai.operation.name`, `gen_ai.system`, `gen_ai.request.model`
   - `gen_ai.request.max_tokens`, `gen_ai.request.temperature`
   - `server.address`, `server.port`

2. **After the call** — set on the span:
   - `gen_ai.response.id`, `gen_ai.response.model`
   - `gen_ai.response.finish_reasons`
   - `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`

3. **On error** — set on the span:
   - `error.type` (exception class name)
   - `span.set_status(ERROR)` / `span.SetStatus(codes.Error, ...)`

## Error Handling Best Practices

- Always set `error.type` to the exception class name, not the message
- Always set span status to ERROR when the operation fails
- Record the exception on the span for stack trace capture:
  ```python
  span.record_exception(e)  # Python
  ```
  ```javascript
  span.recordException(e);  // Node.js
  ```
  ```go
  span.RecordError(err)  // Go
  ```
- Let the exception propagate — don't swallow errors silently
