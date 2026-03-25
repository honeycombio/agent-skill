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

def chat(client, model, messages, conversation_id):
    with tracer.start_as_current_span(
        f"chat {model}",
        kind=SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "chat",
            "gen_ai.conversation.id": conversation_id,
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

async function chat(client, model, messages, conversationId) {
  return tracer.startActiveSpan(
    `chat ${model}`,
    {
      kind: SpanKind.CLIENT,
      attributes: {
        "gen_ai.operation.name": "chat",
        "gen_ai.conversation.id": conversationId,
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

func Chat(ctx context.Context, client *openai.Client, model string, messages []Message, conversationID string) (*Response, error) {
    ctx, span := tracer.Start(ctx, "chat "+model,
        trace.WithSpanKind(trace.SpanKindClient),
        trace.WithAttributes(
            attribute.String("gen_ai.operation.name", "chat"),
            attribute.String("gen_ai.conversation.id", conversationID),
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
def embed(client, model, texts, conversation_id):
    with tracer.start_as_current_span(
        f"embeddings {model}",
        kind=SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "embeddings",
            "gen_ai.conversation.id": conversation_id,
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
async function embed(client, model, texts, conversationId) {
  return tracer.startActiveSpan(
    `embeddings ${model}`,
    {
      kind: SpanKind.CLIENT,
      attributes: {
        "gen_ai.operation.name": "embeddings",
        "gen_ai.conversation.id": conversationId,
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
def retrieve(vector_db, data_source, query, conversation_id, top_k=10):
    with tracer.start_as_current_span(
        f"retrieval {data_source}",
        kind=SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "retrieval",
            "gen_ai.conversation.id": conversation_id,
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

Include `gen_ai.agent.name` and `gen_ai.conversation.id` on tool spans to correlate
tools with their parent agent — essential for debugging which agent triggered a tool
failure.

### Python

```python
def execute_tool(tool_name, tool_call_id, arguments, agent_name, conversation_id):
    with tracer.start_as_current_span(
        f"execute_tool {tool_name}",
        kind=SpanKind.INTERNAL,
        attributes={
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": tool_name,
            "gen_ai.tool.call.id": tool_call_id,
            "gen_ai.agent.name": agent_name,
            "gen_ai.conversation.id": conversation_id,
        },
    ) as span:
        try:
            # Opt-in: capture tool arguments
            span.set_attribute("gen_ai.tool.call.arguments", json.dumps(arguments))

            result = tools[tool_name](**arguments)

            # Handle non-exception tool errors (tool returns error result)
            if isinstance(result, dict) and result.get("error"):
                span.set_attribute("error.type", "ToolExecutionError")
                span.set_status(StatusCode.ERROR, result["error"])

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
async function executeTool(toolName, toolCallId, args, agentName, conversationId) {
  return tracer.startActiveSpan(
    `execute_tool ${toolName}`,
    {
      kind: SpanKind.INTERNAL,
      attributes: {
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": toolName,
        "gen_ai.tool.call.id": toolCallId,
        "gen_ai.agent.name": agentName,
        "gen_ai.conversation.id": conversationId,
      },
    },
    async (span) => {
      try {
        span.setAttribute("gen_ai.tool.call.arguments", JSON.stringify(args));
        const result = await tools[toolName](args);

        // Handle non-exception tool errors
        if (result?.error) {
          span.setAttribute("error.type", "ToolExecutionError");
          span.setStatus({ code: SpanStatusCode.ERROR, message: result.error });
        }

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
func ExecuteTool(ctx context.Context, toolName, callID, agentName, conversationID string, args map[string]any) (any, error) {
    ctx, span := tracer.Start(ctx, "execute_tool "+toolName,
        trace.WithSpanKind(trace.SpanKindInternal),
        trace.WithAttributes(
            attribute.String("gen_ai.operation.name", "execute_tool"),
            attribute.String("gen_ai.tool.name", toolName),
            attribute.String("gen_ai.tool.call.id", callID),
            attribute.String("gen_ai.agent.name", agentName),
            attribute.String("gen_ai.conversation.id", conversationID),
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

    // Handle non-exception tool errors (tool returns error in result)
    if resultMap, ok := result.(map[string]any); ok {
        if errMsg, exists := resultMap["error"]; exists && errMsg != "" {
            span.SetAttributes(attribute.String("error.type", "ToolExecutionError"))
            span.SetStatus(codes.Error, fmt.Sprintf("tool execution failed: %v", errMsg))
        }
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

## Tool-Calling Loop

Complete loop showing `chat` and `execute_tool` as siblings under `invoke_agent`.
The agent owns tool execution — `chat` represents only the LLM inference, and
`execute_tool` represents the agent acting on the model's tool requests.

### Python

```python
def run_agent(client, model, messages, tools, agent_name, agent_id, conversation_id):
    with tracer.start_as_current_span(
        f"invoke_agent {agent_name}",
        kind=SpanKind.CLIENT,
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": agent_name,
            "gen_ai.agent.id": agent_id,
            "gen_ai.conversation.id": conversation_id,
        },
    ) as agent_span:
        total_input = 0
        total_output = 0

        while True:
            # chat span covers only the LLM inference
            with tracer.start_as_current_span(
                f"chat {model}",
                kind=SpanKind.CLIENT,
                attributes={
                    "gen_ai.operation.name": "chat",
                    "gen_ai.system": "openai",
                    "gen_ai.request.model": model,
                    "server.address": "api.openai.com",
                    "server.port": 443,
                },
            ) as chat_span:
                # Capture input messages for full conversation visibility
                chat_span.set_attribute("gen_ai.input.messages", json.dumps(
                    [{"role": m["role"], "parts": [{"type": "text", "text": m.get("content", "")}]}
                     for m in messages]
                ))

                response = client.chat.completions.create(
                    model=model, messages=messages, tools=tools
                )
                chat_span.set_attribute("gen_ai.response.model", response.model)
                chat_span.set_attribute("gen_ai.usage.input_tokens", response.usage.prompt_tokens)
                chat_span.set_attribute("gen_ai.usage.output_tokens", response.usage.completion_tokens)
                total_input += response.usage.prompt_tokens
                total_output += response.usage.completion_tokens

                finish = response.choices[0].finish_reason
                chat_span.set_attribute("gen_ai.response.finish_reasons", [finish])

                # Capture output messages — model response + any tool call requests
                output_parts = []
                for choice in response.choices:
                    msg = choice.message
                    if msg.content:
                        output_parts.append({"type": "text", "text": msg.content})
                    if msg.tool_calls:
                        for tc in msg.tool_calls:
                            output_parts.append({
                                "type": "tool_call", "id": tc.id,
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            })
                chat_span.set_attribute("gen_ai.output.messages", json.dumps(
                    [{"role": "assistant", "parts": output_parts}]
                ))
            # chat span is now closed

            if finish == "tool_calls":
                # execute_tool spans are siblings of chat, children of invoke_agent
                for tc in response.choices[0].message.tool_calls:
                    with tracer.start_as_current_span(
                        f"execute_tool {tc.function.name}",
                        kind=SpanKind.INTERNAL,
                        attributes={
                            "gen_ai.operation.name": "execute_tool",
                            "gen_ai.tool.name": tc.function.name,
                            "gen_ai.tool.call.id": tc.id,
                            "gen_ai.agent.name": agent_name,
                            "gen_ai.conversation.id": conversation_id,
                        },
                    ) as tool_span:
                        args = json.loads(tc.function.arguments)
                        result = tools[tc.function.name](**args)
                        tool_span.set_attribute(
                            "gen_ai.tool.call.result", json.dumps(result)
                        )
                    messages.append({
                        "role": "tool", "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    })
            else:
                # Final response — exit the loop
                agent_span.set_attribute("gen_ai.usage.input_tokens", total_input)
                agent_span.set_attribute("gen_ai.usage.output_tokens", total_output)
                return response
```

### Node.js

```javascript
async function runAgent(client, model, messages, tools, agentName, agentId, conversationId) {
  return tracer.startActiveSpan(
    `invoke_agent ${agentName}`,
    {
      kind: SpanKind.CLIENT,
      attributes: {
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.agent.name": agentName,
        "gen_ai.agent.id": agentId,
        "gen_ai.conversation.id": conversationId,
      },
    },
    async (agentSpan) => {
      let totalInput = 0;
      let totalOutput = 0;

      while (true) {
        // chat span covers only the LLM inference
        const response = await tracer.startActiveSpan(
          `chat ${model}`,
          {
            kind: SpanKind.CLIENT,
            attributes: {
              "gen_ai.operation.name": "chat",
              "gen_ai.system": "openai",
              "gen_ai.request.model": model,
              "server.address": "api.openai.com",
              "server.port": 443,
            },
          },
          async (chatSpan) => {
            // Capture input messages for full conversation visibility
            chatSpan.setAttribute("gen_ai.input.messages", JSON.stringify(
              messages.map((m) => ({
                role: m.role,
                parts: [{ type: "text", text: m.content ?? "" }],
              }))
            ));

            const resp = await client.chat.completions.create({ model, messages, tools });
            chatSpan.setAttributes({
              "gen_ai.response.model": resp.model,
              "gen_ai.usage.input_tokens": resp.usage.prompt_tokens,
              "gen_ai.usage.output_tokens": resp.usage.completion_tokens,
              "gen_ai.response.finish_reasons": [resp.choices[0].finish_reason],
            });
            totalInput += resp.usage.prompt_tokens;
            totalOutput += resp.usage.completion_tokens;

            // Capture output messages — model response + any tool call requests
            const outputParts = [];
            const msg = resp.choices[0].message;
            if (msg.content) {
              outputParts.push({ type: "text", text: msg.content });
            }
            if (msg.tool_calls) {
              for (const tc of msg.tool_calls) {
                outputParts.push({
                  type: "tool_call", id: tc.id,
                  name: tc.function.name,
                  arguments: tc.function.arguments,
                });
              }
            }
            chatSpan.setAttribute("gen_ai.output.messages", JSON.stringify(
              [{ role: "assistant", parts: outputParts }]
            ));

            chatSpan.end();
            return resp;
          }
        );
        // chat span is now closed

        if (response.choices[0].finish_reason === "tool_calls") {
          // execute_tool spans are siblings of chat, children of invoke_agent
          for (const tc of response.choices[0].message.tool_calls) {
            await tracer.startActiveSpan(
              `execute_tool ${tc.function.name}`,
              {
                kind: SpanKind.INTERNAL,
                attributes: {
                  "gen_ai.operation.name": "execute_tool",
                  "gen_ai.tool.name": tc.function.name,
                  "gen_ai.tool.call.id": tc.id,
                  "gen_ai.agent.name": agentName,
                  "gen_ai.conversation.id": conversationId,
                },
              },
              async (toolSpan) => {
                const args = JSON.parse(tc.function.arguments);
                const result = await tools[tc.function.name](args);
                toolSpan.setAttribute("gen_ai.tool.call.result", JSON.stringify(result));
                messages.push({
                  role: "tool",
                  tool_call_id: tc.id,
                  content: JSON.stringify(result),
                });
                toolSpan.end();
              }
            );
          }
        } else {
          agentSpan.setAttributes({
            "gen_ai.usage.input_tokens": totalInput,
            "gen_ai.usage.output_tokens": totalOutput,
          });
          agentSpan.end();
          return response;
        }
      }
    }
  );
}
```

### Go

```go
func RunAgent(ctx context.Context, client *openai.Client, model string, messages []Message,
    tools []Tool, agentName, agentID, conversationID string) (*Response, error) {

    ctx, agentSpan := tracer.Start(ctx, "invoke_agent "+agentName,
        trace.WithSpanKind(trace.SpanKindClient),
        trace.WithAttributes(
            attribute.String("gen_ai.operation.name", "invoke_agent"),
            attribute.String("gen_ai.agent.name", agentName),
            attribute.String("gen_ai.agent.id", agentID),
            attribute.String("gen_ai.conversation.id", conversationID),
        ),
    )
    defer agentSpan.End()

    var totalInput, totalOutput int

    for {
        // chat span covers only the LLM inference
        chatCtx, chatSpan := tracer.Start(ctx, "chat "+model,
            trace.WithSpanKind(trace.SpanKindClient),
            trace.WithAttributes(
                attribute.String("gen_ai.operation.name", "chat"),
                attribute.String("gen_ai.system", "openai"),
                attribute.String("gen_ai.request.model", model),
                attribute.String("server.address", "api.openai.com"),
                attribute.Int("server.port", 443),
            ),
        )

        // Capture input messages for full conversation visibility
        inputJSON, _ := json.Marshal(messages)
        chatSpan.SetAttributes(attribute.String("gen_ai.input.messages", string(inputJSON)))

        resp, err := client.Chat(chatCtx, model, messages, tools)
        if err != nil {
            chatSpan.SetStatus(codes.Error, err.Error())
            chatSpan.SetAttributes(attribute.String("error.type", fmt.Sprintf("%T", err)))
            chatSpan.End()
            return nil, err
        }

        chatSpan.SetAttributes(
            attribute.String("gen_ai.response.model", resp.Model),
            attribute.StringSlice("gen_ai.response.finish_reasons", []string{resp.FinishReason}),
            attribute.Int("gen_ai.usage.input_tokens", resp.Usage.InputTokens),
            attribute.Int("gen_ai.usage.output_tokens", resp.Usage.OutputTokens),
        )
        totalInput += resp.Usage.InputTokens
        totalOutput += resp.Usage.OutputTokens

        // Capture output messages — model response + any tool call requests
        outputJSON, _ := json.Marshal(resp.Message)
        chatSpan.SetAttributes(attribute.String("gen_ai.output.messages", string(outputJSON)))

        chatSpan.End()
        // chat span is now closed

        if resp.FinishReason == "tool_calls" {
            for _, tc := range resp.ToolCalls {
                // execute_tool spans are siblings of chat, children of invoke_agent
                _, toolSpan := tracer.Start(ctx, "execute_tool "+tc.Name,
                    trace.WithSpanKind(trace.SpanKindInternal),
                    trace.WithAttributes(
                        attribute.String("gen_ai.operation.name", "execute_tool"),
                        attribute.String("gen_ai.tool.name", tc.Name),
                        attribute.String("gen_ai.tool.call.id", tc.ID),
                        attribute.String("gen_ai.agent.name", agentName),
                        attribute.String("gen_ai.conversation.id", conversationID),
                    ),
                )
                result, err := tools[tc.Name](ctx, tc.Args)
                if err != nil {
                    toolSpan.SetStatus(codes.Error, err.Error())
                    toolSpan.SetAttributes(attribute.String("error.type", fmt.Sprintf("%T", err)))
                }
                resultJSON, _ := json.Marshal(result)
                toolSpan.SetAttributes(attribute.String("gen_ai.tool.call.result", string(resultJSON)))
                toolSpan.End()

                messages = append(messages, Message{Role: "tool", ToolCallID: tc.ID, Content: string(resultJSON)})
            }
        } else {
            agentSpan.SetAttributes(
                attribute.Int("gen_ai.usage.input_tokens", totalInput),
                attribute.Int("gen_ai.usage.output_tokens", totalOutput),
            )
            return resp, nil
        }
    }
}
```

### Flushing After Agent Invocation

The tool-calling loop examples above produce spans buffered by `BatchSpanProcessor`.
**Always force-flush after the top-level agent call returns** to guarantee export.

#### Python

```python
# After the agent loop completes:
result = run_agent(client, model, messages, tools, "research-agent", "ra-1", "conv-123")
span_processor.force_flush()  # ensure all spans are exported
```

#### Node.js

```typescript
// After the agent loop completes:
const result = await runAgent(client, model, messages, tools, "research-agent", "ra-1", "conv-123");
await spanProcessor.forceFlush();  // ensure all spans are exported
```

#### Go

```go
// After the agent loop completes:
resp, err := RunAgent(ctx, client, model, messages, tools, "research-agent", "ra-1", "conv-123")
spanProcessor.ForceFlush(ctx) // ensure all spans are exported
```

Do NOT call `forceFlush()` inside the agent loop (per chat turn) — it adds unnecessary
latency. Flush once at the outer call boundary.

Resulting trace shape:
```
invoke_agent research-agent          (CLIENT)
├── chat gpt-4                       (CLIENT, inference #1)
├── execute_tool search_web          (INTERNAL)
├── chat gpt-4                       (CLIENT, inference #2)
├── execute_tool read_page           (INTERNAL)
└── chat gpt-4                       (CLIENT, final response)
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

- Set `error.type` on **every** error path — exceptions (`type(e).__name__`) and
  non-exception error results (`"ToolExecutionError"`)
- Set span status to ERROR
- Record exceptions for stack traces (`span.record_exception(e)` / `span.RecordError(err)`)
- Let exceptions propagate — don't swallow errors silently
