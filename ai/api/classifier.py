from fastapi import APIRouter

from ai.schemas.classifier import ClassifierRequest, ClassifierResponse
from ai.services.classifier_service import ClassifierService


router = APIRouter(prefix="/classifier", tags=["classifier"])
ai_router = APIRouter(prefix="/ai", tags=["classifier"])


@router.post("", response_model=ClassifierResponse)
def classify(request: ClassifierRequest) -> ClassifierResponse:
    return ClassifierService().classify(request)


@ai_router.post("/classify", response_model=ClassifierResponse)
def classify_ai(request: ClassifierRequest) -> ClassifierResponse:
    return ClassifierService().classify(request)
