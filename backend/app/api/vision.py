from fastapi import APIRouter

from app.schemas.models import ImageDiagnosisRequest, ImageDiagnosisResult
from app.vision.diagnosis import diagnose_image_bytes

router = APIRouter(prefix="/crop", tags=["vision"])


@router.post("/image-diagnosis", response_model=ImageDiagnosisResult)
def image_diagnosis(request: ImageDiagnosisRequest):
    return diagnose_image_bytes(request.image_base64, crop_hint=request.crop_hint)
