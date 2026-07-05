from ai.chat.assistant import ChatAssistant
from ai.schemas.chat import ChatRequest, ChatResponse


class ChatService:
    def __init__(self, assistant: ChatAssistant | None = None) -> None:
        self._assistant = assistant or ChatAssistant()

    async def respond(self, request: ChatRequest) -> ChatResponse:
        return await self._assistant.respond_async(request)
