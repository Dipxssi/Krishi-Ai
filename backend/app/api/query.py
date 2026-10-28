from fastapi import APIRouter, Depends, HTTPException

from app.db.session import get_farm_context
from app.db.users import UserRow
from app.orchestrator.orchestrator import handle_query
from app.schemas.models import QueryRequest, QueryResponse
from app.services.auth_service import assert_farmer_access, get_current_user

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query_endpoint(
    request: QueryRequest,
    user: UserRow = Depends(get_current_user),
):
    assert_farmer_access(user, request.farmer_id)
    context = get_farm_context(request.farmer_id)
    if not context:
        raise HTTPException(
            status_code=404,
            detail=f"Farmer {request.farmer_id} not found. Create FarmContext via POST /farmers first.",
        )
    return handle_query(
        request.query,
        context,
        image_base64=request.image_base64,
        selected_crop=request.selected_crop,
        vision_model=request.vision_model,
        language=request.language,
    )
