from fastapi import APIRouter, status

from app.models.relationship import FamilyRelationship
from app.schemas.family import RelationshipItem, RelationshipListResponse

router = APIRouter(tags=["Relationships"])


@router.get(
    "/family-relationships",
    response_model=RelationshipListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Family Relationships",
    description="Retrieve all supported family relationships for dynamic UI rendering.",
)
async def get_family_relationships():
    """Return all available family relationships."""
    items = [
        RelationshipItem(value=rel.value, label=rel.label)
        for rel in FamilyRelationship
    ]
    return RelationshipListResponse(data=items)
