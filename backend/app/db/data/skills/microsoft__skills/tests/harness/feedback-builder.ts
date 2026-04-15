/**
 * Builds intelligent, LLM-actionable feedback from evaluation findings.
 *
 * Transforms evaluation results into structured feedback that guides
 * code re-generation in the Ralph Loop, prioritizing errors, organizing
 * by severity, and providing specific correction suggestions.
 */

import {
  type AcceptanceCriteria,
  type EvaluationResult,
  type Finding,
  Severity,
} from "./types.js";

/**
 * Builder for constructing LLM-actionable feedback from evaluation results.
 *
 * Feedback is formatted to:
 * - Prioritize errors (must fix) over warnings (should fix)
 * - Include specific code snippets and suggestions
 * - Group patterns by section for easy reference
 * - Suggest concrete corrections based on criteria
 */
export class FeedbackBuilder {
  /**
   * Build complete feedback from evaluation results.
   *
   * Combines error feedback, warning feedback, pattern analysis,
   * and correction suggestions into a cohesive message.
   *
   * @param evalResult - The evaluation result to build feedback from
   * @param criteria - Optional acceptance criteria for enhanced suggestions
   * @returns Formatted feedback string, or empty string if no findings
   */
  buildFeedback(evalResult: EvaluationResult, criteria?: AcceptanceCriteria): string {
    if (evalResult.findings.length === 0 && evalResult.matchedIncorrect.length === 0) {
      return "";
    }

    const parts: string[] = [];
    parts.push("## Issues Found in Generated Code\n");

    // Build error feedback first (highest priority)
    const errorFeedback = this.formatErrorFeedback(evalResult.findings);
    if (errorFeedback) {
      parts.push(errorFeedback);
    }

    // Then warning feedback
    const warningFeedback = this.formatWarningFeedback(evalResult.findings);
    if (warningFeedback) {
      parts.push(warningFeedback);
    }

    // Then pattern feedback
    const patternFeedback = this.formatPatternFeedback(
      evalResult.matchedIncorrect,
      criteria
    );
    if (patternFeedback) {
      parts.push(patternFeedback);
    }

    // Finally suggestions for corrections
    const suggestions = this.suggestCorrections(evalResult.findings, criteria);
    if (suggestions) {
      parts.push(suggestions);
    }

    return parts.join("\n");
  }

  /**
   * Format error-severity findings for output.
   *
   * Errors are critical issues that must be fixed. Includes full details:
   * problem code, message, and specific suggestion.
   *
   * @param findings - All findings to filter
   * @returns Formatted error section, or empty string if no errors
   */
  formatErrorFeedback(findings: Finding[]): string {
    const errors = findings.filter((f) => f.severity === Severity.ERROR);

    if (errors.length === 0) {
      return "";
    }

    const parts: string[] = [];
    parts.push("### ERRORS (Must Fix)\n");

    for (const finding of errors) {
      parts.push(`- **[${finding.rule}]** ${finding.message}`);

      if (finding.suggestion) {
        parts.push(`  SUGGESTION: ${finding.suggestion}`);
      }

      if (finding.codeSnippet) {
        // Truncate long snippets but keep meaningful context
        const snippet =
          finding.codeSnippet.length > 100
            ? finding.codeSnippet.slice(0, 100) + "..."
            : finding.codeSnippet;
        parts.push(`  Code: \`${snippet}\``);
      }
    }

    parts.push("");
    return parts.join("\n");
  }

  /**
   * Format warning-severity findings for output.
   *
   * Warnings are recommendations for improvement. Less urgent than errors
   * but should be addressed for code quality.
   *
   * @param findings - All findings to filter
   * @returns Formatted warning section, or empty string if no warnings
   */
  formatWarningFeedback(findings: Finding[]): string {
    const warnings = findings.filter((f) => f.severity === Severity.WARNING);

    if (warnings.length === 0) {
      return "";
    }

    const parts: string[] = [];
    parts.push("### WARNINGS (Should Fix)\n");

    for (const warning of warnings) {
      parts.push(`- **[${warning.rule}]** ${warning.message}`);

      if (warning.suggestion) {
        parts.push(`  SUGGESTION: ${warning.suggestion}`);
      }
    }

    parts.push("");
    return parts.join("\n");
  }

  /**
   * Format pattern-based feedback from matched incorrect patterns.
   *
   * Tells the LLM which sections of the acceptance criteria were violated.
   * Groups by section for easy reference back to criteria.
   *
   * @param matchedIncorrect - Section names where incorrect patterns were found
   * @param criteria - Optional criteria for additional context
   * @returns Formatted pattern feedback, or empty string if no matched patterns
   */
  formatPatternFeedback(
    matchedIncorrect: string[],
    criteria?: AcceptanceCriteria
  ): string {
    if (matchedIncorrect.length === 0) {
      return "";
    }

    const parts: string[] = [];
    parts.push("### INCORRECT PATTERNS DETECTED\n");

    // List the specific sections with incorrect patterns
    parts.push(
      `The code contains incorrect patterns from: ${matchedIncorrect.map((s) => `**${s}**`).join(", ")}`
    );
    parts.push("");
    parts.push("Review the acceptance criteria for these sections and use correct patterns instead.\n");

    return parts.join("\n");
  }

  /**
   * Suggest specific corrections based on findings and criteria.
   *
   * Provides concrete alternatives to help the LLM improve the code
   * in the next iteration. Synthesizes multiple sources of information:
   * - Direct suggestions from findings
   * - Pattern mismatches from criteria
   * - Common correction patterns
   *
   * @param findings - Findings that may contain suggestions
   * @param criteria - Optional criteria with correct patterns
   * @returns Formatted suggestions section, or empty string if none available
   */
  suggestCorrections(findings: Finding[], criteria?: AcceptanceCriteria): string {
    const parts: string[] = [];
    let hasSuggestions = false;

    // Collect all unique suggestions from findings
    const suggestions = new Set<string>();
    for (const finding of findings) {
      if (finding.suggestion && finding.suggestion.length > 0) {
        suggestions.add(finding.suggestion);
        hasSuggestions = true;
      }
    }

    // Add suggestions from correct patterns in criteria
    if (criteria && criteria.correctPatterns.length > 0) {
      for (const pattern of criteria.correctPatterns) {
        // Only add if it's a simple, implementable pattern
        if (pattern.description && !pattern.description.includes("\n")) {
          suggestions.add(`Use: ${pattern.description}`);
          hasSuggestions = true;
        }
      }
    }

    if (!hasSuggestions) {
      return "";
    }

    parts.push("### SUGGESTED CORRECTIONS\n");
    parts.push("Based on the acceptance criteria, consider:\n");

    for (const suggestion of suggestions) {
      parts.push(`- ${suggestion}`);
    }

    parts.push("");
    return parts.join("\n");
  }
}

/**
 * Factory function to create a new FeedbackBuilder instance.
 *
 * @returns A new FeedbackBuilder ready for use
 */
export function createFeedbackBuilder(): FeedbackBuilder {
  return new FeedbackBuilder();
}
