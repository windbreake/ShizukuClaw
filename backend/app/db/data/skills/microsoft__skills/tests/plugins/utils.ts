/**
 * Plugin Test Utilities
 *
 * Shared helpers for discovering and validating Claude Code plugins
 * in .github/plugins/.
 */

import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { parse as parseYaml } from "yaml";

// =============================================================================
// Types
// =============================================================================

export interface PluginManifest {
  name: string;
  description: string;
  version: string;
  author?: { name: string };
  homepage?: string;
  repository?: string;
  license?: string;
}

export interface Frontmatter {
  [key: string]: unknown;
}

export interface ParsedMarkdown {
  frontmatter: Frontmatter;
  body: string;
}

export interface PluginFiles {
  commands: string[];
  skills: string[];
  agents: string[];
}

// =============================================================================
// Constants
// =============================================================================

const PLUGINS_DIR = ".github/plugins";

// =============================================================================
// Discovery
// =============================================================================

/**
 * Discover all plugin directories under .github/plugins/.
 */
export function discoverPlugins(basePath: string): string[] {
  const pluginsDir = join(basePath, PLUGINS_DIR);
  if (!existsSync(pluginsDir)) {
    return [];
  }
  return readdirSync(pluginsDir, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name);
}

/**
 * Get the absolute path to a plugin directory.
 */
export function pluginPath(basePath: string, pluginName: string): string {
  return join(basePath, PLUGINS_DIR, pluginName);
}

/**
 * Discover files matching a pattern in a directory (non-recursive).
 */
export function discoverFiles(dir: string, extension: string): string[] {
  if (!existsSync(dir)) {
    return [];
  }
  return readdirSync(dir, { withFileTypes: true })
    .filter((e) => e.isFile() && e.name.endsWith(extension))
    .map((e) => e.name);
}

/**
 * Discover skill directories (each containing SKILL.md).
 */
export function discoverSkillDirs(skillsDir: string): string[] {
  if (!existsSync(skillsDir)) {
    return [];
  }
  return readdirSync(skillsDir, { withFileTypes: true })
    .filter(
      (e) =>
        e.isDirectory() && existsSync(join(skillsDir, e.name, "SKILL.md"))
    )
    .map((e) => e.name);
}

// =============================================================================
// Parsing
// =============================================================================

/**
 * Parse YAML frontmatter from a Markdown file.
 * Expects files starting with `---\n...\n---`.
 */
export function parseFrontmatter(filePath: string): ParsedMarkdown {
  const content = readFileSync(filePath, "utf-8");
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!match) {
    return { frontmatter: {}, body: content };
  }
  const frontmatter = parseYaml(match[1] ?? "") as Frontmatter;
  return { frontmatter, body: match[2] ?? "" };
}

/**
 * Load and parse plugin.json manifest.
 */
export function loadManifest(pluginDir: string): PluginManifest {
  const manifestPath = join(pluginDir, ".claude-plugin", "plugin.json");
  const raw = readFileSync(manifestPath, "utf-8");
  return JSON.parse(raw) as PluginManifest;
}

/**
 * Collect all plugin files for cross-reference checks.
 */
export function collectPluginFiles(pluginDir: string): PluginFiles {
  const commandsDir = join(pluginDir, "commands");
  const skillsDir = join(pluginDir, "skills");
  const agentsDir = join(pluginDir, "agents");

  return {
    commands: discoverFiles(commandsDir, ".md").map((f) =>
      f.replace(/\.md$/, "")
    ),
    skills: discoverSkillDirs(skillsDir),
    agents: discoverFiles(agentsDir, ".md").map((f) =>
      f.replace(/\.md$/, "")
    ),
  };
}
