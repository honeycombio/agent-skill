# Agent and Tool Trace Patterns

Trace structures for common GenAI agent architectures. These diagrams show how spans
compose to create observable agent systems.

## Tool-Calling Loop

The most common pattern: model requests tool calls, results feed back into the next
inference.

```
invoke_agent research-agent          (CLIENT, root)
├── chat gpt-4                       (CLIENT, inference #1)
├── execute_tool search_web          (INTERNAL)
├── chat gpt-4                       (CLIENT, inference #2 with tool results)
├── execute_tool read_page           (INTERNAL)
├── chat gpt-4                       (CLIENT, inference #3 with tool results)
└── [final response — no more tool calls]
```

Key attributes on `invoke_agent`:
- `gen_ai.agent.name`: `"research-agent"`
- `gen_ai.conversation.id`: ties together multi-turn context
- `gen_ai.usage.input_tokens`: total across all child inferences
- `gen_ai.usage.output_tokens`: total across all child inferences

Key attributes on each `chat`:
- `gen_ai.request.model`, `gen_ai.response.finish_reasons`
- `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` per call

Key attributes on each `execute_tool`:
- `gen_ai.tool.name`, `gen_ai.tool.call.id`
- `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result` (opt-in)

**Detecting retry loops**: If `invoke_agent` has many `execute_tool` children with the
same `gen_ai.tool.name`, the model may be stuck. Query: GROUP BY `gen_ai.tool.name`,
COUNT, WHERE parent span is `invoke_agent` with high child count.

## Multi-Turn Conversation

Each user turn triggers a new `invoke_agent` or `chat` span. The
`gen_ai.conversation.id` ties turns together.

```
[Turn 1]
invoke_agent assistant                (CLIENT)
├── chat claude-sonnet-4-5-20250929              (CLIENT)
└── execute_tool calculator           (INTERNAL)

[Turn 2 — same conversation.id]
invoke_agent assistant                (CLIENT)
├── chat claude-sonnet-4-5-20250929              (CLIENT)
└── [direct response, no tools]

[Turn 3 — same conversation.id]
invoke_agent assistant                (CLIENT)
├── chat claude-sonnet-4-5-20250929              (CLIENT)
├── execute_tool search_db            (INTERNAL)
└── chat claude-sonnet-4-5-20250929              (CLIENT, with tool results)
```

Correlate across turns: GROUP BY `gen_ai.conversation.id` to see full conversation
cost, latency, and tool usage patterns.

## Nested Agents (Delegation)

An agent delegates sub-tasks to specialized agents. Parent `invoke_agent` contains
child `invoke_agent` spans.

```
invoke_agent orchestrator             (CLIENT, root)
├── chat gpt-4                        (CLIENT, decides to delegate)
├── invoke_agent researcher           (INTERNAL, sub-agent)
│   ├── chat gpt-4                    (CLIENT)
│   ├── execute_tool search_web       (INTERNAL)
│   └── chat gpt-4                    (CLIENT)
├── invoke_agent writer               (INTERNAL, sub-agent)
│   ├── chat gpt-4                    (CLIENT)
│   └── [generates content]
└── chat gpt-4                        (CLIENT, final synthesis)
```

**Detecting deadlocks**: If two `invoke_agent` spans at the same level have span links
to each other and one times out (`error.type=TimeoutError`), agents may be waiting on
each other. Check `gen_ai.output.messages` for circular delegation patterns.

## Workflow Pattern

Deterministic steps with GenAI calls at specific points.

```
invoke_workflow content-pipeline      (INTERNAL, root)
├── retrieval knowledge-base          (CLIENT, fetch context)
├── chat gpt-4                        (CLIENT, generate draft)
├── invoke_agent reviewer             (INTERNAL, quality check)
│   ├── chat gpt-4                    (CLIENT)
│   └── [evaluation result event]
└── chat gpt-4                        (CLIENT, final edit)
```

Workflows differ from agents: the orchestration is code-driven (deterministic), not
model-driven (stochastic). The `invoke_workflow` span is INTERNAL because the code
controls execution flow.

## RAG Pattern

Retrieval-Augmented Generation: retrieve context, then generate.

```
chat gpt-4                            (CLIENT, root — or invoke_agent)
├── retrieval product-docs            (CLIENT, vector search)
├── retrieval faq-database            (CLIENT, second data source)
└── [generation uses retrieved context]
```

Key attributes on `retrieval`:
- `gen_ai.data_source.id`: identifies which data source
- `server.address`, `server.port`: vector DB connection
- Custom: `gen_ai.retrieval.result_count` for number of chunks returned

## Parallel Tool Execution

Model requests multiple tools simultaneously.

```
chat gpt-4                            (CLIENT)
├── execute_tool get_weather          (INTERNAL, concurrent)
├── execute_tool get_stock_price      (INTERNAL, concurrent)
└── execute_tool get_news             (INTERNAL, concurrent)
```

All three `execute_tool` spans share the same parent and may overlap in time. The
trace waterfall shows them running in parallel.

## Agent with Evaluation

Agent output gets scored before returning to user.

```
invoke_agent qa-assistant             (CLIENT, root)
├── retrieval knowledge-base          (CLIENT)
├── chat gpt-4                        (CLIENT, generate answer)
├── gen_ai.evaluation.result          (EVENT on chat span)
│   name: "relevance"
│   score.value: 0.92
│   score.label: "pass"
└── [return answer if evaluation passes]
```

If evaluation fails, the agent may re-query or refine — creating additional child spans.

## Key Querying Patterns

**Cost per agent**: GROUP BY `gen_ai.agent.name`, SUM(`gen_ai.usage.input_tokens`),
SUM(`gen_ai.usage.output_tokens`)

**Tool failure rate**: GROUP BY `gen_ai.tool.name`, COUNT, WHERE `error.type` EXISTS

**Conversation cost**: GROUP BY `gen_ai.conversation.id`,
SUM(`gen_ai.usage.input_tokens`)

**Slowest tools**: GROUP BY `gen_ai.tool.name`, P99(duration_ms)

**Agent loop detection**: WHERE `gen_ai.operation.name` = `invoke_agent` AND child
count > 10, then inspect child tool names for repetition
