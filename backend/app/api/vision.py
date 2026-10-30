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
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "ElasticNet vision stack is not installed. "
                "Install with: uv sync --extra vision"
            ),
        ) from exc
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
    Prefer VISION_INFERENCE_URL (free HF Space) on slim hosts; else local torch extra.
    """
    from app.core.config import get_settings

    settings = get_settings()
    if settings.vision_inference_url:
        try:
            from app.vision.remote_mobilenet import diagnose_image_via_remote

            result = diagnose_image_via_remote(
                request.image_base64,
                crop_hint=request.crop_hint,
                confidence_threshold=request.confidence_threshold,
            )
            return MobileNetV3DiagnosisResponse(
                status=result.status,
                rejection_reason=result.rejection_reason,
                plant_name=result.plant_name,
                predicted_disease=result.predicted_disease,
                is_healthy=result.is_healthy,
                predicted_class=result.predicted_disease,
                crop_id=result.crop_id,
                disease=result.disease,
                confidence=result.confidence,
                confidence_is_calibrated=result.confidence_is_calibrated,
                top_3=result.top_3,
                requires_expert=result.requires_expert,
                treatment_hints=result.treatment_hints,
                image_quality_score=result.image_quality_score,
                inference_time_ms=float(result.latency_ms or 0.0),
                model_version=result.model_version or "mobilenetv3_plantdisease_best",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Remote MobileNet unavailable: {exc}",
            ) from exc

    try:
        from app.vision.mobilenetv3_service import run_mobilenetv3_diagnosis

        return run_mobilenetv3_diagnosis(request)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "MobileNetV3 vision stack is not installed. "
                "Set VISION_INFERENCE_URL to a free HF Space, or install: uv sync --extra vision"
            ),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference error in MobileNetV3 test endpoint: {exc}",
        ) from exc
