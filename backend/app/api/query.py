from fastapi import APIRouter, HTTPException

from app.db.session import get_farm_context
from app.orchestrator.orchestrator import handle_query
from app.schemas.models import QueryRequest, QueryResponse

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query_endpoint(request: QueryRequest):
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
    )
