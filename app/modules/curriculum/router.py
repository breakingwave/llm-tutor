import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.curriculum import CurriculumItem
from app.services.session_store import SessionStore
from app.services.llm import LLMService
from app.modules.curriculum.service import CurriculumService
from app.dependencies import get_session_store, get_llm_service, get_settings

logger = logging.getLogger("llm_tutor.curriculum.router")
router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])


class GenerateRequest(BaseModel):
    session_id: str
    goal_topic: str | None = None
    depth: str = "introductory"


class UpdateItemRequest(BaseModel):
    title: str | None = None
    content_outline: str | None = None
    completed: bool | None = None
    order: int | None = None


class AddItemRequest(BaseModel):
    session_id: str
    title: str
    content_outline: str = ""
    order: int | None = None


def _get_curriculum_service(
    llm_service: LLMService = Depends(get_llm_service),
) -> CurriculumService:
    settings = get_settings()
    return CurriculumService(llm_service, settings.curriculum)


@router.post("/generate")
async def generate_curriculum(
    request: GenerateRequest,
    store: SessionStore = Depends(get_session_store),
    service: CurriculumService = Depends(_get_curriculum_service),
):
    session_data = store.get(request.session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    profile = session_data.user_profile
    materials = session_data.materials

    goal_topic = request.goal_topic
    if not goal_topic and profile.goals:
        goal_topic = profile.goals[0].topic
    if not goal_topic:
        raise HTTPException(status_code=400, detail="No learning goal specified")

    curriculum = await service.generate_curriculum(
        profile=profile,
        materials=materials,
        goal_topic=goal_topic,
        depth=request.depth,
    )

    session_data.curricula.append(curriculum)
    store.save(request.session_id)

    return curriculum.model_dump(mode="json")


@router.get("/{curriculum_id}")
async def get_curriculum(
    curriculum_id: str,
    session_id: str,
    store: SessionStore = Depends(get_session_store),
):
    session_data = store.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    for c in session_data.curricula:
        if c.id == curriculum_id:
            return c.model_dump(mode="json")
    raise HTTPException(status_code=404, detail="Curriculum not found")


@router.post("/{curriculum_id}/items")
async def add_curriculum_item(
    curriculum_id: str,
    request: AddItemRequest,
    store: SessionStore = Depends(get_session_store),
):
    session_data = store.get(request.session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    for c in session_data.curricula:
        if c.id == curriculum_id:
            max_order = max((i.order for i in c.items), default=0)
            item = CurriculumItem(
                objective_id="",
                title=request.title,
                content_outline=request.content_outline,
                order=request.order if request.order is not None else max_order + 1,
            )
            c.items.append(item)
            store.save(request.session_id)
            return item.model_dump(mode="json")
    raise HTTPException(status_code=404, detail="Curriculum not found")


@router.put("/{curriculum_id}/items/{item_id}")
async def update_curriculum_item(
    curriculum_id: str,
    item_id: str,
    update: UpdateItemRequest,
    session_id: str,
    store: SessionStore = Depends(get_session_store),
):
    session_data = store.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    for c in session_data.curricula:
        if c.id == curriculum_id:
            for item in c.items:
                if item.id == item_id:
                    if update.title is not None:
                        item.title = update.title
                    if update.content_outline is not None:
                        item.content_outline = update.content_outline
                    if update.completed is not None:
                        item.completed = update.completed
                    if update.order is not None:
                        item.order = update.order
                    store.save(session_id)
                    return item.model_dump(mode="json")
            raise HTTPException(status_code=404, detail="Item not found")
    raise HTTPException(status_code=404, detail="Curriculum not found")


@router.delete("/{curriculum_id}/items/{item_id}")
async def delete_curriculum_item(
    curriculum_id: str,
    item_id: str,
    session_id: str,
    store: SessionStore = Depends(get_session_store),
):
    session_data = store.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    for c in session_data.curricula:
        if c.id == curriculum_id:
            c.items = [i for i in c.items if i.id != item_id]
            store.save(session_id)
            return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Curriculum not found")
