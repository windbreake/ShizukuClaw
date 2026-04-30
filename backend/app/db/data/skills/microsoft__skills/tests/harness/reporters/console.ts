/**
 * Console Reporter
 *
 * Pretty console output for evaluation results using chalk.
 */

import chalk from "chalk";
import type { EvaluationResult, EvaluationSummary, Finding, Severity } from "../types.js";

/**
 * Reports evaluation results to the console.
 */
export class ConsoleReporter {
  private verbose: boolean;
  private useColor: boolean;

  constructor(options: { verbose?: boolean; useColor?: boolean } = {}) {
    this.verbose = options.verbose ?? false;
    this.useColor = options.useColor ?? true;
  }

  /**
   * Print a summary of evaluation results.
   */
  reportSummary(summary: EvaluationSummary): void {
    const passRate =
      summary.totalScenarios > 0
        ? (summary.passed / summary.totalScenarios) * 100
        : 0;

    // Header
    console.log();
    this.printHeader(`${summary.skillName} Evaluation`);

    // Status indicator
    const statusEmoji = summary.failed === 0 ? "✅" : "❌";
    const statusText = summary.failed === 0 ? "PASSED" : "FAILED";
    const statusColor = summary.failed === 0 ? chalk.green : chalk.red;

    console.log(`${statusEmoji} ${statusColor.bold(statusText)}`);
    console.log();

    // Summary table
    console.log(this.formatMetric("Total Scenarios", summary.totalScenarios.toString()));
    console.log(this.formatMetric("Passed", chalk.green(summary.passed.toString())));
    console.log(
      this.formatMetric(
        "Failed",
        summary.failed > 0 ? chalk.red(summary.failed.toString()) : "0"
      )
    );

    const rateColor =
      passRate >= 80 ? chalk.green : passRate >= 50 ? chalk.yellow : chalk.red;
    console.log(this.formatMetric("Pass Rate", rateColor(`${passRate.toFixed(1)}%`)));

    const scoreColor =
      summary.avgScore >= 80
        ? chalk.green
        : summary.avgScore >= 50
          ? chalk.yellow
          : chalk.red;
    console.log(
      this.formatMetric("Average Score", scoreColor(summary.avgScore.toFixed(1)))
    );
    console.log(this.formatMetric("Duration", `${summary.durationMs.toFixed(0)}ms`));

    // Failed scenarios
    if (summary.failed > 0 && this.verbose) {
      console.log();
      console.log(chalk.red.bold("Failed Scenarios:"));
      for (const result of summary.results) {
        if (!result.passed) {
          this.reportResult(result);
        }
      }
    }
  }

  /**
   * Print a single evaluation result.
   */
  reportResult(result: EvaluationResult): void {
    const status = result.passed
      ? chalk.green("PASS")
      : chalk.red("FAIL");

    console.log();
    console.log(`  ${status} ${result.scenario} (score: ${result.score.toFixed(1)})`);

    if (this.verbose || !result.passed) {
      for (const finding of result.findings) {
        this.printFinding(finding);
      }
    }
  }

  /**
   * Print a list of skills.
   */
  printSkillList(skills: string[]): void {
    this.printHeader("Available Skills with Acceptance Criteria");
    console.log();

    for (const skill of skills) {
      console.log(`  • ${skill}`);
    }

    console.log();
    console.log(chalk.dim(`Total: ${skills.length} skills`));
  }

  /**
   * Print a section header.
   */
  printHeader(text: string): void {
    if (this.useColor) {
      console.log(chalk.blue.bold(text));
      console.log(chalk.blue("─".repeat(text.length)));
    } else {
      console.log(text);
      console.log("-".repeat(text.length));
    }
  }

  /**
   * Print an error message.
   */
  printError(text: string): void {
    if (this.useColor) {
      console.error(`${chalk.red("Error:")} ${text}`);
    } else {
      console.error(`Error: ${text}`);
    }
  }

  /**
   * Print a warning message.
   */
  printWarning(text: string): void {
    if (this.useColor) {
      console.warn(`${chalk.yellow("Warning:")} ${text}`);
    } else {
      console.warn(`Warning: ${text}`);
    }
  }

  /**
   * Print a success message.
   */
  printSuccess(text: string): void {
    if (this.useColor) {
      console.log(`${chalk.green("✓")} ${text}`);
    } else {
      console.log(`✓ ${text}`);
    }
  }

  /**
   * Print an info message.
   */
  printInfo(text: string): void {
    if (this.useColor) {
      console.log(chalk.dim(text));
    } else {
      console.log(text);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Private helpers
  // ─────────────────────────────────────────────────────────────────────────────

  private formatMetric(label: string, value: string): string {
    const paddedLabel = label.padEnd(18);
    return `  ${chalk.cyan(paddedLabel)} ${value}`;
  }

  private printFinding(finding: Finding): void {
    const severityStyle = this.getSeverityStyle(finding.severity);
    const severityLabel = finding.severity.toUpperCase();

    console.log(
      `    ${severityStyle(`[${severityLabel}]`)} ${finding.rule}: ${finding.message}`
    );

    if (finding.suggestion) {
      console.log(`      💡 ${finding.suggestion}`);
    }

    if (finding.codeSnippet) {
      console.log(chalk.dim(`      ${finding.codeSnippet}`));
    }
  }

  private getSeverityStyle(severity: Severity | string): (text: string) => string {
    const severityValue = typeof severity === "string" ? severity : severity;
    switch (severityValue) {
      case "error":
        return chalk.red;
      case "warning":
        return chalk.yellow;
      case "info":
        return chalk.blue;
      default:
        return (text: string) => text;
    }
  }
}
