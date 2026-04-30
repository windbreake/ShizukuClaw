/**
 * Markdown Reporter
 *
 * Generates markdown reports for evaluation results.
 */

import * as fs from "node:fs";
import * as path from "node:path";
import type { EvaluationResult, EvaluationSummary, Finding, Severity } from "../types.js";

/**
 * Generates markdown reports for evaluation results.
 */
export class MarkdownReporter {
  private outputDir: string;

  constructor(outputDir?: string) {
    this.outputDir = outputDir ?? "tests/reports";
    // Ensure output directory exists
    fs.mkdirSync(this.outputDir, { recursive: true });
  }

  /**
   * Generate a markdown report for an evaluation summary.
   * @returns Path to the generated report file.
   */
  generateReport(summary: EvaluationSummary, filename?: string): string {
    const reportFilename = filename ?? `${summary.skillName}-report.md`;
    const outputPath = path.join(this.outputDir, reportFilename);

    const content = this.buildReport(summary);
    fs.writeFileSync(outputPath, content, "utf-8");

    return outputPath;
  }

  /**
   * Generate a combined report for multiple skills.
   * @returns Path to the generated report file.
   */
  generateMultiSkillReport(
    summaries: EvaluationSummary[],
    filename = "evaluation-report.md"
  ): string {
    const outputPath = path.join(this.outputDir, filename);
    const lines: string[] = [];

    // Header
    lines.push("# Skill Evaluation Report");
    lines.push("");
    lines.push(`**Generated:** ${this.formatDate()}`);
    lines.push(`**Skills Evaluated:** ${summaries.length}`);
    lines.push("");

    // Overview table
    lines.push("## Overview");
    lines.push("");
    lines.push("| Skill | Status | Pass Rate | Avg Score |");
    lines.push("|-------|--------|-----------|-----------|");

    let totalPassed = 0;
    let totalScenarios = 0;

    for (const summary of summaries) {
      const status = summary.failed === 0 ? "✅" : "❌";
      const passRate =
        summary.totalScenarios > 0
          ? (summary.passed / summary.totalScenarios) * 100
          : 0;

      lines.push(
        `| ${summary.skillName} | ${status} | ${passRate.toFixed(1)}% | ${summary.avgScore.toFixed(1)} |`
      );

      totalPassed += summary.passed;
      totalScenarios += summary.totalScenarios;
    }

    lines.push("");

    // Overall summary
    const overallPassRate =
      totalScenarios > 0 ? (totalPassed / totalScenarios) * 100 : 0;

    lines.push("## Overall Statistics");
    lines.push("");
    lines.push(`- **Total Scenarios:** ${totalScenarios}`);
    lines.push(`- **Total Passed:** ${totalPassed}`);
    lines.push(`- **Overall Pass Rate:** ${overallPassRate.toFixed(1)}%`);
    lines.push("");

    // Detailed sections for failed skills
    for (const summary of summaries) {
      if (summary.failed > 0) {
        lines.push(`## ${summary.skillName}`);
        lines.push("");
        lines.push(...this.buildSummarySection(summary).slice(2)); // Skip header
        lines.push(...this.buildDetailedFindings(summary));
      }
    }

    lines.push(...this.buildFooter());

    fs.writeFileSync(outputPath, lines.join("\n"), "utf-8");
    return outputPath;
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Private helpers
  // ─────────────────────────────────────────────────────────────────────────────

  private buildReport(summary: EvaluationSummary): string {
    const lines: string[] = [];

    lines.push(...this.buildHeader(summary));
    lines.push(...this.buildSummarySection(summary));
    lines.push(...this.buildResultsTable(summary));

    if (summary.failed > 0) {
      lines.push(...this.buildDetailedFindings(summary));
    }

    lines.push(...this.buildFooter());

    return lines.join("\n");
  }

  private buildHeader(summary: EvaluationSummary): string[] {
    const statusEmoji = summary.failed === 0 ? "✅" : "❌";

    return [
      `# ${statusEmoji} Skill Evaluation Report: ${summary.skillName}`,
      "",
      `**Generated:** ${this.formatDate()}`,
      "",
    ];
  }

  private buildSummarySection(summary: EvaluationSummary): string[] {
    const passRate =
      summary.totalScenarios > 0
        ? (summary.passed / summary.totalScenarios) * 100
        : 0;

    const status = summary.failed === 0 ? "🟢 PASSED" : "🔴 FAILED";

    return [
      "## Summary",
      "",
      `**Status:** ${status}`,
      "",
      "| Metric | Value |",
      "|--------|-------|",
      `| Total Scenarios | ${summary.totalScenarios} |`,
      `| Passed | ${summary.passed} |`,
      `| Failed | ${summary.failed} |`,
      `| Pass Rate | ${passRate.toFixed(1)}% |`,
      `| Average Score | ${summary.avgScore.toFixed(1)} |`,
      `| Duration | ${summary.durationMs.toFixed(0)}ms |`,
      "",
    ];
  }

  private buildResultsTable(summary: EvaluationSummary): string[] {
    const lines: string[] = [
      "## Scenario Results",
      "",
      "| Scenario | Status | Score | Errors | Warnings |",
      "|----------|--------|-------|--------|----------|",
    ];

    for (const result of summary.results) {
      const status = result.passed ? "✅ Pass" : "❌ Fail";
      lines.push(
        `| ${result.scenario} | ${status} | ${result.score.toFixed(1)} | ${result.errorCount} | ${result.warningCount} |`
      );
    }

    lines.push("");
    return lines;
  }

  private buildDetailedFindings(summary: EvaluationSummary): string[] {
    const lines: string[] = ["## Detailed Findings", ""];

    for (const result of summary.results) {
      if (!result.passed) {
        lines.push(...this.buildResultDetails(result));
      }
    }

    return lines;
  }

  private buildResultDetails(result: EvaluationResult): string[] {
    const lines: string[] = [
      `### ${result.scenario}`,
      "",
      `**Score:** ${result.score.toFixed(1)}`,
      "",
    ];

    if (result.findings.length > 0) {
      lines.push("#### Findings");
      lines.push("");

      for (const finding of result.findings) {
        const severityEmoji = this.getSeverityEmoji(finding.severity);
        lines.push(`- ${severityEmoji} **${finding.rule}**: ${finding.message}`);

        if (finding.suggestion) {
          lines.push(`  - 💡 *Suggestion:* ${finding.suggestion}`);
        }

        if (finding.codeSnippet) {
          lines.push("  ```python");
          lines.push(`  ${finding.codeSnippet}`);
          lines.push("  ```");
        }
      }

      lines.push("");
    }

    // Show matched patterns
    if (result.matchedIncorrect.length > 0) {
      lines.push("#### Incorrect Patterns Detected");
      lines.push("");
      for (const pattern of result.matchedIncorrect) {
        lines.push(`- \`${pattern}\``);
      }
      lines.push("");
    }

    if (result.matchedCorrect.length > 0) {
      lines.push("#### Correct Patterns Found");
      lines.push("");
      for (const pattern of result.matchedCorrect) {
        lines.push(`- \`${pattern}\``);
      }
      lines.push("");
    }

    return lines;
  }

  private buildFooter(): string[] {
    return ["---", "", "*Report generated by Skill Evaluation Harness*"];
  }

  private formatDate(): string {
    return new Date().toISOString().replace("T", " ").substring(0, 19);
  }

  private getSeverityEmoji(severity: Severity | string): string {
    const severityValue = typeof severity === "string" ? severity : severity;
    switch (severityValue) {
      case "error":
        return "🔴";
      case "warning":
        return "🟡";
      case "info":
        return "🔵";
      default:
        return "⚪";
    }
  }
}
