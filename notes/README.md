# Notes Directory

Gregory uses Markdown notes for context when chatting. Files in this directory are loaded and passed to the AI as system context.

## File Structure

| File | Purpose |
|------|---------|
| `household.md` | Shared household notes (schedules, house rules, shared context) |
| `{user_id}.md` | Per-user notes (e.g. `alice.md`, `bob.md`) — preferences, reminders, personal context |

## Usage

- Notes are read before each chat and included in the system prompt.
- User IDs are sanitized: only alphanumeric, `-`, and `_` are allowed in filenames.
- Empty or missing files are ignored.

## Example

**household.md:**
```markdown
# Household
- Dog feeding: 7am and 6pm
- Trash day: Tuesday
```

**alice.md:**
```markdown
# Alice
- Prefers reminders for morning meetings
- Allergic to nuts
```

See [CONFIGURATION.md](../docs/CONFIGURATION.md) for `NOTES_PATH` and [ARCHITECTURE.md](../docs/ARCHITECTURE.md) for the data flow.
