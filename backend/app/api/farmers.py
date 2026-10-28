from fastapi import APIRouter, Depends, HTTPException

from app.db.session import create_farm_context, get_farm_context, update_farm_context
from app.db.users import UserRow
from app.schemas.models import FarmContext, FarmContextCreate, FarmContextUpdate
from app.services.auth_service import assert_farmer_access, get_current_user

router = APIRouter(prefix="/farmers", tags=["farmers"])


@router.post("", response_model=FarmContext, status_code=201)
def create_farmer(
    payload: FarmContextCreate,
    user: UserRow = Depends(get_current_user),
):
    assert_farmer_access(user, payload.farmer_id)
    try:
        return create_farm_context(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{farmer_id}", response_model=FarmContext)
def read_farmer(
    farmer_id: str,
    user: UserRow = Depends(get_current_user),
):
    assert_farmer_access(user, farmer_id)
    context = get_farm_context(farmer_id)
    if not context:
        raise HTTPException(status_code=404, detail=f"Farmer {farmer_id} not found")
    return context


@router.put("/{farmer_id}", response_model=FarmContext)
def put_farmer(
    farmer_id: str,
    payload: FarmContextUpdate,
    user: UserRow = Depends(get_current_user),
):
    assert_farmer_access(user, farmer_id)
    context = update_farm_context(farmer_id, payload)
    if not context:
        raise HTTPException(status_code=404, detail=f"Farmer {farmer_id} not found")
    return context
