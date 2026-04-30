# MCP Server Usage for Agents

How agents interact with Model Context Protocol (MCP) servers configured in this repository.

## What is MCP?

MCP (Model Context Protocol) is a standard for connecting AI agents to external tools and data sources. MCP servers expose capabilities that agents can invoke during task execution.

## Configured MCP Servers

This repository provides MCP server configurations in `.vscode/mcp.json`:

### Documentation Servers

| Server | Purpose | When to Use |
|--------|---------|-------------|
| `microsoft-docs` | Search Microsoft Learn | **FIRST** before any Azure SDK implementation |
| `context7` | Semantic search over indexed docs | When you need Foundry-specific patterns |
| `deepwiki` | Query GitHub repositories | When researching OSS implementations |

### Development Servers

| Server | Purpose | When to Use |
|--------|---------|-------------|
| `github` | GitHub API operations | PRs, issues, code search |
| `playwright` | Browser automation | Testing, scraping, verification |
| `terraform` | Infrastructure as code | Azure resource provisioning |
| `eslint` | JavaScript/TypeScript linting | Code quality checks |

### Utility Servers

| Server | Purpose | When to Use |
|--------|---------|-------------|
| `sequentialthinking` | Step-by-step reasoning | Complex multi-step problems |
| `memory` | Persistent storage | Cross-session context |
| `markitdown` | Document conversion | Converting files to markdown |

## Agent Workflow: Using MCP Servers

### Pattern: Search Before Implement

**Critical**: Azure SDKs change frequently. Always search official docs before writing code.

```
User: "Create an Azure AI Search index with vector fields"

Agent workflow:
1. FIRST: Query microsoft-docs MCP
   → Search: "Azure AI Search vector index Python SDK"
   → Get: Current API signatures, required parameters
   
2. THEN: Load relevant skill
   → azure-search-documents-py
   
3. FINALLY: Implement
   → Use patterns from skill + current API from docs
```

### Example: microsoft-docs MCP Usage

The `microsoft-docs` MCP provides tools for searching Microsoft Learn:

```
Agent invokes: microsoft_docs_search
Query: "azure-ai-projects AIProjectClient Python"

Response:
- Title: "Azure AI Projects client library for Python"
- URL: https://learn.microsoft.com/python/api/azure-ai-projects/
- Excerpt: "AIProjectClient is the main entry point..."
```

If search results are incomplete, fetch the full page:

```
Agent invokes: microsoft_docs_fetch
URL: "https://learn.microsoft.com/python/api/azure-ai-projects/"

Response: Full markdown content of the documentation page
```

### Example: context7 MCP Usage

The `context7` MCP provides semantic search over this repository's indexed documentation:

```
Agent invokes: context7_query-docs
Library: "/microsoft/agent-skills"
Query: "How to create a Cosmos DB service layer with FastAPI"

Response:
- Relevant skill content from azure-cosmos-db-py
- Patterns for service layer implementation
- FastAPI integration examples
```

### Example: Combining MCP + Skills

```
Task: "Add Azure Blob Storage upload endpoint"

Step 1: Search current API
  → microsoft-docs: "azure-storage-blob Python upload_blob"
  → Get: Current BlobClient.upload_blob() signature

Step 2: Load skills
  → azure-storage-blob-py: Storage patterns
  → fastapi-router-py: Endpoint patterns

Step 3: Implement using both
  → Current API from docs + Patterns from skills
```

## MCP Configuration Format

MCP servers are configured in `.vscode/mcp.json`:

```json
{
  "servers": {
    "microsoft-docs": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@anthropic/microsoft-docs-mcp"]
    },
    "context7": {
      "type": "stdio", 
      "command": "npx",
      "args": ["-y", "@anthropic/context7-mcp"]
    },
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@anthropic/github-mcp"],
      "env": {
        "GITHUB_TOKEN": "${env:GITHUB_TOKEN}"
      }
    }
  }
}
```

## Agent Decision Tree for MCP Usage

```
Is task about Azure/Microsoft SDK?
├─ YES → Query microsoft-docs FIRST
│        Then load relevant skill
│        Then implement
│
└─ NO → Is task about this repository's patterns?
        ├─ YES → Query context7
        │        Then load relevant skill
        │
        └─ NO → Is task about external code/repos?
                ├─ YES → Query deepwiki or github
                │
                └─ NO → Proceed with skill-only approach
```

## Why MCP + Skills Together?

| MCP Servers Provide | Skills Provide |
|---------------------|----------------|
| Current API signatures | Established patterns |
| Latest documentation | Best practices |
| Real-time data | Domain expertise |
| External integrations | Coding standards |

**MCP = Fresh information. Skills = Proven patterns.**

Use both for reliable implementations:

```
# BAD: Skill only (may use outdated API)
Load azure-cosmos-db-py → Implement

# BAD: MCP only (no patterns, reinventing wheel)
Search docs → Implement from scratch

# GOOD: MCP + Skill
Search docs (current API) → Load skill (patterns) → Implement
```

## Troubleshooting

### MCP Server Not Responding

1. Check server is installed: `npx -y @anthropic/microsoft-docs-mcp --version`
2. Verify configuration in `.vscode/mcp.json`
3. Check environment variables (e.g., `GITHUB_TOKEN` for github MCP)

### Stale Results from context7

Context7 indexes are updated daily via GitHub Actions. For the freshest content:
1. Check when workflow last ran: `.github/workflows/update-llms-txt.yml`
2. For immediate updates, trigger workflow manually
3. Fall back to `microsoft-docs` for authoritative current info
