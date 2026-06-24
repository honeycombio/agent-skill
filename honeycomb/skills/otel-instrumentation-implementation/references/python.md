# Python — configuration

## Init path — match how the app is actually launched
Two ways to initialize, and the right one depends on the **launch command you don't control**:
- **`opentelemetry-instrument` wrapper** (zero-code auto-instrumentation) — only takes effect if the
  process is started *through* it. If the app is launched as plain `python -m …`, `uvicorn app:app`,
  `gunicorn`, etc. (and you can't change that), the wrapper never runs and nothing is instrumented.
- **On-import SDK setup** — call your `setup_otel()` at import of the app's entry module so it runs no
  matter how the process is started. **Prefer this** when you don't own the launch command. Make sure
  it runs *before* the framework/DB libraries are imported, so their instrumentation hooks attach.

## Exporter / transport — don't hardcode the gRPC (or HTTP) exporter class
Importing `opentelemetry.exporter.otlp.proto.grpc...` (or `...proto.http...`) and constructing it
directly **pins the transport and ignores `OTEL_EXPORTER_OTLP_PROTOCOL`** — so it silently drops all
telemetry when the endpoint speaks the other protocol. Instead:
- Prefer env-driven autoconfiguration (`opentelemetry-distro` / the SDK's autoconfigure), which picks
  the exporter from `OTEL_EXPORTER_OTLP_PROTOCOL`; or
- If you build providers by hand, select the exporter class **from** `OTEL_EXPORTER_OTLP_PROTOCOL`
  yourself (default `http/protobuf`), rather than importing one unconditionally.

## Dependencies — OTel packages can conflict with the app's existing pins
Adding `opentelemetry-distro` / instrumentation packages can be **unsatisfiable** against deps the app
already pins (e.g. an old `opentelemetry-*` pulled in transitively by another library). A broken
resolve means the app won't start at all. Before adding:
- Check existing OTel-related constraints in the project; pin compatible versions.
- If the full `distro` conflicts, install only the specific SDK + exporter + instrumentation packages
  you need rather than the umbrella.

## service.name
Set via `OTEL_SERVICE_NAME` in the launch script, or in the `Resource` you build in `setup_otel()`.
If you can't guarantee the launch env (see init path above), put a deterministic default on the
resource in code so it's never `unknown_service`.

## Stable semantic conventions
Set `OTEL_SEMCONV_STABILITY_OPT_IN=http,database` before instrumentation libraries import (env, or
`os.environ.setdefault(...)` at the very top of `setup_otel()` — it's read once at init).
