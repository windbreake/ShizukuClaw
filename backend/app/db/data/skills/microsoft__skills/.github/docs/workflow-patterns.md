# Workflow Patterns: Combining Skills and Prompts

How to compose skills with prompts for multi-step workflows.

## Skills vs Prompts

| Component | Purpose | Location | When Used |
|-----------|---------|----------|-----------|
| **Skills** | Domain expertise, SDK patterns, coding standards | `.github/skills/` | Task matches skill description |
| **Prompts** | Reusable templates for specific actions | `.github/prompts/` | User invokes explicitly or agent selects |

Skills provide **knowledge**. Prompts provide **structure**.

## Composing Skills + Prompts

### Example 1: Adding a New API Endpoint

**Task**: "Add a PUT endpoint for updating user profiles"

**Components needed**:
- Skill: `fastapi-router-py` — FastAPI patterns, response models, auth
- Skill: `pydantic-models-py` — Request/response schema patterns
- Prompt: `add-endpoint.prompt.md` — Step-by-step endpoint creation template

**Workflow**:

```
1. Agent loads fastapi-router-py skill
   → Learns: Router patterns, dependency injection, response models
   
2. Agent loads pydantic-models-py skill
   → Learns: Base/Create/Update/Response model pattern
   
3. Agent uses add-endpoint.prompt.md structure:
   → Step 1: Define Pydantic models (UserUpdate, UserResponse)
   → Step 2: Create router with PUT handler
   → Step 3: Add authentication dependency
   → Step 4: Write tests
```

### Example 2: Building a Data Service with Storage

**Task**: "Create a document service backed by Cosmos DB"

**Components needed**:
- Skill: `azure-cosmos-db-py` — Cosmos DB service patterns
- Skill: `azure-identity-py` — Authentication with DefaultAzureCredential
- Skill: `pydantic-models-py` — Model definitions

**Workflow**:

```
1. Agent loads azure-identity-py skill
   → Establishes: Use DefaultAzureCredential, never hardcode credentials
   
2. Agent loads azure-cosmos-db-py skill
   → Learns: Service layer pattern, partition key strategy, parameterized queries
   
3. Agent loads pydantic-models-py skill
   → Learns: Model variant pattern (Base, Create, Update, Response, InDB)
   
4. Agent implements:
   → DocumentBase, DocumentCreate, DocumentResponse models
   → DocumentService class with CRUD operations
   → Proper error handling and logging
```

### Example 3: Frontend Component with State

**Task**: "Create a workflow editor with draggable nodes"

**Components needed**:
- Skill: `react-flow-node-ts` — Custom React Flow nodes
- Skill: `zustand-store-ts` — State management
- Prompt: `create-node.prompt.md` — Node component template
- Prompt: `create-store.prompt.md` — Store creation template

**Workflow**:

```
1. Agent uses create-store.prompt.md with zustand-store-ts skill
   → Creates: workflowStore with nodes, edges, actions
   
2. Agent uses create-node.prompt.md with react-flow-node-ts skill
   → Creates: Custom node components with handles, TypeScript types
   
3. Agent integrates components
   → Connects store to React Flow canvas
   → Adds drag-drop functionality
```

## Multi-Step Workflow Template

For complex tasks, structure the workflow explicitly:

```markdown
## Task: [Description]

### Step 1: [Setup]
- Load skills: [skill-1], [skill-2]
- Verify: [check]

### Step 2: [Implementation]
- Use prompt: [prompt-name]
- Apply patterns from: [skill-name]
- Verify: [check]

### Step 3: [Integration]
- Connect components
- Verify: [check]

### Step 4: [Testing]
- Write tests following TDD pattern
- Verify: All tests pass
```

## Prompt Templates in This Repository

| Prompt | Purpose | Combines Well With |
|--------|---------|-------------------|
| `add-endpoint.prompt.md` | Create REST API endpoints | `fastapi-router-py`, `pydantic-models-py` |
| `create-store.prompt.md` | Create Zustand stores | `zustand-store-ts` |
| `create-node.prompt.md` | Create React Flow nodes | `react-flow-node-ts` |
| `code-review.prompt.md` | Review code changes | Any skill for domain context |

## Best Practices

### 1. Load Skills Before Prompts

Skills establish context and patterns. Prompts structure the execution.

```
CORRECT:
1. Load azure-cosmos-db-py (establishes patterns)
2. Apply add-endpoint.prompt.md (structures implementation)

WRONG:
1. Apply add-endpoint.prompt.md (no domain context)
2. Load azure-cosmos-db-py (too late, patterns not applied)
```

### 2. Limit Active Skills

Keep 2-3 relevant skills active at once. More causes context dilution.

```
GOOD: fastapi-router-py + pydantic-models-py + azure-cosmos-db-py
BAD:  Loading all 127 skills "just in case"
```

### 3. Chain Skills for Complex Domains

When a task spans multiple domains, chain skills in logical order:

```
Authentication → Data Layer → API Layer → Frontend
azure-identity-py → azure-cosmos-db-py → fastapi-router-py → react-flow-node-ts
```

### 4. Use Prompts for Repeatability

If you do the same workflow often, create a prompt template:

```markdown
---
name: new-azure-endpoint
description: Create a new Azure-backed API endpoint with full stack
---

## Steps

1. Load skills: azure-identity-py, [data-skill], fastapi-router-py
2. Create Pydantic models for request/response
3. Implement service layer with Azure SDK
4. Create FastAPI router with endpoint
5. Add authentication dependency
6. Write tests
```
