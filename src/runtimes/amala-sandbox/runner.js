#!/usr/bin/env node

/**
 * Shizuku Sandbox Runtime using vm2
 * Runs untrusted JavaScript code in a secure, isolated environment
 */

const fs = require('fs');
const path = require('path');
const { VM } = require('vm2');

// Parse command line arguments
const args = process.argv.slice(2);
const scriptPath = args[0] || '';
const timeoutMs = parseInt(args[1]) || 30000;

// Configuration
const CONFIG = {
  TIMEOUT_MS: Math.min(timeoutMs, 45000), // Max 45 seconds
  MAX_MEMORY_MB: 256,
  SANDBOX_GLOBALS: {
    // Safe globals to expose
    console: true,
    Math: true,
    JSON: true,
    Array: true,
    Object: true,
    String: true,
    Number: true,
    Boolean: true,
    Date: true,
    Buffer: true,
  },
};

/**
 * Execute code safely within vm2 sandbox
 */
async function executeInSandbox(code) {
  const startTime = Date.now();
  
  try {
    // Capture output
    const capturedOutput = [];
    const sandbox = {
      console: {
        log: (...args) => capturedOutput.push(args.map(String).join(' ')),
        error: (...args) => capturedOutput.push(`[ERROR] ${args.map(String).join(' ')}`),
        warn: (...args) => capturedOutput.push(`[WARN] ${args.map(String).join(' ')}`),
        info: (...args) => capturedOutput.push(`[INFO] ${args.map(String).join(' ')}`),
        debug: (...args) => capturedOutput.push(`[DEBUG] ${args.map(String).join(' ')}`),
      },
      Math: Math,
      JSON: JSON,
      Array: Array,
      Object: Object,
      String: String,
      Number: Number,
      Boolean: Boolean,
      Date: Date,
      Buffer: Buffer,
    };

    // Create VM with strict options
    const vm = new VM({
      timeout: CONFIG.TIMEOUT_MS,
      sandbox: sandbox,
      eval: false,
      wasm: false,
      fixAsync: true,
    });

    // Execute code
    const result = vm.run(code, {
      timeout: CONFIG.TIMEOUT_MS,
      filename: 'sandbox.js',
    });

    const duration = Date.now() - startTime;

    return {
      ok: true,
      engine: 'vm2-sandbox',
      return_code: 0,
      stdout: capturedOutput.join('\n'),
      stderr: '',
      timed_out: false,
      duration_ms: duration,
      warning: '',
      combined_output: capturedOutput.join('\n'),
      result: result !== undefined ? String(result) : '',
    };
  } catch (err) {
    const duration = Date.now() - startTime;
    const isTimeout = err.message.includes('Script execution timed out');

    return {
      ok: false,
      engine: 'vm2-sandbox',
      return_code: -1,
      stdout: '',
      stderr: err.message || String(err),
      timed_out: isTimeout,
      duration_ms: duration,
      warning: isTimeout ? 'Code execution exceeded timeout limit' : '',
      combined_output: `Error: ${err.message || String(err)}`,
      result: null,
    };
  }
}

/**
 * Read script from file
 */
async function readScript(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf-8');
  } catch (err) {
    throw new Error(`Failed to read script file: ${err.message}`);
  }
}

/**
 * Main execution entry point
 */
async function main() {
  try {
    // Handle different input modes
    let code = '';

    if (scriptPath && scriptPath !== '--test') {
      // Read from file
      code = await readScript(scriptPath);
    } else if (scriptPath === '--test') {
      // Test mode
      code = `
        console.log('Test execution successful');
        const result = 2 + 2;
        console.log('2 + 2 =', result);
        result;
      `;
    } else {
      // Read from stdin
      code = fs.readFileSync(0, 'utf-8');
    }

    // Execute in sandbox
    const result = await executeInSandbox(code);

    // Output JSON result
    console.log(JSON.stringify(result, null, 2));
    process.exit(result.ok ? 0 : 1);
  } catch (err) {
    const output = {
      ok: false,
      engine: 'vm2-sandbox',
      return_code: -1,
      stdout: '',
      stderr: err.message || String(err),
      timed_out: false,
      duration_ms: 0,
      warning: 'Fatal error in sandbox initialization',
      combined_output: `Fatal Error: ${err.message || String(err)}`,
    };

    console.log(JSON.stringify(output, null, 2));
    process.exit(1);
  }
}

main().catch(err => {
  console.error(JSON.stringify({
    ok: false,
    engine: 'vm2-sandbox',
    return_code: -1,
    stderr: err.message,
    combined_output: `Uncaught error: ${err.message}`,
  }));
  process.exit(1);
});
