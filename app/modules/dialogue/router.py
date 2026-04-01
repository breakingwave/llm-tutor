import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.models.chat import ChatRequest, ChatSession
from app.models.curriculum import Curriculum
from app.services.session_store import SessionStore, SessionData
from app.services.llm import LLMService
from app.modules.dialogue.service import DialogueService
from app.dependencies import get_session_store, get_llm_service, get_settings

logger = logging.getLogger("llm_tutor.dialogue.router")
router = APIRouter(prefix="/api/chat", tags=["chat"])


def _get_dialogue_service(
    llm_service: LLMService = Depends(get_llm_service),
) -> DialogueService:
    settings = get_settings()
    return DialogueService(llm_service, settings.dialogue)


@router.post("/send")
async def send_message(
    request: ChatRequest,
    store: SessionStore = Depends(get_session_store),
    dialogue: DialogueService = Depends(_get_dialogue_service),
):
    session_data = store.get(request.session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    chat_session = _get_or_create_chat_session(session_data, request.session_id)

    if request.curriculum_item_id:
        chat_session.active_item_id = request.curriculum_item_id

    curriculum = _pick_curriculum(session_data)

    # TODO: Add RAG context retrieval here when vector store is ready
    rag_context = None

    async def event_generator():
        try:
            async for token in dialogue.chat_stream(
                profile=session_data.user_profile,
                chat_session=chat_session,
                message=request.message,
                curriculum=curriculum,
                active_item_id=chat_session.active_item_id,
                rag_context=rag_context,
            ):
                yield {"event": "token", "data": json.dumps({"token": token})}
            yield {"event": "done", "data": json.dumps({"status": "complete"})}
        except Exception as e:
            logger.error("Stream error: %s", e)
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
        finally:
            store.save(request.session_id)

    return EventSourceResponse(event_generator())


@router.get("/history/{session_id}")
async def get_chat_history(
    session_id: str,
    store: SessionStore = Depends(get_session_store),
):
    session_data = store.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    chat_session = _get_or_create_chat_session(session_data, session_id)
    return {
        "session_id": session_id,
        "messages": [m.model_dump(mode="json") for m in chat_session.messages],
    }


def _pick_curriculum(session_data: SessionData) -> Curriculum | None:
    curricula = session_data.curricula or []
    if not curricula:
        return None
    primary_topic = None
    if session_data.user_profile.goals:
        primary_topic = session_data.user_profile.goals[0].topic
    if primary_topic:
        for c in curricula:
            if c.goal_topic == primary_topic:
                return c
    return curricula[-1]


def _get_or_create_chat_session(session_data: SessionData, user_id: str) -> ChatSession:
    if session_data.chat_sessions:
        return session_data.chat_sessions[0]
    chat = ChatSession(user_id=user_id)
    session_data.chat_sessions.append(chat)
    return chat
