from fastapi import APIRouter, HTTPException, status

from app.schemas.models import (
    ElasticNetDiagnosisRequest,
    ElasticNetDiagnosisResponse,
    ImageDiagnosisRequest,
    ImageDiagnosisResult,
    MobileNetV3DiagnosisRequest,
    MobileNetV3DiagnosisResponse,
)
from app.vision.diagnosis import diagnose_image_bytes
from app.vision.elasticnet_service import run_elasticnet_diagnosis
from app.vision.mobilenetv3_service import run_mobilenetv3_diagnosis

router = APIRouter(prefix="/crop", tags=["vision"])


@router.post("/image-diagnosis", response_model=ImageDiagnosisResult, response_model_exclude_none=True)
def image_diagnosis(request: ImageDiagnosisRequest):
    """Production image diagnosis endpoint using heuristic color ratios and expert rules."""
    return diagnose_image_bytes(request.image_base64, crop_hint=request.crop_hint)


@router.post("/elasticnet-diagnosis", response_model=ElasticNetDiagnosisResponse)
def elasticnet_diagnosis(request: ElasticNetDiagnosisRequest):
    """
    Test inference endpoint for evaluating the trained ElasticNet classifier.
    Reuses exact training-time feature extraction and scaling.
    Kept separate from the live heuristic endpoint until field evaluation passes.
    """
    try:
        return run_elasticnet_diagnosis(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference error in ElasticNet test endpoint: {exc}",
        ) from exc


@router.post("/mobilenetv3-diagnosis", response_model=MobileNetV3DiagnosisResponse)
def mobilenetv3_diagnosis(request: MobileNetV3DiagnosisRequest):
    """
    Test inference endpoint for evaluating the trained MobileNetV3 transfer learning model.
    Reuses exact evaluation preprocessing, ImageNet normalization, and uncertainty rejection.
    Kept separate from the live heuristic endpoint until expert-verified field evaluation passes.
    """
    try:
        return run_mobilenetv3_diagnosis(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference error in MobileNetV3 test endpoint: {exc}",
        ) from exc
