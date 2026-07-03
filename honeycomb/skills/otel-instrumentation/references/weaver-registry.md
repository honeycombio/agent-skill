# Authoring a weaver registry

Your telemetry is judged against a **weaver registry**: a manifest of every attribute you emit,
standard and custom. This file covers the *mechanics* of authoring one. The intent — extend an
existing registry, reuse standard attributes, mint new ones only when nothing fits — lives in the
skill (steps 3–5).

## Directory and file layout

Put the registry in its **own subdirectory** (e.g. `telemetry/registry/`), **never the repo root**.
Weaver treats the whole registry directory as the registry and chokes on any non-registry YAML it
finds there (a collector config, a linter config, …), which makes it fail to load the registry at
all. Name the manifest `manifest.yaml`.

## Manifest identity + dependencies

Identity fields live at the **top level**: `name`, and either `schema_url` or both
`schema_base_url` and `semconv_version`. Imported registries are declared in a top-level
**`dependencies:`** list (each entry a `name` and a `registry_path`). A minimal valid shape:

```yaml
name: <service>-registry
# Use your OWN schema_url host — NOT opentelemetry.io/schemas/... A schema_url under
# opentelemetry.io makes your registry share the upstream's identity and weaver fails with a
# "circular dependency" error.
schema_url: https://<your-app>/schemas/1.0.0
dependencies:
  - name: otel
    registry_path: https://github.com/open-telemetry/semantic-conventions.git[model]
```

## Importing standard namespaces

`dependencies:` makes the upstream conventions *resolvable*, but importing alone does **not**
reference them. Reference the standard namespaces you emit with a top-level **`imports:`** block (a
sibling of `groups:`, in any registry file). `imports:` pulls in **signals** — `spans`, `metrics`,
`events`, `entities` — by glob, and each imported signal transitively references its attributes:

```yaml
imports:
  spans:
    - http.*
    - db.*
  metrics:
    - http.*
    - db.*
```

Import the signal namespaces your telemetry actually uses (add `messaging.*`, `rpc.*`, etc. as they
apply).

## Attributes imports can't reach

`imports:` only takes signal types — there is no bare `attributes:` import — so standard attributes
in signal-less namespaces (e.g. `url.*`, `client.*`, `user_agent.*`) aren't covered this way. Add an
explicit `ref:` to each of those in a group. Walk the attributes your instrumentation actually emits
and make sure each one is either imported or explicitly ref'd.

## Don't forget the resource attributes

Every OTel SDK stamps a fixed set of **resource attributes** onto everything it exports —
`service.name`, `service.version`, `service.instance.id`, and the `telemetry.sdk.*` family — with no
code on your part. They are always present in the telemetry, so the registry must cover them too, or
the live-check flags each one as an attribute that "does not exist in the registry." Import them via
the `entities` signal (a sibling of `spans:`/`metrics:` under `imports:`) or `ref:` them explicitly:

```yaml
imports:
  entities:
    - service.*
    - telemetry.*
```

## Verify the import actually loaded

A `registries:` block (or any other misspelling of `dependencies:`/`imports:`) is **silently
ignored**, and `weaver registry check` still passes even when the import is wrong. So `check`
passing does **not** prove your imports resolved — confirm that the standard attributes you expect
are actually referenced before trusting the registry.

Confirm it in **one** `resolve` — don't re-run `check` repeatedly to poke at it. Resolve the registry
and look for a standard attribute you imported; a non-zero count proves the import landed:

```
weaver registry resolve --registry <registry-dir> --format json | grep -c '"http.route"'
```

Run `check` once (it's a static pass/fail) and `resolve` once (to confirm imports) — then move on.
