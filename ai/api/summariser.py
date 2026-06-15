from fastapi import APIRouter

from ai.schemas.summariser import SummariserRequest, SummariserResponse
from ai.services.summariser_service import SummariserService


router = APIRouter(prefix="/summariser", tags=["summariser"])
ai_router = APIRouter(prefix="/ai", tags=["summariser"])


@router.post("", response_model=SummariserResponse)
def summarise(request: SummariserRequest) -> SummariserResponse:
    return SummariserService().summarise(request)


@ai_router.post("/summarise", response_model=SummariserResponse)
def summarise_ai(request: SummariserRequest) -> SummariserResponse:
    return SummariserService().summarise(request)
