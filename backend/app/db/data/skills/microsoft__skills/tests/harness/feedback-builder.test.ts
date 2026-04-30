/**
 * Tests for FeedbackBuilder
 *
 * Validates that feedback is formatted correctly, errors appear before warnings,
 * patterns are properly referenced, and suggestions guide re-generation.
 */

import { describe, it, expect, beforeEach } from "vitest";
import {
  Severity,
  type Finding,
  type EvaluationResult,
  type AcceptanceCriteria,
  createFinding,
  createEvaluationResult,
  createAcceptanceCriteria,
  createCodePattern,
} from "./types.js";
import { FeedbackBuilder, createFeedbackBuilder } from "./feedback-builder.js";

describe("FeedbackBuilder", () => {
  let builder: FeedbackBuilder;

  beforeEach(() => {
    builder = new FeedbackBuilder();
  });

  describe("buildFeedback", () => {
    it("returns empty string when no findings or patterns", () => {
      const evalResult = createEvaluationResult("skill-py", "test", "code");
      const feedback = builder.buildFeedback(evalResult);
      expect(feedback).toBe("");
    });

    it("includes all sections when findings present", () => {
      const evalResult = createEvaluationResult("skill-py", "test", "code");

      evalResult.findings.push(
        createFinding({
          severity: Severity.ERROR,
          rule: "import-rule",
          message: "Wrong import path",
          suggestion: "Use correct import",
          codeSnippet: "from wrong.path import Client",
        })
      );

      evalResult.findings.push(
        createFinding({
          severity: Severity.WARNING,
          rule: "style-rule",
          message: "Inconsistent style",
          suggestion: "Add docstring",
        })
      );

      evalResult.matchedIncorrect = ["imports-section"];

      const feedback = builder.buildFeedback(evalResult);

      expect(feedback).toContain("## Issues Found in Generated Code");
      expect(feedback).toContain("### ERRORS (Must Fix)");
      expect(feedback).toContain("### WARNINGS (Should Fix)");
      expect(feedback).toContain("### INCORRECT PATTERNS DETECTED");
    });

    it("prioritizes errors before warnings", () => {
      const evalResult = createEvaluationResult("skill-py", "test", "code");

      evalResult.findings.push(
        createFinding({
          severity: Severity.WARNING,
          rule: "warn-rule",
          message: "Warning issue",
        })
      );

      evalResult.findings.push(
        createFinding({
          severity: Severity.ERROR,
          rule: "error-rule",
          message: "Error issue",
        })
      );

      const feedback = builder.buildFeedback(evalResult);
      const errorIndex = feedback.indexOf("### ERRORS");
      const warningIndex = feedback.indexOf("### WARNINGS");

      expect(errorIndex).toBeLessThan(warningIndex);
    });

    it("accepts optional criteria for enhanced suggestions", () => {
      const evalResult = createEvaluationResult("skill-py", "test", "code");
      evalResult.findings.push(
        createFinding({
          severity: Severity.ERROR,
          rule: "auth-rule",
          message: "Missing authentication",
        })
      );

      const criteria = createAcceptanceCriteria({
        skillName: "skill-py",
        correctPatterns: [
          createCodePattern({
            code: "from azure.identity import DefaultAzureCredential",
            description: "Always use DefaultAzureCredential for auth",
            isCorrect: true,
          }),
        ],
      });

      const feedback = builder.buildFeedback(evalResult, criteria);

      expect(feedback).toContain("SUGGESTED CORRECTIONS");
      expect(feedback).toContain("DefaultAzureCredential");
    });
  });

  describe("formatErrorFeedback", () => {
    it("returns empty string when no error findings", () => {
      const findings: Finding[] = [
        createFinding({
          severity: Severity.WARNING,
          message: "Warning",
        }),
      ];

      const feedback = builder.formatErrorFeedback(findings);
      expect(feedback).toBe("");
    });

    it("includes all error findings", () => {
      const findings: Finding[] = [
        createFinding({
          severity: Severity.ERROR,
          rule: "import-rule",
          message: "Wrong import",
          suggestion: "Use correct import",
          codeSnippet: "wrong code",
        }),
        createFinding({
          severity: Severity.ERROR,
          rule: "pattern-rule",
          message: "Incorrect pattern",
          suggestion: "Follow correct pattern",
          codeSnippet: "bad pattern",
        }),
      ];

      const feedback = builder.formatErrorFeedback(findings);

      expect(feedback).toContain("### ERRORS (Must Fix)");
      expect(feedback).toContain("[import-rule]");
      expect(feedback).toContain("[pattern-rule]");
      expect(feedback).toContain("Use correct import");
      expect(feedback).toContain("Follow correct pattern");
    });

    it("truncates long code snippets", () => {
      const longSnippet = "x".repeat(150);
      const findings: Finding[] = [
        createFinding({
          severity: Severity.ERROR,
          rule: "rule",
          message: "msg",
          codeSnippet: longSnippet,
        }),
      ];

      const feedback = builder.formatErrorFeedback(findings);

      expect(feedback).toContain("...");
      expect(feedback).not.toContain(longSnippet);
    });

    it("includes suggestions when present", () => {
      const findings: Finding[] = [
        createFinding({
          severity: Severity.ERROR,
          rule: "rule",
          message: "msg",
          suggestion: "Fix it this way",
        }),
      ];

      const feedback = builder.formatErrorFeedback(findings);

      expect(feedback).toContain("SUGGESTION: Fix it this way");
    });

    it("omits suggestions when not present", () => {
      const findings: Finding[] = [
        createFinding({
          severity: Severity.ERROR,
          rule: "rule",
          message: "msg",
          suggestion: "",
        }),
      ];

      const feedback = builder.formatErrorFeedback(findings);

      expect(feedback).not.toContain("SUGGESTION:");
    });
  });

  describe("formatWarningFeedback", () => {
    it("returns empty string when no warning findings", () => {
      const findings: Finding[] = [
        createFinding({
          severity: Severity.ERROR,
          message: "Error",
        }),
      ];

      const feedback = builder.formatWarningFeedback(findings);
      expect(feedback).toBe("");
    });

    it("includes all warning findings", () => {
      const findings: Finding[] = [
        createFinding({
          severity: Severity.WARNING,
          rule: "style-rule",
          message: "Missing docstring",
          suggestion: "Add docstring",
        }),
        createFinding({
          severity: Severity.WARNING,
          rule: "perf-rule",
          message: "Inefficient operation",
          suggestion: "Use faster method",
        }),
      ];

      const feedback = builder.formatWarningFeedback(findings);

      expect(feedback).toContain("### WARNINGS (Should Fix)");
      expect(feedback).toContain("[style-rule]");
      expect(feedback).toContain("[perf-rule]");
      expect(feedback).toContain("Add docstring");
      expect(feedback).toContain("Use faster method");
    });

    it("separates warnings from errors by not including ERROR severity", () => {
      const findings: Finding[] = [
        createFinding({
          severity: Severity.ERROR,
          rule: "error-rule",
          message: "This is an error",
        }),
        createFinding({
          severity: Severity.WARNING,
          rule: "warning-rule",
          message: "This is a warning",
        }),
      ];

      const feedback = builder.formatWarningFeedback(findings);

      expect(feedback).not.toContain("error-rule");
      expect(feedback).toContain("warning-rule");
    });
  });

  describe("formatPatternFeedback", () => {
    it("returns empty string when no matched incorrect patterns", () => {
      const feedback = builder.formatPatternFeedback([]);
      expect(feedback).toBe("");
    });

    it("lists all matched incorrect pattern sections", () => {
      const patterns = ["imports-section", "authentication-section", "patterns-section"];

      const feedback = builder.formatPatternFeedback(patterns);

      expect(feedback).toContain("### INCORRECT PATTERNS DETECTED");
      expect(feedback).toContain("**imports-section**");
      expect(feedback).toContain("**authentication-section**");
      expect(feedback).toContain("**patterns-section**");
    });

    it("instructs LLM to review acceptance criteria", () => {
      const patterns = ["section1"];

      const feedback = builder.formatPatternFeedback(patterns);

      expect(feedback).toContain("Review the acceptance criteria");
      expect(feedback).toContain("correct patterns instead");
    });

    it("accepts optional criteria for context", () => {
      const patterns = ["section1"];
      const criteria = createAcceptanceCriteria({
        skillName: "test-skill",
      });

      const feedback = builder.formatPatternFeedback(patterns, criteria);

      expect(feedback).toContain("### INCORRECT PATTERNS DETECTED");
      expect(feedback).toContain("**section1**");
    });
  });

  describe("suggestCorrections", () => {
    it("returns empty string when no suggestions available", () => {
      const findings: Finding[] = [
        createFinding({
          severity: Severity.ERROR,
          rule: "rule",
          message: "msg",
          suggestion: "", // empty suggestion
        }),
      ];

      const feedback = builder.suggestCorrections(findings);
      expect(feedback).toBe("");
    });

    it("includes suggestions from findings", () => {
      const findings: Finding[] = [
        createFinding({
          severity: Severity.ERROR,
          rule: "rule1",
          message: "msg1",
          suggestion: "Use method A instead",
        }),
        createFinding({
          severity: Severity.WARNING,
          rule: "rule2",
          message: "msg2",
          suggestion: "Add better error handling",
        }),
      ];

      const feedback = builder.suggestCorrections(findings);

      expect(feedback).toContain("### SUGGESTED CORRECTIONS");
      expect(feedback).toContain("Use method A instead");
      expect(feedback).toContain("Add better error handling");
    });

    it("includes suggestions from correct patterns in criteria", () => {
      const findings: Finding[] = [];
      const criteria = createAcceptanceCriteria({
        skillName: "skill-py",
        correctPatterns: [
          createCodePattern({
            code: "from azure.identity import DefaultAzureCredential",
            description: "Use DefaultAzureCredential for secure auth",
            isCorrect: true,
          }),
          createCodePattern({
            code: "with client: ...",
            description: "Use context manager for resource cleanup",
            isCorrect: true,
          }),
        ],
      });

      const feedback = builder.suggestCorrections(findings, criteria);

      expect(feedback).toContain("### SUGGESTED CORRECTIONS");
      expect(feedback).toContain("DefaultAzureCredential");
      expect(feedback).toContain("context manager");
    });

    it("deduplicates suggestions", () => {
      const findings: Finding[] = [
        createFinding({
          severity: Severity.ERROR,
          rule: "rule1",
          message: "msg1",
          suggestion: "Use correct import",
        }),
        createFinding({
          severity: Severity.WARNING,
          rule: "rule2",
          message: "msg2",
          suggestion: "Use correct import", // duplicate
        }),
      ];

      const feedback = builder.suggestCorrections(findings);

      // Count occurrences of the suggestion
      const count = (feedback.match(/Use correct import/g) || []).length;
      expect(count).toBe(1); // Should appear only once
    });

    it("formats suggestions as bullet points", () => {
      const findings: Finding[] = [
        createFinding({
          severity: Severity.ERROR,
          suggestion: "First suggestion",
        }),
        createFinding({
          severity: Severity.ERROR,
          suggestion: "Second suggestion",
        }),
      ];

      const feedback = builder.suggestCorrections(findings);

      expect(feedback).toContain("- First suggestion");
      expect(feedback).toContain("- Second suggestion");
    });

    it("ignores multiline descriptions from criteria patterns", () => {
      const findings: Finding[] = [];
      const criteria = createAcceptanceCriteria({
        skillName: "skill-py",
        correctPatterns: [
          createCodePattern({
            code: "...",
            description: "This is a multiline\ndescription that\nshould be ignored",
            isCorrect: true,
          }),
        ],
      });

      const feedback = builder.suggestCorrections(findings, criteria);

      // Should be empty or not contain the multiline description
      expect(feedback).not.toContain("This is a multiline");
    });
  });

  describe("createFeedbackBuilder", () => {
    it("creates a FeedbackBuilder instance", () => {
      const builder = createFeedbackBuilder();
      expect(builder).toBeInstanceOf(FeedbackBuilder);
    });

    it("returned instance has all required methods", () => {
      const builder = createFeedbackBuilder();
      expect(typeof builder.buildFeedback).toBe("function");
      expect(typeof builder.formatErrorFeedback).toBe("function");
      expect(typeof builder.formatWarningFeedback).toBe("function");
      expect(typeof builder.formatPatternFeedback).toBe("function");
      expect(typeof builder.suggestCorrections).toBe("function");
    });
  });

  describe("LLM-actionable format", () => {
    it("produces output that guides code re-generation", () => {
      const evalResult = createEvaluationResult("skill-py", "test", "code");

      evalResult.findings.push(
        createFinding({
          severity: Severity.ERROR,
          rule: "import-error",
          message: "Incorrect import path",
          suggestion: "Change to: from azure.ai.projects import ProjectClient",
          codeSnippet: "from azure.ai.projects.models import ProjectClient",
        })
      );

      evalResult.matchedIncorrect = ["imports-section"];

      const feedback = builder.buildFeedback(evalResult);

      // Should be clear and actionable
      expect(feedback).toContain("ERRORS (Must Fix)");
      expect(feedback).toContain("import-error");
      expect(feedback).toContain("ProjectClient");
      expect(feedback).toContain("SUGGESTION:");
      expect(feedback).toContain("imports-section");
    });

    it("prioritizes most important information", () => {
      const evalResult = createEvaluationResult("skill-py", "test", "code");

      // Add many warnings but one critical error
      for (let i = 0; i < 5; i++) {
        evalResult.findings.push(
          createFinding({
            severity: Severity.WARNING,
            rule: `warn-${i}`,
            message: `Warning ${i}`,
          })
        );
      }

      evalResult.findings.push(
        createFinding({
          severity: Severity.ERROR,
          rule: "critical-error",
          message: "Critical issue that breaks functionality",
          suggestion: "Must implement this pattern",
        })
      );

      const feedback = builder.buildFeedback(evalResult);
      const errorIndex = feedback.indexOf("ERRORS");
      const firstWarningIndex = feedback.indexOf("warn-0");

      // Error section should come before any warning details
      expect(errorIndex).toBeLessThan(firstWarningIndex);
    });
  });

  describe("edge cases", () => {
    it("handles findings with empty or undefined fields gracefully", () => {
      const findings: Finding[] = [
        createFinding({
          severity: Severity.ERROR,
          rule: "rule",
          message: "message",
          suggestion: "", // empty
          codeSnippet: "", // empty
        }),
      ];

      const feedback = builder.formatErrorFeedback(findings);

      expect(feedback).toContain("[rule]");
      expect(feedback).toContain("message");
      expect(feedback).not.toContain("SUGGESTION:");
      expect(feedback).not.toContain("Code:");
    });

    it("handles very long rule names", () => {
      const longRuleName = "a".repeat(100);
      const findings: Finding[] = [
        createFinding({
          severity: Severity.ERROR,
          rule: longRuleName,
          message: "msg",
        }),
      ];

      const feedback = builder.formatErrorFeedback(findings);

      expect(feedback).toContain(longRuleName);
    });

    it("handles mixed INFO severity findings (not shown)", () => {
      const findings: Finding[] = [
        createFinding({
          severity: Severity.INFO,
          rule: "info-rule",
          message: "Info message",
        }),
        createFinding({
          severity: Severity.ERROR,
          rule: "error-rule",
          message: "Error message",
        }),
      ];

      const feedback = builder.formatErrorFeedback(findings);
      expect(feedback).toContain("error-rule");
      expect(feedback).not.toContain("info-rule");
    });

    it("handles criteria with no patterns", () => {
      const findings: Finding[] = [
        createFinding({
          severity: Severity.ERROR,
          message: "msg",
        }),
      ];

      const criteria = createAcceptanceCriteria({
        skillName: "skill",
        correctPatterns: [], // empty
      });

      const feedback = builder.suggestCorrections(findings, criteria);
      expect(feedback).toBe("");
    });
  });
});
