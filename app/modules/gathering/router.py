import asyncio
import logging
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.services.session_store import SessionStore
from app.services.llm import LLMService
from app.services.search import SearchService
from app.modules.gathering.service import GatheringService
from app.dependencies import (
    get_session_store,
    get_llm_service,
    get_settings,
    get_api_logger,
    get_env_settings,
    get_vector_store_service,
)

logger = logging.getLogger("llm_tutor.gathering.router")
router = APIRouter(prefix="/api/gathering", tags=["gathering"])


class GatheringStartRequest(BaseModel):
    session_id: str
    goal_topic: str | None = None
    depth: str = "introductory"


def _get_gathering_service(
    llm_service: LLMService = Depends(get_llm_service),
) -> GatheringService:
    settings = get_settings()
    env = get_env_settings()
    api_logger = get_api_logger()
    search_service = SearchService(env.tavily_api_key, settings.gathering, api_logger)
    vector_store = get_vector_store_service()
    return GatheringService(
        llm_service, search_service, settings.gathering,
        vector_store=vector_store,
        openstax_collection_name=settings.openstax.collection_name,
    )


@router.post("/start")
async def start_gathering(
    request: GatheringStartRequest,
    background_tasks: BackgroundTasks,
    store: SessionStore = Depends(get_session_store),
    service: GatheringService = Depends(_get_gathering_service),
):
    session_data = store.get(request.session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    goal_topic = request.goal_topic
    if not goal_topic and session_data.user_profile.goals:
        goal_topic = session_data.user_profile.goals[0].topic
    if not goal_topic:
        raise HTTPException(status_code=400, detail="No learning goal specified")

    task_id = str(uuid4())
    session_data.gathering_tasks[task_id] = {
        "status": "running",
        "goal_topic": goal_topic,
        "progress": [],
        "materials_count": 0,
    }
    store.save(request.session_id)

    background_tasks.add_task(
        _run_gathering_task,
        service, store, request.session_id, task_id, goal_topic, request.depth,
    )

    return {"task_id": task_id, "status": "started"}


async def _run_gathering_task(
    service: GatheringService,
    store: SessionStore,
    session_id: str,
    task_id: str,
    goal_topic: str,
    depth: str,
):
    session_data = store.get(session_id)
    if not session_data:
        return

    task_info = session_data.gathering_tasks.get(task_id, {})

    def on_progress(update: dict):
        task_info.setdefault("progress", []).append(update)
        task_info["materials_count"] = update.get("total_materials", task_info.get("materials_count", 0))
        store.save(session_id)

    try:
        materials = await service.run_gathering(
            profile=session_data.user_profile,
            goal_topic=goal_topic,
            depth=depth,
            on_progress=on_progress,
        )
        session_data.materials.extend(materials)
        task_info["status"] = "completed"
        task_info["materials_count"] = len(materials)

        # Chunk and embed Tavily materials into vector store
        try:
            indexed = await service.index_materials(materials, session_id=session_id)
            logger.info("Indexed %d chunks for session %s", indexed, session_id)
        except Exception as e:
            logger.error("Material indexing failed: %s", e)
    except Exception as e:
        logger.error("Gathering task failed: %s", e)
        task_info["status"] = "failed"
        task_info["error"] = str(e)
    finally:
        store.save(session_id)


@router.get("/status/{task_id}")
async def get_gathering_status(
    task_id: str,
    session_id: str,
    store: SessionStore = Depends(get_session_store),
):
    session_data = store.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    task_info = session_data.gathering_tasks.get(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task_id,
        "status": task_info.get("status"),
        "materials_count": task_info.get("materials_count", 0),
        "progress": task_info.get("progress", []),
    }


@router.get("/results/{task_id}")
async def get_gathering_results(
    task_id: str,
    session_id: str,
    store: SessionStore = Depends(get_session_store),
):
    session_data = store.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    task_info = session_data.gathering_tasks.get(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task_id,
        "status": task_info.get("status"),
        "materials": [m.model_dump(mode="json") for m in session_data.materials],
    }
