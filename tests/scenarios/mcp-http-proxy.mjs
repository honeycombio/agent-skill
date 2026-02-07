#!/usr/bin/env node
// Minimal MCP stdio-to-HTTP proxy for CI.
// Bridges stdin/stdout to a Streamable HTTP MCP server with Bearer auth.
// No OAuth discovery, no external dependencies — just Node.js built-in fetch.
//
// Usage: node mcp-http-proxy.mjs <bearer-token> [server-url]
//    or: HONEYCOMB_API_KEY=xxx node mcp-http-proxy.mjs

const API_KEY = process.argv[2] || process.env.HONEYCOMB_API_KEY;
const MCP_URL = process.argv[3] || process.env.MCP_SERVER_URL || 'https://mcp.honeycomb.io/mcp';

process.stderr.write(`[mcp-http-proxy] starting, url=${MCP_URL}, key=${API_KEY ? 'set' : 'MISSING'}\n`);

if (!API_KEY) {
  process.stderr.write('[mcp-http-proxy] Error: pass API key as argv[2] or HONEYCOMB_API_KEY env\n');
  process.exit(1);
}

let sessionId = null;
let buffer = '';

// Start listening on stdin immediately — no network calls first.
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  buffer += chunk;
  let idx;
  while ((idx = buffer.indexOf('\n')) !== -1) {
    const line = buffer.slice(0, idx);
    buffer = buffer.slice(idx + 1);
    if (line.trim()) {
      try {
        const msg = JSON.parse(line);
        handleMessage(msg).catch((err) => {
          process.stderr.write(`Proxy error: ${err.message}\n`);
        });
      } catch (err) {
        process.stderr.write(`JSON parse error: ${err.message}\n`);
      }
    }
  }
});

process.stdin.on('end', () => {
  process.exit(0);
});

async function handleMessage(message) {
  const headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/event-stream',
    'Authorization': `Bearer ${API_KEY}`,
  };
  if (sessionId) {
    headers['mcp-session-id'] = sessionId;
  }

  const response = await fetch(MCP_URL, {
    method: 'POST',
    headers,
    body: JSON.stringify(message),
  });

  // Track session ID from server.
  const sid = response.headers.get('mcp-session-id');
  if (sid) {
    sessionId = sid;
  }

  if (!response.ok) {
    const text = await response.text().catch(() => '');
    process.stderr.write(`HTTP ${response.status}: ${text}\n`);
    // Send JSON-RPC error response if this was a request (has id).
    if (message.id !== undefined) {
      const errResp = {
        jsonrpc: '2.0',
        id: message.id,
        error: { code: -32000, message: `HTTP ${response.status}: ${text.slice(0, 200)}` },
      };
      process.stdout.write(JSON.stringify(errResp) + '\n');
    }
    return;
  }

  // 202 Accepted = notification acknowledged, no response body.
  if (response.status === 202) {
    return;
  }

  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('text/event-stream')) {
    await handleSSE(response);
  } else {
    const data = await response.json();
    const messages = Array.isArray(data) ? data : [data];
    for (const msg of messages) {
      process.stdout.write(JSON.stringify(msg) + '\n');
    }
  }
}

async function handleSSE(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let sseBuf = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    sseBuf += decoder.decode(value, { stream: true });

    // Split on double-newline (SSE event boundary).
    const parts = sseBuf.split('\n\n');
    sseBuf = parts.pop(); // keep incomplete tail

    for (const part of parts) {
      if (!part.trim()) continue;
      // Extract event ID for session tracking.
      const idLine = part.split('\n').find((l) => l.startsWith('id: ') || l.startsWith('id:'));
      // Extract data lines and concatenate.
      const dataLines = part.split('\n').filter((l) => l.startsWith('data: ') || l.startsWith('data:'));
      const data = dataLines.map((l) => l.replace(/^data:\s?/, '')).join('\n');
      if (data.trim()) {
        try {
          const msg = JSON.parse(data);
          process.stdout.write(JSON.stringify(msg) + '\n');
        } catch {
          // Not valid JSON — skip.
        }
      }
    }
  }

  // Process any remaining buffer.
  if (sseBuf.trim()) {
    const dataLines = sseBuf.split('\n').filter((l) => l.startsWith('data: ') || l.startsWith('data:'));
    const data = dataLines.map((l) => l.replace(/^data:\s?/, '')).join('\n');
    if (data.trim()) {
      try {
        const msg = JSON.parse(data);
        process.stdout.write(JSON.stringify(msg) + '\n');
      } catch {
        // Not valid JSON — skip.
      }
    }
  }
}
