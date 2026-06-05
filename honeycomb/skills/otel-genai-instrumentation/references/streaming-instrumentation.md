# Streaming Instrumentation

Instrumenting streaming GenAI responses (SSE, chunked responses) with proper span
lifecycle, timing metrics, and error handling.

## Span Lifecycle

A streaming span covers the **full stream lifetime** — from request start to final
chunk received. Usage attributes are set after the stream completes.

```
chat gpt-4  ─────────────────────────────────────►
             │         │    │    │    │         │
             request   first chunk  chunk     stream
             sent      chunk       ...        complete
                       ▲                      ▲
                       TTFC                   set usage attrs,
                                              end span
```

## Key Metrics

### Client-Side (Hosted APIs)

| Metric | Description | When to use |
| :--- | :--- | :--- |
| `gen_ai.client.operation.time_to_first_chunk` | Time from request to first streamed chunk (includes network) | Hosted APIs (OpenAI, Anthropic) |
| `gen_ai.client.operation.time_per_output_chunk` | Inter-chunk time (client-observed) | Measuring delivery consistency |

### Server-Side (Self-Hosted)

| Metric | Description | When to use |
| :--- | :--- | :--- |
| `gen_ai.server.time_to_first_token` | Server-side TTFT (queue + prefill time) | Self-hosted (vLLM, TGI) |
| `gen_ai.server.time_per_output_token` | Decode speed after first token | Self-hosted throughput |

**Client vs Server**: Client metrics include network latency; server metrics isolate
model performance. Use client metrics when calling hosted APIs, server metrics when
running your own inference server.

## Python Example

```python
import time
from opentelemetry import trace, metrics
from opentelemetry.trace import SpanKind, StatusCode

tracer = trace.get_tracer("genai-client")
meter = metrics.get_meter("genai-client")

ttfc_histogram = meter.create_histogram(
    "gen_ai.client.operation.time_to_first_chunk",
    unit="s",
    description="Time to first chunk from streaming GenAI response",
)

duration_histogram = meter.create_histogram(
    "gen_ai.client.operation.duration",
    unit="s",
    description="Total duration of GenAI operation",
)

def chat_stream(client, model, messages, conversation_id):
    with tracer.start_as_current_span(
        f"chat {model}",
        kind=SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "chat",
            "gen_ai.conversation.id": conversation_id,
            "gen_ai.system": "openai",
            "gen_ai.request.model": model,
            "server.address": "api.openai.com",
            "server.port": 443,
        },
    ) as span:
        start_time = time.monotonic()
        first_chunk_time = None
        collected_content = []
        input_tokens = 0
        output_tokens = 0

        try:
            stream = client.chat.completions.create(
                model=model, messages=messages, stream=True
            )

            for chunk in stream:
                if first_chunk_time is None and chunk.choices:
                    first_chunk_time = time.monotonic()
                    ttfc = first_chunk_time - start_time
                    ttfc_histogram.record(ttfc, {
                        "gen_ai.operation.name": "chat",
                        "gen_ai.request.model": model,
                    })

                if chunk.choices and chunk.choices[0].delta.content:
                    collected_content.append(chunk.choices[0].delta.content)

                # Usage comes in the final chunk
                if chunk.usage:
                    input_tokens = chunk.usage.prompt_tokens
                    output_tokens = chunk.usage.completion_tokens

                # Check for finish reason
                if chunk.choices and chunk.choices[0].finish_reason:
                    span.set_attribute(
                        "gen_ai.response.finish_reasons",
                        [chunk.choices[0].finish_reason],
                    )

            # Set usage after stream completes
            span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", output_tokens)

            total_duration = time.monotonic() - start_time
            duration_histogram.record(total_duration, {
                "gen_ai.operation.name": "chat",
                "gen_ai.request.model": model,
            })

            return "".join(collected_content)

        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            span.set_attribute("error.type", type(e).__name__)
            raise
```

## Node.js Example

```javascript
const { trace, SpanKind, SpanStatusCode } = require("@opentelemetry/api");
const { metrics } = require("@opentelemetry/api");

const tracer = trace.getTracer("genai-client");
const meter = metrics.getMeter("genai-client");

const ttfcHistogram = meter.createHistogram(
  "gen_ai.client.operation.time_to_first_chunk",
  { unit: "s", description: "Time to first chunk" }
);

async function chatStream(client, model, messages, conversationId) {
  return tracer.startActiveSpan(
    `chat ${model}`,
    {
      kind: SpanKind.CLIENT,
      attributes: {
        "gen_ai.operation.name": "chat",
        "gen_ai.conversation.id": conversationId,
        "gen_ai.system": "openai",
        "gen_ai.request.model": model,
        "server.address": "api.openai.com",
        "server.port": 443,
      },
    },
    async (span) => {
      const startTime = performance.now();
      let firstChunkRecorded = false;
      const chunks = [];

      try {
        const stream = await client.chat.completions.create({
          model,
          messages,
          stream: true,
          stream_options: { include_usage: true },
        });

        for await (const chunk of stream) {
          if (!firstChunkRecorded && chunk.choices?.length > 0) {
            const ttfc = (performance.now() - startTime) / 1000;
            ttfcHistogram.record(ttfc, {
              "gen_ai.operation.name": "chat",
              "gen_ai.request.model": model,
            });
            firstChunkRecorded = true;
          }

          if (chunk.choices?.[0]?.delta?.content) {
            chunks.push(chunk.choices[0].delta.content);
          }

          if (chunk.usage) {
            span.setAttributes({
              "gen_ai.usage.input_tokens": chunk.usage.prompt_tokens,
              "gen_ai.usage.output_tokens": chunk.usage.completion_tokens,
            });
          }

          if (chunk.choices?.[0]?.finish_reason) {
            span.setAttribute(
              "gen_ai.response.finish_reasons",
              [chunk.choices[0].finish_reason]
            );
          }
        }

        return chunks.join("");
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

## Go Example

```go
func ChatStream(ctx context.Context, client *openai.Client, model string, messages []Message, conversationID string) (string, error) {
    ctx, span := tracer.Start(ctx, "chat "+model,
        trace.WithSpanKind(trace.SpanKindClient),
        trace.WithAttributes(
            attribute.String("gen_ai.operation.name", "chat"),
            attribute.String("gen_ai.conversation.id", conversationID),
            attribute.String("gen_ai.system", "openai"),
            attribute.String("gen_ai.request.model", model),
            attribute.String("server.address", "api.openai.com"),
            attribute.Int("server.port", 443),
        ),
    )
    defer span.End()

    startTime := time.Now()
    firstChunkRecorded := false
    var content strings.Builder

    stream, err := client.ChatStream(ctx, model, messages)
    if err != nil {
        span.SetStatus(codes.Error, err.Error())
        span.SetAttributes(attribute.String("error.type", fmt.Sprintf("%T", err)))
        return "", err
    }
    defer stream.Close()

    for {
        chunk, err := stream.Recv()
        if err == io.EOF {
            break
        }
        if err != nil {
            span.SetStatus(codes.Error, err.Error())
            span.SetAttributes(attribute.String("error.type", fmt.Sprintf("%T", err)))
            return "", err
        }

        if !firstChunkRecorded && len(chunk.Choices) > 0 {
            ttfc := time.Since(startTime).Seconds()
            ttfcHistogram.Record(ctx, ttfc,
                metric.WithAttributes(
                    attribute.String("gen_ai.operation.name", "chat"),
                    attribute.String("gen_ai.request.model", model),
                ),
            )
            firstChunkRecorded = true
        }

        if len(chunk.Choices) > 0 && chunk.Choices[0].Delta.Content != "" {
            content.WriteString(chunk.Choices[0].Delta.Content)
        }

        if chunk.Usage != nil {
            span.SetAttributes(
                attribute.Int("gen_ai.usage.input_tokens", chunk.Usage.InputTokens),
                attribute.Int("gen_ai.usage.output_tokens", chunk.Usage.OutputTokens),
            )
        }
    }

    return content.String(), nil
}
```

## Handling Mid-Stream Errors

When a stream fails partway through:

1. Record the error on the span immediately
2. Set span status to ERROR
3. Record partial usage if available
4. End the span — don't leave it hanging

```python
# Python: mid-stream error handling
try:
    for chunk in stream:
        process_chunk(chunk)
except Exception as e:
    span.set_status(StatusCode.ERROR, str(e))
    span.set_attribute("error.type", type(e).__name__)
    span.add_event("stream.error", {
        "stream.chunks_received": chunk_count,
        "stream.partial": True,
    })
    raise
```

**Common mid-stream errors:**
- `ConnectionError` / `TimeoutError`: Network interruption
- `APIError`: Provider-side failure during generation
- `ContentFilterError`: Response filtered mid-stream

## Metrics Recording Pattern

Record metrics at specific points in the stream lifecycle:

| Point | Metric | Value |
| :--- | :--- | :--- |
| First chunk received | `gen_ai.client.operation.time_to_first_chunk` | elapsed since request |
| Each chunk received | `gen_ai.client.operation.time_per_output_chunk` | time since previous chunk |
| Stream complete | `gen_ai.client.operation.duration` | total elapsed time |
| Stream complete | `gen_ai.client.token.usage` | final token counts |
