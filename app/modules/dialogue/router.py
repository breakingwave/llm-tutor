import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.models.chat import ChatRequest
from app.services.session_store import SessionStore
from app.services.llm import LLMService
from app.modules.dialogue.service import DialogueService
from app.services.session_helpers import get_or_create_chat_session, pick_curriculum
from app.dependencies import (
    get_llm_service,
    get_session_store,
    get_settings,
    get_vector_store_service,
)

logger = logging.getLogger("llm_tutor.dialogue.router")
router = APIRouter(prefix="/api/chat", tags=["chat"])


def _get_dialogue_service(
    llm_service: LLMService = Depends(get_llm_service),
) -> DialogueService:
    settings = get_settings()
    return DialogueService(
        llm_service,
        settings.dialogue,
    ).configure_retrieval(
        vector_store=get_vector_store_service(),
        openstax_collection_name=settings.openstax.collection_name,
    )


@router.post("/send")
async def send_message(
    request: ChatRequest,
    store: SessionStore = Depends(get_session_store),
    dialogue: DialogueService = Depends(_get_dialogue_service),
):
    session_data = store.get(request.session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    chat_session = get_or_create_chat_session(session_data, request.session_id)

    if request.curriculum_item_id:
        chat_session.active_item_id = request.curriculum_item_id

    curriculum = pick_curriculum(session_data)
    rag_context, rag_chunk_ids = await dialogue.build_rag_context(
        profile=session_data.user_profile,
        message=request.message,
        curriculum=curriculum,
        active_item_id=chat_session.active_item_id,
    )

    async def event_generator():
        try:
            async for token in dialogue.chat_stream(
                profile=session_data.user_profile,
                chat_session=chat_session,
                message=request.message,
                curriculum=curriculum,
                active_item_id=chat_session.active_item_id,
                rag_context=rag_context,
                rag_chunk_ids=rag_chunk_ids,
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

    chat_session = get_or_create_chat_session(session_data, session_id)
    return {
        "session_id": session_id,
        "messages": [m.model_dump(mode="json") for m in chat_session.messages],
    }
