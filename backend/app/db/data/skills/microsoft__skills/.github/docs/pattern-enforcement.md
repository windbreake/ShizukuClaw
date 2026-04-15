# Pattern Enforcement with Skills

How skills enforce coding patterns, standards, and best practices across teams.

## How Skills Enforce Patterns

Skills contain explicit instructions that agents follow. When a skill says "Always use X", the agent applies that pattern consistently.

### Example: Authentication Pattern Enforcement

The `azure-identity-py` skill contains:

```markdown
## Authentication

Always use `DefaultAzureCredential` for production code:

```python
from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient

credential = DefaultAzureCredential()
client = CosmosClient(url=endpoint, credential=credential)
```

Never hardcode credentials or use connection strings in code.
```

**Result**: Every agent with this skill loaded will use `DefaultAzureCredential`, never hardcoded secrets.

## Standard Patterns Enforced by Skills

### 1. Authentication (azure-identity-py)

| Enforced Pattern | Prevented Anti-Pattern |
|------------------|------------------------|
| `DefaultAzureCredential` | Hardcoded credentials |
| Environment variables for config | Secrets in code |
| Managed identity in production | Connection strings |

### 2. Error Handling (all skills)

| Enforced Pattern | Prevented Anti-Pattern |
|------------------|------------------------|
| Explicit exception handling | Empty `except:` blocks |
| Specific exception types | Catching `Exception` |
| Meaningful error messages | Silent failures |

### 3. Async/Await (Azure SDK skills)

| Enforced Pattern | Prevented Anti-Pattern |
|------------------|------------------------|
| `async/await` for I/O | Blocking synchronous calls |
| Context managers | Unclosed clients |
| Proper client lifecycle | Resource leaks |

### 4. Type Safety (all skills)

| Enforced Pattern | Prevented Anti-Pattern |
|------------------|------------------------|
| Type hints on functions | Untyped parameters |
| Pydantic models | Raw dicts |
| Explicit return types | Implicit `Any` |

## Team Standardization

### Sharing Skills Across Projects

Teams can enforce consistent patterns by sharing the same skill set:

```bash
# Team skill repository
team-skills/
├── .github/skills/
│   ├── azure-identity-py/      # Auth patterns
│   ├── azure-cosmos-db-py/     # Data layer patterns  
│   ├── fastapi-router-py/      # API patterns
│   └── team-conventions/       # Custom team rules
```

Every project symlinks to the team skills:

```bash
# In each project
ln -s /path/to/team-skills/.github/skills .github/skills
```

**Result**: All projects use identical patterns. Updates propagate instantly.

### Custom Team Skills

Create team-specific skills for internal conventions:

```markdown
---
name: team-conventions
description: Internal coding standards for the platform team
---

# Team Conventions

## API Response Format

All endpoints must return:
```python
{
    "data": <result>,
    "meta": {
        "request_id": str,
        "timestamp": str
    }
}
```

## Logging

Use structured logging with correlation IDs:
```python
logger.info("Operation completed", extra={
    "correlation_id": request.state.correlation_id,
    "operation": "create_user",
    "duration_ms": elapsed
})
```

## Database Queries

Always use parameterized queries:
```python
# CORRECT
query = "SELECT * FROM c WHERE c.id = @id"
params = [{"name": "@id", "value": user_id}]

# WRONG - SQL injection risk
query = f"SELECT * FROM c WHERE c.id = '{user_id}'"
```
```

## Enforcement Verification

### Pre-Commit Checks

Skills work best with automated verification:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: type-check
        name: Type checking
        entry: mypy src/
        language: system
        
      - id: lint
        name: Linting
        entry: ruff check src/
        language: system
```

### Code Review Checklist

Skills provide implicit review criteria:

| If Skill Loaded | Reviewer Checks |
|-----------------|-----------------|
| `azure-identity-py` | No hardcoded credentials? |
| `azure-cosmos-db-py` | Partition key strategy documented? |
| `fastapi-router-py` | Response models defined? |
| `pydantic-models-py` | Using model variants correctly? |

## Pattern Enforcement Examples

### Example 1: Cosmos DB Service Layer

**Skill**: `azure-cosmos-db-py`

**Enforced patterns**:
- Service class wraps CosmosClient
- Partition key included in all operations
- Parameterized queries for safety
- Dual auth support (DefaultAzureCredential + emulator)

```python
# Agent generates this pattern consistently
class UserService:
    def __init__(self, client: CosmosClient, database: str, container: str):
        self.container = client.get_database_client(database).get_container_client(container)
    
    async def get_user(self, user_id: str, partition_key: str) -> User:
        query = "SELECT * FROM c WHERE c.id = @id"
        params = [{"name": "@id", "value": user_id}]
        items = self.container.query_items(query, parameters=params, partition_key=partition_key)
        # ...
```

### Example 2: FastAPI Router

**Skill**: `fastapi-router-py`

**Enforced patterns**:
- Router with prefix and tags
- Dependency injection for auth
- Pydantic response models
- Proper HTTP status codes

```python
# Agent generates this pattern consistently
router = APIRouter(prefix="/users", tags=["users"])

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service)
) -> UserResponse:
    user = await service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.from_orm(user)
```

### Example 3: Pydantic Models

**Skill**: `pydantic-models-py`

**Enforced patterns**:
- Base model with shared fields
- Create model (no id, no timestamps)
- Update model (all optional)
- Response model (computed fields)
- InDB model (with id, timestamps)

```python
# Agent generates this pattern consistently
class UserBase(BaseModel):
    email: EmailStr
    name: str

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: EmailStr | None = None
    name: str | None = None

class UserResponse(UserBase):
    id: str
    created_at: datetime

class UserInDB(UserResponse):
    hashed_password: str
```

## Benefits of Skill-Based Enforcement

| Benefit | How Skills Achieve It |
|---------|----------------------|
| **Consistency** | Same patterns across all code |
| **Onboarding** | New devs inherit team standards |
| **Maintenance** | Update skill = update all future code |
| **Auditing** | Skills document "why" not just "what" |
| **Evolution** | Patterns improve over time |
