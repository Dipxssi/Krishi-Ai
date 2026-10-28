from fastapi import APIRouter, Depends, HTTPException

from app.db.users import UserRow
from app.schemas.models import FeedbackRequest
from app.services.audit import get_query_run, list_feedback, save_feedback
from app.services.auth_service import get_current_user

router = APIRouter(tags=["audit"])


@router.get("/audit/{request_id}")
def audit_request(
    request_id: str,
    _user: UserRow = Depends(get_current_user),
):
    record = get_query_run(request_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Request {request_id} not found")
    return record


@router.post("/feedback")
def submit_feedback(
    payload: FeedbackRequest,
    _user: UserRow = Depends(get_current_user),
):
    save_feedback(payload.request_id, payload.rating, payload.comment, payload.expert_verdict)
    return {"status": "ok"}


@router.get("/feedback/export")
def export_feedback(
    limit: int = 100,
    _user: UserRow = Depends(get_current_user),
):
    return {"items": list_feedback(limit=limit)}
