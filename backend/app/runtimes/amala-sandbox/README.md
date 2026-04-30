# Amala-Sandbox Runtime for Shizuku

This directory contains the Node.js runtime for running untrusted JavaScript code in a secure, isolated environment using **amala-sandbox**.

## Features

- **Strict Execution Isolation**: Uses amala-sandbox to prevent access to dangerous APIs
- **Resource Limits**: Memory, CPU, and execution depth constraints
- **Timeout Protection**: Configurable timeout with 45-second hard limit
- **Safe Context**: Whitelisted globals only (Math, JSON, etc.)
- **Comprehensive Logging**: Captures stdout, stderr, and execution metadata

## Installation

```bash
npm install
```

This will install `amala-sandbox` and its dependencies.

## Usage

### Run a JavaScript file in sandbox:
```bash
node runner.js /path/to/script.js [timeout_ms]
```

### Run code from stdin:
```bash
echo "console.log(2 + 2)" | node runner.js
```

### Test mode:
```bash
node runner.js --test
```

## Security Model

### Allowed APIs
- `console.log/error/warn/info` (captured to stdout)
- `Math` object (all methods)
- `JSON` object (stringify, parse)
- `Array, Object, String, Number, Boolean` (basic types)
- `Date` object

### Blocked APIs
- `require()` - No external modules
- `process` - No process access
- `eval()`, `Function()` - No code generation
- `__dirname`, `__filename` - No path access
- `setTimeout/setInterval` - No event loop blocking
- Network APIs - No external connectivity
- File system APIs - No direct file access

### Docker Integration (Optional)
For additional OS-level isolation, run this via Docker:
```dockerfile
FROM node:20-alpine
WORKDIR /sandbox
COPY . .
RUN npm install
ENTRYPOINT ["node", "runner.js"]
```

## Configuration

Edit `runner.js` to adjust:
- `TIMEOUT_MS`: Max execution time (default: 30s, hard max: 45s)
- `MAX_MEMORY_MB`: Memory limit (default: 256MB)
- `MAX_EXECUTION_DEPTH`: Recursion depth limit (default: 100)

## Output Format

The runner returns JSON with the following structure:
```json
{
  "ok": true,
  "engine": "amala-sandbox",
  "return_code": 0,
  "stdout": "captured output",
  "stderr": "",
  "timed_out": false,
  "duration_ms": 125,
  "warning": "",
  "combined_output": "full output",
  "result": null
}
```

## Integration with Shizuku

The Python `agent_sandbox.py` will:
1. Write JavaScript code to a temporary file
2. Call this runner via subprocess
3. Parse JSON output
4. Return execution result to the agent

## Troubleshooting

### "amala-sandbox not found"
Run `npm install` to install dependencies.

### Timeout errors
Increase the timeout parameter: `node runner.js script.js 60000`

### Memory errors
The sandbox has a 256MB memory limit. For heavier workloads, this can be adjusted in Docker.

## Security Notes

- ⚠️ This is a **second-layer** sandbox. For maximum security, combine with Docker/OS-level isolation.
- ⚠️ Run this runner itself in a container for production use.
- ✅ No network access by default.
- ✅ No file system access except via whitelisted APIs.
- ✅ No process spawning capability.
