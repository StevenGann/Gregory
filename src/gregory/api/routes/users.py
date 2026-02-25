"""Users route - list family members."""

from fastapi import APIRouter

from gregory.api.schemas import UsersResponse
from gregory.config import get_settings
from gregory.notes.service import NotesService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UsersResponse)
async def list_users() -> UsersResponse:
    """List known family members (from config and notes directory)."""
    settings = get_settings()
    notes = NotesService()

    users: set[str] = set()

    # From config
    if settings.family_members:
        for u in settings.family_members.split(","):
            u = u.strip().lower()
            if u:
                users.add(u)

    # From notes directory
    for u in notes.list_users_from_notes():
        users.add(u)

    return UsersResponse(users=sorted(users))
