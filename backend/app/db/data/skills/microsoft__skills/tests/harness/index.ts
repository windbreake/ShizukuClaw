/**
 * Skill Evaluation Test Harness
 *
 * A test framework for evaluating AI-generated code against acceptance criteria.
 */

// Types
export * from "./types.js";

// Core components
export { AcceptanceCriteriaLoader } from "./criteria-loader.js";
export { CodeEvaluator } from "./evaluator.js";
export { MockCopilotClient, SkillCopilotClient } from "./copilot-client.js";
export { SkillEvaluationRunner, type RalphLoopSummary } from "./runner.js";

// Feedback Builder
export { FeedbackBuilder, createFeedbackBuilder } from "./feedback-builder.js";

// Ralph Loop
export {
  RalphLoopController,
  createRalphConfig,
  createRalphLoopController,
  DEFAULT_RALPH_CONFIG,
  type RalphLoopConfig,
  type IterationResult,
  type RalphLoopResult,
  type StopReason,
} from "./ralph-loop.js";

// Reporters
export { ConsoleReporter } from "./reporters/console.js";
export { MarkdownReporter } from "./reporters/markdown.js";
