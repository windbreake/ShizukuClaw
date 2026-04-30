#!/usr/bin/env node
/**
 * TypeScript Syntax Checker
 * 
 * Usage: node ts-syntax-check.js <file.ts>
 * 
 * Checks TypeScript syntax WITHOUT module resolution.
 * Uses ts.transpileModule() which performs syntax-only transformation.
 * 
 * Exit codes:
 *   0 - Valid syntax
 *   1 - Syntax error (error message printed to stderr)
 *   2 - Usage error (missing file argument)
 */

import ts from 'typescript';
import fs from 'fs';
import path from 'path';

const file = process.argv[2];

if (!file) {
    console.error('Usage: node ts-syntax-check.js <file.ts>');
    process.exit(2);
}

// Read the file
let code;
try {
    code = fs.readFileSync(file, 'utf-8');
} catch (err) {
    console.error(`Cannot read file: ${err.message}`);
    process.exit(2);
}

// Use transpileModule for syntax-only checking (no module resolution)
const result = ts.transpileModule(code, {
    compilerOptions: {
        target: ts.ScriptTarget.ESNext,
        module: ts.ModuleKind.ESNext,
        strict: false,
        noImplicitAny: false,
        skipLibCheck: true,
        // These settings ensure we only check syntax, not types
        isolatedModules: true,
    },
    reportDiagnostics: true,
    fileName: path.basename(file),
});

// Check for diagnostics (syntax errors)
if (result.diagnostics && result.diagnostics.length > 0) {
    const diagnostic = result.diagnostics[0];
    let message;
    
    if (typeof diagnostic.messageText === 'string') {
        message = diagnostic.messageText;
    } else if (diagnostic.messageText.messageText) {
        message = diagnostic.messageText.messageText;
    } else {
        message = 'Unknown syntax error';
    }
    
    // Add line number if available
    if (diagnostic.file && diagnostic.start !== undefined) {
        const { line, character } = diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start);
        console.error(`Line ${line + 1}, Col ${character + 1}: ${message}`);
    } else {
        console.error(message);
    }
    
    process.exit(1);
}

// Valid syntax
process.exit(0);
