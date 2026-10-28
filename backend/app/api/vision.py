from fastapi import APIRouter, Depends, HTTPException, status

from app.db.users import UserRow
from app.schemas.models import (
    ElasticNetDiagnosisRequest,
    ElasticNetDiagnosisResponse,
    ImageDiagnosisRequest,
    ImageDiagnosisResult,
    MobileNetV3DiagnosisRequest,
    MobileNetV3DiagnosisResponse,
)
from app.services.auth_service import get_current_user
from app.vision.diagnosis import diagnose_image_bytes

router = APIRouter(prefix="/crop", tags=["vision"])


@router.post("/image-diagnosis", response_model=ImageDiagnosisResult, response_model_exclude_none=True)
def image_diagnosis(
    request: ImageDiagnosisRequest,
    _user: UserRow = Depends(get_current_user),
):
    """Production image diagnosis endpoint using heuristic color ratios and expert rules."""
    return diagnose_image_bytes(request.image_base64, crop_hint=request.crop_hint)


@router.post("/elasticnet-diagnosis", response_model=ElasticNetDiagnosisResponse)
def elasticnet_diagnosis(
    request: ElasticNetDiagnosisRequest,
    _user: UserRow = Depends(get_current_user),
):
    """
    Test inference endpoint for evaluating the trained ElasticNet classifier.
    Reuses exact training-time feature extraction and scaling.
    Kept separate from the live heuristic endpoint until field evaluation passes.
    """
    try:
        from app.vision.elasticnet_service import run_elasticnet_diagnosis

        return run_elasticnet_diagnosis(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference error in ElasticNet test endpoint: {exc}",
        ) from exc


@router.post("/mobilenetv3-diagnosis", response_model=MobileNetV3DiagnosisResponse)
def mobilenetv3_diagnosis(
    request: MobileNetV3DiagnosisRequest,
    _user: UserRow = Depends(get_current_user),
):
    """
    Test inference endpoint for evaluating the trained MobileNetV3 transfer learning model.
    Reuses exact evaluation preprocessing, ImageNet normalization, and uncertainty rejection.
    Kept separate from the live heuristic endpoint until expert-verified field evaluation passes.
    """
    try:
        from app.vision.mobilenetv3_service import run_mobilenetv3_diagnosis

        return run_mobilenetv3_diagnosis(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference error in MobileNetV3 test endpoint: {exc}",
        ) from exc
