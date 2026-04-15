/**
 * Code Evaluator
 *
 * Validates generated code against acceptance criteria patterns.
 * Performs static analysis to check for correct/incorrect usage patterns.
 */

import ts from "typescript";
import type {
  AcceptanceCriteria,
  CodePattern,
  EvaluationResult,
  Finding,
  ValidationRule,
} from "./types.js";
import { Severity, createEvaluationResult, createFinding } from "./types.js";

// =============================================================================
// Types
// =============================================================================

interface CompiledPattern {
  section: string;
  regex: RegExp;
}

// =============================================================================
// CodeEvaluator
// =============================================================================

/**
 * Evaluates generated code against acceptance criteria.
 *
 * Performs:
 * - Import validation (correct modules used)
 * - Pattern matching (correct/incorrect patterns)
 * - Syntax validation (TypeScript, Python bracket balance)
 * - Best practice checks
 */
export class CodeEvaluator {
  private readonly criteria: AcceptanceCriteria;
  private correctRegexes: CompiledPattern[] = [];
  private incorrectRegexes: CompiledPattern[] = [];

  constructor(criteria: AcceptanceCriteria) {
    this.criteria = criteria;
    this.compilePatterns();
  }

  /**
   * Pre-compile regex patterns for efficiency.
   */
  private compilePatterns(): void {
    this.correctRegexes = [];
    this.incorrectRegexes = [];

    for (const pattern of this.criteria.correctPatterns) {
      const regex = this.codeToRegex(pattern.code);
      if (regex) {
        this.correctRegexes.push({ section: pattern.section, regex });
      }
    }

    for (const pattern of this.criteria.incorrectPatterns) {
      const regex = this.codeToRegex(pattern.code);
      if (regex) {
        this.incorrectRegexes.push({ section: pattern.section, regex });
      }
    }
  }

  /**
   * Convert a code snippet to a flexible regex pattern.
   */
  private codeToRegex(code: string): RegExp | null {
    // Escape special regex chars but keep structure
    let pattern = this.escapeRegex(code.trim());

    // Make whitespace flexible
    pattern = pattern.replace(/ +/g, "\\s+");
    pattern = pattern.replace(/\\n/g, "\\s*");

    // Make string quotes flexible
    pattern = pattern.replace(/"/g, '["\']');
    pattern = pattern.replace(/'/g, '["\']');

    try {
      return new RegExp(pattern, "ms"); // multiline, dotall
    } catch {
      return null;
    }
  }

  /**
   * Escape special regex characters.
   */
  private escapeRegex(str: string): string {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  /**
   * Evaluate code against acceptance criteria.
   */
  evaluate(code: string, scenario = ""): EvaluationResult {
    const result = createEvaluationResult(
      this.criteria.skillName,
      scenario,
      code
    );

    // Check for syntax errors first
    if (!this.checkSyntax(code, result)) {
      result.score = 0;
      return result;
    }

    // Check imports
    this.checkImports(code, result);

    // Check for incorrect patterns
    this.checkIncorrectPatterns(code, result);

    // Check for correct patterns
    this.checkCorrectPatterns(code, result);

    // Check rule-specific criteria
    for (const rule of this.criteria.rules) {
      this.checkRule(code, rule, result);
    }

    // Calculate score
    result.score = this.calculateScore(result);

    // Update passed status
    result.passed = !result.findings.some((f) => f.severity === Severity.ERROR);

    // Update counts
    result.errorCount = result.findings.filter(
      (f) => f.severity === Severity.ERROR
    ).length;
    result.warningCount = result.findings.filter(
      (f) => f.severity === Severity.WARNING
    ).length;

    return result;
  }

  /**
   * Check if code has valid syntax based on language.
   */
  private checkSyntax(code: string, result: EvaluationResult): boolean {
    const language = this.criteria.language.toLowerCase();

    if (language === "python") {
      // Check for bracket balance (can't parse Python AST from TypeScript)
      return this.checkBracketBalance(code, result, "Python");
    }

    if (language === "typescript") {
      // Use TypeScript compiler API for proper syntax checking
      return this.checkTypeScriptSyntax(code, result);
    }

    if (language === "csharp" || language === "java") {
      // Use bracket balance check for C# and Java
      return this.checkBracketBalance(code, result, language === "csharp" ? "C#" : "Java");
    }

    // Unknown language - skip validation
    return true;
  }

  /**
   * Check TypeScript syntax using the TypeScript compiler API.
   * Uses ts.transpileModule() which performs syntax-only transformation
   * WITHOUT module resolution, so Azure SDK imports won't cause errors.
   */
  private checkTypeScriptSyntax(code: string, result: EvaluationResult): boolean {
    // First do a quick bracket balance check
    if (!this.checkBracketBalance(code, result, "TypeScript")) {
      return false;
    }

    try {
      // Use transpileModule for syntax-only checking (no module resolution)
      const transpileResult = ts.transpileModule(code, {
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
        fileName: "code.ts",
      });

      // Check for diagnostics (syntax errors)
      const diagnostics = transpileResult.diagnostics;
      if (diagnostics && diagnostics.length > 0) {
        // Iterate through diagnostics to satisfy TypeScript's strict checking
        for (const diagnostic of diagnostics) {
          let message: string;

          if (typeof diagnostic.messageText === "string") {
            message = diagnostic.messageText;
          } else if (diagnostic.messageText?.messageText) {
            message = diagnostic.messageText.messageText;
          } else {
            message = "Unknown syntax error";
          }

          // Add line number if available
          let fullMessage = message;
          if (diagnostic.file && diagnostic.start !== undefined) {
            const { line, character } = diagnostic.file.getLineAndCharacterOfPosition(
              diagnostic.start
            );
            fullMessage = `Line ${line + 1}, Col ${character + 1}: ${message}`;
          }

          result.findings.push(
            createFinding({
              severity: Severity.ERROR,
              rule: "syntax",
              message: `TypeScript syntax error: ${fullMessage}`,
            })
          );
          
          // Only report first error
          break;
        }
        return false;
      }

      return true;
    } catch (error) {
      // If transpilation throws an unexpected error, treat as syntax error
      const errorMessage = error instanceof Error ? error.message : String(error);
      result.findings.push(
        createFinding({
          severity: Severity.ERROR,
          rule: "syntax",
          message: `TypeScript parsing failed: ${errorMessage}`,
        })
      );
      return false;
    }
  }

  /**
   * Check for balanced brackets, braces, and parentheses.
   * Used as a fallback or quick check for non-TypeScript languages.
   */
  private checkBracketBalance(
    code: string,
    result: EvaluationResult,
    languageName: string
  ): boolean {
    const openParens = (code.match(/\(/g) ?? []).length;
    const closeParens = (code.match(/\)/g) ?? []).length;
    const openBrackets = (code.match(/\[/g) ?? []).length;
    const closeBrackets = (code.match(/]/g) ?? []).length;
    const openBraces = (code.match(/\{/g) ?? []).length;
    const closeBraces = (code.match(/}/g) ?? []).length;

    const errors: string[] = [];

    if (openParens !== closeParens) {
      errors.push(`Mismatched parentheses: ${openParens} '(' vs ${closeParens} ')'`);
    }

    if (openBrackets !== closeBrackets) {
      errors.push(`Mismatched brackets: ${openBrackets} '[' vs ${closeBrackets} ']'`);
    }

    if (openBraces !== closeBraces) {
      errors.push(`Mismatched braces: ${openBraces} '{' vs ${closeBraces} '}'`);
    }

    if (errors.length > 0) {
      result.findings.push(
        createFinding({
          severity: Severity.ERROR,
          rule: "syntax",
          message: `${languageName} syntax error: ${errors.join("; ")}`,
        })
      );
      return false;
    }

    return true;
  }

  /**
   * Check import statements using regex matching.
   * Note: Without Python AST, we use regex-based matching.
   * 
   * IMPORTANT: Incorrect import patterns often involve COMBINATIONS of imports
   * (e.g., sync client + async credential). We only flag as incorrect when
   * ALL import lines in the pattern are present together.
   */
  private checkImports(code: string, result: EvaluationResult): void {
    const language = this.criteria.language.toLowerCase();

    // Extract actual imports from code
    const actualImports = new Set<string>();

    if (language === "python") {
      // Match "from X import Y" patterns
      const fromImportRegex = /^from\s+([\w.]+)\s+import\s+(.+)$/gm;
      let match: RegExpExecArray | null;

      while ((match = fromImportRegex.exec(code)) !== null) {
        const module = match[1];
        const names = match[2]?.split(",").map((n) => n.trim()) ?? [];
        for (const name of names) {
          // Remove any "as alias" parts
          const cleanName = name.split(/\s+as\s+/)[0]?.trim();
          if (cleanName && module) {
            actualImports.add(`from ${module} import ${cleanName}`);
          }
        }
      }
    }

    // Check incorrect import patterns from criteria
    // Only flag as incorrect when:
    // 1. ALL imports in the pattern are present together
    // 2. The pattern is IMPORT-ONLY (no non-import lines showing misuse)
    //    If pattern has non-import lines, it's handled by checkRule/patternMatches
    for (const pattern of this.criteria.incorrectPatterns) {
      if (!pattern.code.toLowerCase().includes("import")) {
        continue;
      }

      // Separate import lines from non-import lines in the pattern
      const patternImports: string[] = [];
      const nonImportLines: string[] = [];
      
      for (const line of pattern.code.split("\n")) {
        const trimmedLine = line.trim();
        if (trimmedLine.startsWith("#") || !trimmedLine) {
          continue;
        }
        if (
          trimmedLine.startsWith("from ") ||
          trimmedLine.startsWith("import ")
        ) {
          // Normalize whitespace
          const normalizedPattern = trimmedLine.split(/\s+/).join(" ");
          patternImports.push(normalizedPattern);
        } else {
          nonImportLines.push(trimmedLine);
        }
      }

      // Skip if no import lines found in pattern
      if (patternImports.length === 0) {
        continue;
      }

      // CRITICAL FIX: If pattern has non-import lines, skip here.
      // These "mixed patterns" (import + misuse) are handled by patternMatches()
      // which correctly requires ALL parts to match before flagging as incorrect.
      // Without this check, we'd flag valid imports as incorrect just because
      // they appear in an incorrect pattern that also shows their misuse.
      if (nonImportLines.length > 0) {
        continue;
      }

      // Check if ALL imports in the pattern are present in actual code
      const allPresent = patternImports.every((pi) => actualImports.has(pi));
      
      if (allPresent) {
        // All imports from the incorrect pattern are present together
        result.findings.push(
          createFinding({
            severity: Severity.ERROR,
            rule: "imports",
            message: `Incorrect import combination: ${patternImports.join(", ")}`,
            suggestion: `Check acceptance criteria section: ${pattern.section}`,
          })
        );
      }
    }
  }

  /**
   * Check for incorrect patterns in the code.
   */
  private checkIncorrectPatterns(
    code: string,
    result: EvaluationResult
  ): void {
    for (const { section, regex } of this.incorrectRegexes) {
      if (regex.test(code)) {
        result.matchedIncorrect.push(section);
        result.findings.push(
          createFinding({
            severity: Severity.ERROR,
            rule: `pattern:${section}`,
            message: `Incorrect pattern found from section: ${section}`,
            suggestion: "Review acceptance criteria for correct usage",
          })
        );
      }
    }
  }

  /**
   * Check for presence of correct patterns.
   */
  private checkCorrectPatterns(code: string, result: EvaluationResult): void {
    const matchedSections = new Set<string>();

    // First pass: try compiled regex (exact structure match)
    for (const { section, regex } of this.correctRegexes) {
      if (regex.test(code)) {
        result.matchedCorrect.push(section);
        matchedSections.add(section);
      }
    }

    // Second pass: flexible matching for unmatched patterns
    for (const pattern of this.criteria.correctPatterns) {
      if (!matchedSections.has(pattern.section)) {
        if (this.patternMatches(code, pattern, false)) {
          result.matchedCorrect.push(pattern.section);
          matchedSections.add(pattern.section);
        }
      }
    }
  }

  /**
   * Check code against a specific validation rule.
   */
  private checkRule(
    code: string,
    rule: ValidationRule,
    result: EvaluationResult
  ): void {
    // Check for incorrect patterns in this rule
    for (const pattern of rule.incorrectPatterns) {
      if (this.patternMatches(code, pattern, true)) {
        result.findings.push(
          createFinding({
            severity: Severity.ERROR,
            rule: rule.name,
            message: `Incorrect usage in ${rule.name}`,
            codeSnippet: pattern.code.slice(0, 100),
          })
        );
      }
    }

    // Check for required patterns
    for (const reqPattern of rule.requiredPatterns) {
      if (!code.includes(reqPattern)) {
        result.findings.push(
          createFinding({
            severity: Severity.WARNING,
            rule: rule.name,
            message: `Missing recommended pattern: ${reqPattern}`,
          })
        );
      }
    }
  }

  /**
   * Check if a code pattern matches in the generated code.
   *
   * Uses more precise matching:
   * - For imports: exact statement matching
   * - For incorrect patterns: EXACT matching (to catch specific errors)
   * - For correct patterns: FLEXIBLE matching (to allow variations)
   */
  private patternMatches(
    code: string,
    pattern: CodePattern,
    isIncorrect: boolean
  ): boolean {
    const patternCode = pattern.code.trim();

    // Remove comment lines from the pattern
    const codeLines = patternCode
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("#"));

    if (codeLines.length === 0) {
      return false;
    }

    // Separate import lines from non-import lines
    const importLines = codeLines.filter(
      (line) => line.startsWith("from ") || line.startsWith("import ")
    );
    const nonImportLines = codeLines.filter(
      (line) => !line.startsWith("from ") && !line.startsWith("import ")
    );

    // Case 1: Pattern has BOTH imports AND non-import code (mixed pattern)
    // This is critical for incorrect patterns that show: import X + misuse X
    // We must require ALL parts to match to avoid false positives
    if (importLines.length > 0 && nonImportLines.length > 0) {
      const importsMatch = this.importPatternMatches(code, importLines);
      if (!importsMatch) {
        return false;
      }
      // Also require the non-import lines to match
      if (isIncorrect) {
        return this.multiLinePatternMatchesExact(code, nonImportLines);
      } else {
        return this.multiLinePatternMatchesFlexible(code, nonImportLines);
      }
    }

    // Case 2: Import-only pattern
    if (importLines.length > 0) {
      return this.importPatternMatches(code, importLines);
    }

    // Case 3: Code-only pattern (no imports)
    if (isIncorrect) {
      // Incorrect patterns: use EXACT matching to catch specific errors
      return this.multiLinePatternMatchesExact(code, codeLines);
    } else {
      // Correct patterns: use FLEXIBLE matching to allow variations
      return this.multiLinePatternMatchesFlexible(code, codeLines);
    }
  }

  /**
   * Check if import patterns match in the code.
   *
   * For multi-line import patterns (combinations), ALL import lines must be present.
   * This is important for catching incorrect combinations like:
   *   - sync credential + async client
   *   - async credential + sync client
   */
  private importPatternMatches(code: string, importLines: string[]): boolean {
    const language = this.criteria.language.toLowerCase();
    if (language !== "python") {
      return false;
    }

    // Extract actual imports from code using regex
    const actualImports = new Set<string>();
    const fromImportRegex = /^from\s+([\w.]+)\s+import\s+(.+)$/gm;
    const importRegex = /^import\s+(.+)$/gm;

    let match: RegExpExecArray | null;
    while ((match = fromImportRegex.exec(code)) !== null) {
      const module = match[1];
      const names = match[2]?.split(",").map((n) => n.trim()) ?? [];
      for (const name of names) {
        const cleanName = name.split(/\s+as\s+/)[0]?.trim();
        if (cleanName && module) {
          actualImports.add(`from ${module} import ${cleanName}`);
        }
      }
    }

    while ((match = importRegex.exec(code)) !== null) {
      const names = match[1]?.split(",").map((n) => n.trim()) ?? [];
      for (const name of names) {
        const cleanName = name.split(/\s+as\s+/)[0]?.trim();
        if (cleanName) {
          actualImports.add(`import ${cleanName}`);
        }
      }
    }

    // Filter to only import lines from the pattern
    const patternImports: string[] = [];
    for (const importLine of importLines) {
      if (
        !importLine.startsWith("from ") &&
        !importLine.startsWith("import ")
      ) {
        continue;
      }
      const normalizedPattern = importLine.split(/\s+/).join(" ");
      patternImports.push(normalizedPattern);
    }

    // No import lines found in pattern
    if (patternImports.length === 0) {
      return false;
    }

    // For combination patterns, ALL imports must be present
    // This prevents false positives when only part of the pattern matches
    return patternImports.every((pi) => actualImports.has(pi));
  }

  /**
   * Check if pattern lines match EXACTLY in code.
   *
   * Used for incorrect patterns (anti-patterns).
   * Requires ALL significant lines to match exactly to avoid false positives.
   * This ensures we only flag code when the ENTIRE incorrect pattern is present,
   * not just parts of it.
   */
  private multiLinePatternMatchesExact(
    code: string,
    patternLines: string[]
  ): boolean {
    if (patternLines.length === 0) {
      return false;
    }

    const codeLinesNormalized = code
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("#"))
      .map((line) => line.split(/\s+/).join(" "));

    let matchedCount = 0;
    for (const patternLine of patternLines) {
      const normalizedPattern = patternLine.split(/\s+/).join(" ");

      if (normalizedPattern.length < 15) {
        continue;
      }

      for (const codeLine of codeLinesNormalized) {
        if (normalizedPattern === codeLine) {
          matchedCount++;
          break;
        }
      }
    }

    const significantLines = patternLines.filter((l) => l.length >= 15);
    
    // For incorrect patterns, ALL significant lines must match
    // This prevents false positives when only part of the pattern is present
    return matchedCount >= 1 && matchedCount === significantLines.length;
  }

  /**
   * Check if pattern lines match FLEXIBLY in code.
   *
   * Used for correct patterns (documentation examples).
   * Allows variations like different formatting, extra parameters, or comments.
   */
  private multiLinePatternMatchesFlexible(
    code: string,
    patternLines: string[]
  ): boolean {
    if (patternLines.length === 0) {
      return false;
    }

    const codeLinesNormalized = code
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("#"))
      .map((line) => line.split(/\s+/).join(" "));

    let matchedCount = 0;
    for (const patternLine of patternLines) {
      const normalizedPattern = patternLine.split(/\s+/).join(" ");

      if (normalizedPattern.length < 15) {
        continue;
      }

      for (const codeLine of codeLinesNormalized) {
        if (
          codeLine.includes(normalizedPattern) ||
          normalizedPattern.includes(codeLine)
        ) {
          matchedCount++;
          break;
        }
      }
    }

    const significantLines = patternLines.filter((l) => l.length >= 15);
    if (significantLines.length <= 2) {
      return matchedCount >= 1 && matchedCount === significantLines.length;
    }

    return matchedCount >= 2;
  }

  /**
   * Calculate a score from 0-100 based on findings.
   */
  private calculateScore(result: EvaluationResult): number {
    if (result.findings.length === 0 && result.matchedCorrect.length === 0) {
      return 50; // Neutral - no patterns matched
    }

    // Start with base score
    let score = 100;

    // Deduct for errors
    score -= result.findings.filter((f) => f.severity === Severity.ERROR)
      .length * 20;

    // Deduct for warnings
    score -= result.findings.filter((f) => f.severity === Severity.WARNING)
      .length * 5;

    // Bonus for matching correct patterns
    score += result.matchedCorrect.length * 5;

    // Major penalty for incorrect patterns
    score -= result.matchedIncorrect.length * 15;

    return Math.max(0, Math.min(100, score));
  }
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Convert evaluation result to a plain object for JSON serialization.
 */
export function evaluationResultToDict(result: EvaluationResult): Record<string, unknown> {
  return {
    skill_name: result.skillName,
    scenario: result.scenario,
    passed: result.passed,
    score: result.score,
    error_count: result.errorCount,
    warning_count: result.warningCount,
    findings: result.findings.map((f) => ({
      severity: f.severity,
      rule: f.rule,
      message: f.message,
      line: f.line,
      suggestion: f.suggestion,
    })),
    matched_correct: result.matchedCorrect,
    matched_incorrect: result.matchedIncorrect,
  };
}
