# Lambda Instrumentation Patterns (Node.js / TypeScript)

Patterns for instrumenting AWS Lambda functions with OpenTelemetry. Lambda's
execution model introduces constraints that don't apply to long-running servers:
execution freezes when the handler promise resolves, cold starts are expensive,
and there are no HTTP headers to propagate context over direct Lambda invocations.

## Choosing an Approach: OTel Layer vs Manual SDK Setup

There are two fundamentally different ways to instrument a Lambda function. The
choice comes down to where you want to pay the latency cost.

| | AWS Managed OTel Layer | Manual SDK Setup |
| :--- | :--- | :--- |
| Cold start overhead | Higher (~2–5 s extra) | Lower |
| Per-request latency | None — export happens after response | Added — `forceFlush()` blocks the response |
| Code complexity | Less — layer handles SDK init and export | More — full SDK wiring in your code |
| Control over SDK config | Limited | Full |

**When to prefer the OTel Layer:**

- Cold starts are infrequent or not important (async workflows, scheduled jobs, or when using provisioned concurrency)
- Per-request latency budget is tight (user-facing APIs)
- You want minimal instrumentation code
- The OTLP endpoint is outside your Lambda's AWS region and you can't or don't want to run an Open Telemetry Collector in the region. — `forceFlush()` in the manual SDK setup incurs a full cross-region HTTPS round-trip on every invocation before the response can be returned to the client, which can add hundreds of milliseconds per request

**When to prefer Manual SDK Setup:**

- Cold start latency is critical (latency-sensitive functions hit often)
- You need fine-grained control over sampling, resource attributes, or processors

**Ask the developer which trade-off matters more before choosing an approach.**

---

## Approach 1: AWS Managed OTel Layer

The [AWS Distro for OpenTelemetry (ADOT) Lambda layer](https://github.com/aws-observability/aws-otel-lambda)
bundles an OTel Collector sidecar that runs in the Lambda execution environment.
It intercepts OTLP exports from the SDK and forwards them to the OTLP endpoint
*after* the function response has been returned to the client — so telemetry
export does not add to request latency.

### Add the Layer and Configure Environment Variables

Find the correct layer ARN for your region and runtime at
<https://github.com/aws-observability/aws-otel-lambda/releases>.

In CDK:

```typescript
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as cdk from 'aws-cdk-lib';

const fn = new NodejsFunction(this, 'Fn', {
  runtime: lambda.Runtime.NODEJS_20_X,
  timeout: cdk.Duration.seconds(15),
  layers: [
    lambda.LayerVersion.fromLayerVersionArn(this, 'OtelLayer',
      'arn:aws:lambda:us-east-1:901920570463:layer:aws-otel-nodejs-amd64-ver-1-30-1:1'
      // ↑ replace with the latest ARN for your region and architecture
    ),
  ],
  environment: {
    AWS_LAMBDA_EXEC_WRAPPER:       '/opt/otel-handler',
    OTEL_EXPORTER_OTLP_ENDPOINT:   'https://your-otlp-endpoint',  // Honeycomb: https://api.honeycomb.io, or your OTel Collector URL
    OTEL_EXPORTER_OTLP_HEADERS:    'x-honeycomb-team=YOUR_API_KEY', // omit if using a Collector that handles auth
    OTEL_SERVICE_NAME:             'my-function',
    OTEL_PROPAGATORS:              'tracecontext',
  },
  bundling: {
    externalModules: ['@aws-sdk/*'],
    sourceMap: true,
  },
});
```

`AWS_LAMBDA_EXEC_WRAPPER=/opt/otel-handler` tells the layer to wrap the Node.js
handler — it initialises the OTel SDK automatically before your code runs.

### Dependencies

With the layer handling SDK init and export, you only need the API package for
custom spans and attributes:

```bash
npm install @opentelemetry/api
```

You do **not** need `sdk-trace-node`, `sdk-trace-base`, or the OTLP exporter —
those are provided by the layer.

### Handler Code (no forceFlush needed)

This is just an example of how to create a span if needed. By default the layer creates a span already, so it isn't needed to create a span for the entire handler method.

```typescript
import { trace, SpanStatusCode } from '@opentelemetry/api';

const tracer = trace.getTracer('my-function');

export async function handler(event: any) {
  return tracer.startActiveSpan('my-operation', async (span) => {
    try {
      // … do work …
      return result;
    } catch (err) {
      span.recordException(err as Error);
      span.setStatus({ code: SpanStatusCode.ERROR });
      throw err;
    } finally {
      span.end();
      // No forceFlush() needed — the layer flushes after the response is returned
    }
  });
}
```

### Cold Start Impact

The layer adds approximately 2–5+ seconds to cold starts. For latency-sensitive
functions that are invoked frequently (so cold starts are rare), this is usually
acceptable. For functions where cold starts happen on every invocation (e.g.,
low-traffic functions with short TTLs), evaluate whether that overhead is tolerable.

Provisioned Concurrency eliminates cold starts entirely if the overhead is not
acceptable.

---

## Approach 2: Manual SDK Setup

Set up the OTel SDK directly in your function code. Gives full control but
requires calling `forceFlush()` before the handler returns, which adds latency
on every invocation.

### Manual SDK Dependencies

```bash
npm install @opentelemetry/sdk-trace-node \
            @opentelemetry/sdk-trace-base \
            @opentelemetry/exporter-trace-otlp-proto \
            @opentelemetry/resources \
            @opentelemetry/core \
            @opentelemetry/api
```

Use `@opentelemetry/exporter-trace-otlp-proto` (protobuf over HTTP) rather
than the gRPC exporter — gRPC adds significant cold-start overhead in Lambda.

### SDK 2.x API (breaking changes from 1.x)

OTel Node SDK 2.x changed two construction APIs that matter for Lambda:

```typescript
import { NodeTracerProvider } from '@opentelemetry/sdk-trace-node';
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-proto';
import { resourceFromAttributes } from '@opentelemetry/resources'; // not new Resource()
import { W3CTraceContextPropagator } from '@opentelemetry/core';

const provider = new NodeTracerProvider({
  resource: resourceFromAttributes({ 'service.name': 'my-function' }), // not new Resource()
  spanProcessors: [new BatchSpanProcessor(new OTLPTraceExporter())],   // in constructor, not addSpanProcessor()
});
provider.register({ propagator: new W3CTraceContextPropagator() });
```

In SDK 1.x, `spanProcessors` was not a constructor option — you called
`provider.addSpanProcessor()` after construction. In 2.x, processors passed in
the constructor are the only supported path.

### Singleton Init Pattern

Call `initTelemetry()` at **module scope**, not inside the handler. Lambda reuses
the execution environment across warm invocations — re-initialising on every call
leaks providers and re-registers propagators.

```typescript
// ✅ module-level: runs once on cold start, no-op on warm invocations
let provider: NodeTracerProvider | null = null;

export function initTelemetry(): void {
  if (provider) return; // guard: no-op on warm invocations
  provider = new NodeTracerProvider({ … });
  provider.register({ propagator: new W3CTraceContextPropagator() });
}

initTelemetry(); // ← called at module load, outside the handler

export async function handler(event, ctx) { … }
```

### Resource Attributes from Lambda Env Vars

AWS injects these env vars automatically — wire them to `faas.*` semantic conventions:

```typescript
resourceFromAttributes({
  'service.name':     process.env.OTEL_SERVICE_NAME ?? 'unknown',
  'cloud.provider':   'aws',
  'cloud.region':     process.env.AWS_REGION ?? 'unknown',
  'faas.name':        process.env.AWS_LAMBDA_FUNCTION_NAME ?? 'unknown',
  'faas.version':     process.env.AWS_LAMBDA_FUNCTION_VERSION ?? '$LATEST',
})
```

### Critical: forceFlush Before Returning

`BatchSpanProcessor` queues spans in memory and flushes on a background timer.
When the handler promise resolves, Lambda **freezes the process** — the timer never
fires and any queued spans are silently dropped.

Call `provider.forceFlush()` in the handler's `finally` block before returning:

```typescript
export async function handler(event, ctx) {
  return tracer.startActiveSpan('my-operation', async (span) => {
    try {
      // … do work …
      return result;
    } catch (err) {
      span.recordException(err);
      span.setStatus({ code: SpanStatusCode.ERROR });
      throw err;
    } finally {
      span.end();
      await provider.forceFlush(); // ← must come before the function returns
    }
  });
}
```

This is the single most common cause of missing spans in Lambda. There is no
error — the function succeeds, the spans are created, but they never leave the
process.

**Latency note:** `forceFlush()` performs a synchronous HTTPS POST to the OTLP
endpoint before the handler returns. The round-trip cost depends entirely on
where the endpoint is relative to the Lambda:

- **OTel Collector in the same AWS region** (e.g. running on ECS or EC2 in the
  same VPC): typically 1–5 ms — negligible.
- **OTLP endpoint in the same AWS region but outside the VPC** (e.g. a managed
  service in the same region): typically 20–50 ms per invocation.
- **OTLP endpoint in a different region or continent**: the round-trip can add
  200–500 ms or more to every request.

Running a regional OTel Collector sidecar is the most effective way to keep
`forceFlush()` latency low while retaining the Manual SDK approach. Factor
the expected round-trip into your timeout sizing.

### Timeout Sizing

The 3-second default timeout is too short once OTel is added. Two costs compound:

- **Cold start**: the OTLP exporter opens an HTTPS connection to the endpoint
- **Per-invocation**: `forceFlush()` awaits a real HTTPS POST before returning

Practical minimums with a remote OTLP endpoint (adjust down if using a same-region Collector):

| Function role | Recommended timeout |
| :--- | :--- |
| Leaf function (DynamoDB / simple logic only) | **15s** |
| Orchestrator (invokes another Lambda + flushes) | **30s** |
| Authorizer | **15s** |

In CDK:

```typescript
import * as cdk from 'aws-cdk-lib';

new NodejsFunction(this, 'Fn', {
  timeout: cdk.Duration.seconds(30),
  // …
});
```

### Bundling — Exclude AWS SDK

Lambda Node.js 18+ runtimes include `@aws-sdk/*` v3. Mark it as external to keep
bundle size small and cold-start fast:

```typescript
// CDK NodejsFunction (esbuild under the hood)
bundling: {
  externalModules: ['@aws-sdk/*'],
  sourceMap: true,
}
```

Do **not** mark `@opentelemetry/*` as external — it must be bundled because the
Lambda runtime does not include it (unlike the OTel Layer approach).

---

## Common Patterns (Both Approaches)

### Header Normalisation (SAM Local vs API Gateway)

API Gateway v1 lowercases all HTTP headers in production (`traceparent`,
`authorization`). SAM Local uses a Flask dev server that title-cases them
(`Traceparent`, `Authorization`). The W3CTraceContextPropagator always looks
for the lowercase `traceparent` key.

**Always normalise header keys to lowercase** before calling
`propagation.extract()`:

```typescript
import { propagation, ROOT_CONTEXT, context } from '@opentelemetry/api';

export function extractTraceFromHeaders(
  headers: Record<string, string | undefined> | null | undefined,
): ReturnType<typeof context.active> {
  if (!headers) return ROOT_CONTEXT;
  const normalized: Record<string, string> = {};
  for (const [k, v] of Object.entries(headers)) {
    if (v !== undefined) normalized[k.toLowerCase()] = v;
  }
  return propagation.extract(ROOT_CONTEXT, normalized);
}

// In the handler:
const parentCtx = extractTraceFromHeaders(event.headers);
return otelContext.with(parentCtx, () => tracer.startActiveSpan(…));
```

Without this, traces connect correctly in production but appear as disconnected
roots when testing under SAM Local — a confusing local/prod discrepancy.

### Cross-Lambda Trace Propagation (Direct Invoke)

When invoking a Lambda function via the AWS SDK (`InvokeCommand`), there are no
HTTP headers — the payload is a raw JSON blob. Inject W3C context into a custom
field in the payload and extract it on the receiving side.

#### Caller (e.g. middleware Lambda)

```typescript
import { LambdaClient, InvokeCommand } from '@aws-sdk/client-lambda';
import { propagation, context } from '@opentelemetry/api';

const client = new LambdaClient({});

// Serialise the active trace context into the request payload
const carrier: Record<string, string> = {};
propagation.inject(context.active(), carrier);

const payload = { ...myRequest, traceContext: carrier };
const result = await client.send(new InvokeCommand({
  FunctionName: process.env.BACKEND_FUNCTION_NAME,
  InvocationType: 'RequestResponse',
  Payload: Buffer.from(JSON.stringify(payload)),
}));
```

#### Callee (e.g. backend Lambda)

```typescript
import { propagation, context, ROOT_CONTEXT } from '@opentelemetry/api';

export async function handler(event: MyRequest) {
  const parentCtx = event.traceContext
    ? propagation.extract(ROOT_CONTEXT, event.traceContext)
    : ROOT_CONTEXT;

  return context.with(parentCtx, () =>
    tracer.startActiveSpan('backend.invoke', async (span) => {
      // … this span is now a child of the middleware span …
    })
  );
}
```

### API Gateway Authorizer — Use REQUEST Type

`TOKEN` type authorizers receive only the `authorizationToken` value — no headers reach the function, so `traceparent` is unavailable and the authorizer span cannot join the caller's trace.

**Use `REQUEST` type authorizers** to receive the full header map:

```typescript
// AWS CDK
import { RequestAuthorizer, IdentitySource } from 'aws-cdk-lib/aws-apigateway';

new RequestAuthorizer(this, 'Auth', {
  handler: authorizerFn,
  identitySources: [IdentitySource.header('Authorization')],
  // identitySources controls the cache key — traceparent doesn't need to be here
  resultsCacheTtl: Duration.minutes(5),
});
```

In the authorizer handler, extract the token from `event.headers.Authorization`
(or the lowercase variant — apply the normalisation helper above):

```typescript
const token = event.headers?.Authorization?.replace(/^Bearer\s+/i, '')
           ?? event.headers?.authorization?.replace(/^Bearer\s+/i, '');
```
