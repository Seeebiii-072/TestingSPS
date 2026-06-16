from fastapi import APIRouter, HTTPException, status

from ai.schemas.summariser import SummariserRequest, SummariserResponse
from ai.services.summariser_service import SummariserService


router = APIRouter(prefix="/summarise", tags=["summariser"])


@router.post("", response_model=SummariserResponse)
def summarise(request: SummariserRequest) -> SummariserResponse:
    try:
        return SummariserService().summarise(request)
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        ) from exc