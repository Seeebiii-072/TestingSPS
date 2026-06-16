from fastapi import APIRouter, HTTPException, status

from ai.schemas.classifier import ClassifierRequest, ClassifierResponse
from ai.services.classifier_service import ClassifierService


router = APIRouter(prefix="/classify", tags=["classifier"])


@router.post("", response_model=ClassifierResponse)
def classify(request: ClassifierRequest) -> ClassifierResponse:
    try:
        return ClassifierService().classify(request)
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        ) from exc