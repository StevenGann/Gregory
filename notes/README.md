# Notes Directory

Markdown notes loaded as system context before each chat.

## File Structure

| File / Folder | Purpose |
|---|---|
| `household.md` | Shared household context (schedules, rules) |
| `gregory.md` | Gregory's self-notes — experiences, thoughts, preferences |
| `services.md` | Local services and contacts |
| `entities/*.md` | Notes about things (e.g. `dog.md`, `house.md`, `garden.md`) |
| `{user_id}.md` | Per-user notes (e.g. `alice.md`, `bob.md`) — preferences, reminders |

Filenames are sanitized: alphanumeric, `-`, and `_` only. Empty or missing files are ignored.

## Flow

```mermaid
flowchart TB
    subgraph notes_dir [notes/]
        household[household.md]
        gregory[gregory.md]
        services[services.md]
        entities[entities/*.md]
        user[alice.md, bob.md, ...]
    end

    subgraph loader [Notes Loader]
        Load[load_notes_for_chat]
    end

    subgraph usage [Usage]
        SystemPrompt[System Prompt]
        Chat[Chat Response]
    end

    subgraph observations [Observations - if enabled]
        Obs[Extract blocks]
        Append[Append to notes]
    end

    household --> Load
    gregory --> Load
    services --> Load
    entities --> Load
    user --> Load
    Load --> SystemPrompt
    SystemPrompt --> Chat
    Chat -.-> Obs
    Obs -.-> Append
    Append -.-> notes_dir
```

## Observations

When `OBSERVATIONS_ENABLED=true`, Gregory can append to notes using these block types:

| Block | Target |
|---|---|
| `[OBSERVATION: ...]` | User note |
| `[GREGORY_NOTE: ...]` | `gregory.md` |
| `[HOUSEHOLD_NOTE: ...]` | `household.md` |
| `[NOTE:entity: ...]` | `entities/{entity}.md` |

## Examples

**`household.md`**
```markdown
# Household
- Dog feeding: 7am and 6pm
- Trash day: Tuesday
```

**`gregory.md`**
```markdown
# Gregory
- Prefers concise answers unless asked to elaborate
- Has learned the family prefers informal tone
```

**`services.md`**
```markdown
# Local Services

## Pepper's care
- Primary care: Dr. X, 555-1234
- Urgent care: Clinic Y, 555-5678
- Pharmacy: Pharmacy Z, 555-9012

## Emergency
- Poison control: 1-800-222-1222
- Nearest ER: Hospital A, 555-0000
```

**`entities/dog.md`**
```markdown
# Dog
- Name: Max
- Loves bacon treats
```

**`alice.md`**
```markdown
# Alice
- Prefers reminders for morning meetings
- Allergic to nuts
```

## See Also

- [CONFIGURATION.md](../docs/CONFIGURATION.md) — `NOTES_PATH` setting
- [ARCHITECTURE.md](../docs/ARCHITECTURE.md) — data flow details
