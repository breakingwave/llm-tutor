from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.account import UserAccount
from app.models.learning_topic import LearningTopicSummary
from app.models.user import UserProfile, LearningGoal
from app.services.session_store import SessionStore
from app.services.user_store import UserStore
from app.dependencies import get_session_store, get_current_user, get_user_store

router = APIRouter(tags=["pages"])


class OnboardingForm(BaseModel):
    background: str = ""
    goal_topic: str = ""
    goal_depth: str = "introductory"


class BackgroundUpdate(BaseModel):
    background: str


class AddGoalForm(BaseModel):
    topic: str
    depth: str = "introductory"


@router.get("/api/sessions/topics")
async def list_learning_topics(
    store: SessionStore = Depends(get_session_store),
    user: UserAccount = Depends(get_current_user),
):
    """Summarize each session as one learning topic (session-per-topic)."""
    summaries: list[LearningTopicSummary] = []
    for sid in user.session_ids:
        session_data = store.get(sid)
        if not session_data:
            continue
        profile = session_data.user_profile
        goals = profile.goals or []
        if goals:
            g0 = goals[0]
            topic = g0.topic or "Untitled"
            depth = g0.depth or "introductory"
            extra = max(0, len(goals) - 1)
        else:
            topic, depth, extra = "Untitled", "introductory", 0
        summaries.append(
            LearningTopicSummary(
                session_id=sid,
                topic=topic,
                depth=depth,
                extra_goals_count=extra,
                created_at=profile.created_at,
            )
        )
    summaries.sort(
        key=lambda s: s.created_at.timestamp() if s.created_at else 0.0,
        reverse=True,
    )
    return {"topics": [t.model_dump(mode="json") for t in summaries]}


@router.post("/api/sessions")
async def create_session(
    form: OnboardingForm,
    store: SessionStore = Depends(get_session_store),
    user: UserAccount = Depends(get_current_user),
    user_store: UserStore = Depends(get_user_store),
):
    background = form.background
    if not background.strip():
        background = user.background or ""
    profile = UserProfile(
        background=background,
        goals=[LearningGoal(topic=form.goal_topic, depth=form.goal_depth)]
        if form.goal_topic
        else [],
    )
    store.create(profile)
    user_store.add_session(user.id, profile.id)
    return {"session_id": profile.id, "redirect": f"/dashboard/{profile.id}"}


@router.get("/api/sessions/{session_id}")
async def get_session(
    session_id: str,
    store: SessionStore = Depends(get_session_store),
    user: UserAccount = Depends(get_current_user),
):
    if session_id not in user.session_ids and user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    session_data = store.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_data.to_dict()


@router.put("/api/sessions/{session_id}/background")
async def update_background(
    session_id: str,
    update: BackgroundUpdate,
    store: SessionStore = Depends(get_session_store),
    user: UserAccount = Depends(get_current_user),
):
    if session_id not in user.session_ids and user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    session_data = store.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    session_data.user_profile.background = update.background
    store.save(session_id)
    return {"status": "updated"}


@router.post("/api/sessions/{session_id}/goals")
async def add_goal(
    session_id: str,
    form: AddGoalForm,
    store: SessionStore = Depends(get_session_store),
    user: UserAccount = Depends(get_current_user),
):
    if session_id not in user.session_ids and user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    session_data = store.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    goal = LearningGoal(topic=form.topic, depth=form.depth)
    session_data.user_profile.goals.append(goal)
    store.save(session_id)
    return {"status": "added", "goals": [g.model_dump() for g in session_data.user_profile.goals]}


@router.delete("/api/sessions/{session_id}/goals/{goal_index}")
async def remove_goal(
    session_id: str,
    goal_index: int,
    store: SessionStore = Depends(get_session_store),
    user: UserAccount = Depends(get_current_user),
):
    if session_id not in user.session_ids and user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    session_data = store.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    goals = session_data.user_profile.goals
    if goal_index < 0 or goal_index >= len(goals):
        raise HTTPException(status_code=404, detail="Goal not found")

    goals.pop(goal_index)
    store.save(session_id)
    return {"status": "removed", "goals": [g.model_dump() for g in goals]}
