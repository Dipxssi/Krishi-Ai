from fastapi import APIRouter, HTTPException

from app.db.session import get_farm_context
from app.orchestrator.router import route_for_debug
from app.schemas.models import RouteRequest, RouteResponse
from app.services.audit import new_request_id

router = APIRouter(tags=["routing"])


@router.post("/route", response_model=RouteResponse)
def route_endpoint(request: RouteRequest):
    context = get_farm_context(request.farmer_id) if request.farmer_id else None
    if request.farmer_id and not context:
        raise HTTPException(status_code=404, detail=f"Farmer {request.farmer_id} not found")
    debug = route_for_debug(
        request.query,
        context,
        has_image=bool(request.image_url),
    )
    return RouteResponse(
        request_id=new_request_id(),
        selected_agents=debug["selected_agents"],
        agent_scores=debug["agent_scores"],
        missing_information=debug["missing_information"],
        risk_level=debug["risk_level"],
        routing_mode=debug["routing_mode"],
    )
