# Microsoft Foundry

One plugin to get your coding agent fluent in Microsoft AI Foundry. Install it once and get 39 SDK skills across Python, .NET, TypeScript, and Java, plus three MCP servers for live Azure operations, Foundry-native tooling, and always-current Microsoft Learn documentation.

## Install

```bash
# Copilot CLI
/plugin marketplace add microsoft/skills
/plugin install microsoft-foundry@skills
```

```bash
# npx
npx skills add microsoft/skills --skill microsoft-foundry
```

## What You Get

### MCP Servers

The plugin bundles three MCP servers that activate automatically on install:

| Server | Purpose |
|--------|---------|
| **Azure MCP** | Manage Azure resources, deployments, and infrastructure from your editor. 40+ services. |
| **Foundry MCP** | Foundry-native operations at `mcp.ai.azure.com` -- model catalog, agents, indexes. |
| **Microsoft Docs** | Search Microsoft Learn in real-time so the agent always uses current SDK patterns. |

### Orchestration Skill

The `microsoft-foundry` skill routes between sub-skills for end-to-end Foundry workflows:

| Sub-Skill | What It Does |
|-----------|-------------|
| `project/create` | Provision a new Foundry project with `azd` |
| `resource/create` | Create Azure AI Services multi-service resources via CLI |
| `models/deploy-model` | Unified deployment -- routes to preset, custom, or capacity discovery |
| `agent/create/agent-framework` | Scaffold agents with Microsoft Agent Framework SDK |
| `quota` | Check usage, troubleshoot `QuotaExceeded`, request increases |
| `rbac` | Manage role assignments, managed identities, service principals |

### SDK Skills by Language

#### Python (16 skills)

| Skill | Package / Focus |
|-------|----------------|
| `azure-ai-projects-py` | Foundry project client, versioned agents, evals, connections |
| `agent-framework-azure-ai-py` | Agent Framework SDK -- persistent agents, hosted tools, MCP integration |
| `agents-v2-py` | Container-based hosted agents with `ImageBasedHostedAgentDefinition` |
| `hosted-agents-v2-py` | Hosted agents running custom code in Foundry |
| `azure-search-documents-py` | AI Search -- vector, hybrid, semantic ranking, agentic retrieval |
| `azure-ai-voicelive-py` | Real-time bidirectional voice AI over WebSocket |
| `azure-ai-contentsafety-py` | Harmful content detection for text and images |
| `azure-ai-contentunderstanding-py` | Multimodal extraction from documents, images, audio, video |
| `azure-ai-ml-py` | ML workspaces, training jobs, model registry, pipelines |
| `azure-ai-textanalytics-py` | Sentiment, entities, PII detection, healthcare NLP |
| `azure-ai-transcription-py` | Real-time and batch speech-to-text |
| `azure-ai-translation-document-py` | Batch document translation with format preservation |
| `azure-ai-translation-text-py` | Text translation, transliteration, language detection |
| `azure-ai-vision-imageanalysis-py` | Captions, OCR, object detection, smart cropping |
| `azure-speech-to-text-rest-py` | Short-audio transcription via REST |
| `m365-agents-py` | M365 Agents SDK for Teams/Copilot Studio |

#### .NET (8 skills)

| Skill | Package / Focus |
|-------|----------------|
| `azure-ai-projects-dotnet` | Foundry project client, versioned agents, evals |
| `azure-ai-agents-persistent-dotnet` | Low-level persistent agents with threads, runs, tools |
| `azure-ai-openai-dotnet` | Azure OpenAI chat, embeddings, image generation, audio |
| `azure-search-documents-dotnet` | AI Search -- full-text, vector, semantic, hybrid |
| `azure-ai-voicelive-dotnet` | Real-time voice AI over WebSocket |
| `azure-ai-document-intelligence-dotnet` | Document extraction and form recognition |
| `azure-mgmt-weightsandbiases-dotnet` | ML experiment tracking integration |
| `m365-agents-dotnet` | M365 Agents SDK for Teams/Copilot Studio |

#### TypeScript (7 skills)

| Skill | Package / Focus |
|-------|----------------|
| `azure-ai-projects-ts` | Foundry project client, agents, evals, OpenAI clients |
| `azure-search-documents-ts` | AI Search -- vector, hybrid, semantic, agentic retrieval |
| `azure-ai-voicelive-ts` | Real-time voice AI over WebSocket |
| `azure-ai-contentsafety-ts` | Harmful content detection |
| `azure-ai-document-intelligence-ts` | Document extraction |
| `azure-ai-translation-ts` | Text and document translation |
| `m365-agents-ts` | M365 Agents SDK for Teams/Copilot Studio |

#### Java (7 skills)

| Skill | Package / Focus |
|-------|----------------|
| `azure-ai-projects-java` | Foundry project management, connections, datasets, indexes |
| `azure-ai-agents-persistent-java` | Low-level persistent agents with threads, runs, tools |
| `azure-ai-voicelive-java` | Real-time voice conversations over WebSocket |
| `azure-ai-contentsafety-java` | Harmful content detection |
| `azure-ai-formrecognizer-java` | Document Intelligence / form recognition |
| `azure-ai-vision-imageanalysis-java` | Captions, OCR, object detection |
| `azure-ai-anomalydetector-java` | Time-series anomaly detection |

## Prerequisites

- **Azure account** with an AI Foundry project ([create one](https://learn.microsoft.com/azure/ai-foundry/how-to/create-projects))
- **Azure CLI** authenticated (`az login`)
- **Node.js 18+** (for the Azure MCP server)

## Authentication

The plugin uses `DefaultAzureCredential`. Authenticate via Azure CLI:

```bash
az login
```

Set your Foundry project endpoint:

```bash
export AZURE_AI_PROJECT_ENDPOINT="https://<resource>.services.ai.azure.com/api/projects/<project>"
```

## Quick Start

After installing the plugin, your coding agent can:

```
"Create a new Foundry project and deploy gpt-4o"
  -> microsoft-foundry orchestration skill routes to project/create then models/deploy-model

"Build a RAG agent with Azure AI Search"
  -> azure-ai-projects + azure-search-documents skills activate

"Add real-time voice to my agent"
  -> azure-ai-voicelive skill activates for your language

"Deploy a hosted agent with custom container"
  -> hosted-agents-v2-py / agents-v2-py skills activate

"What's the current API for creating a persistent agent in .NET?"
  -> Microsoft Docs MCP searches learn.microsoft.com for current patterns
```

## Plugin Structure

```
microsoft-foundry/
  .claude-plugin/
    plugin.json             # Plugin manifest
  .mcp.json                 # Azure MCP + Foundry MCP + Microsoft Docs MCP
  README.md
  skills/
    microsoft-foundry/      # Orchestration skill (project, models, agents, RBAC, quota)
    azure-ai-projects-py/   # Python Foundry SDK
    azure-ai-projects-dotnet/
    azure-ai-projects-ts/
    azure-ai-projects-java/
    agent-framework-azure-ai-py/
    agents-v2-py/
    hosted-agents-v2-py/
    azure-ai-agents-persistent-dotnet/
    azure-ai-agents-persistent-java/
    azure-search-documents-py/
    azure-search-documents-dotnet/
    azure-search-documents-ts/
    azure-ai-voicelive-py/
    azure-ai-voicelive-dotnet/
    azure-ai-voicelive-ts/
    azure-ai-voicelive-java/
    ... (39 skills total)
```

Skills are symlinked to their canonical sources in the `azure-sdk-*` and `azure-skills` plugins to maintain a single source of truth.

## License

MIT
