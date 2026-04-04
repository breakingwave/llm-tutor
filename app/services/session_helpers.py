from app.models.chat import ChatSession
from app.models.curriculum import Curriculum
from app.models.user import LearningGoal, UserProfile
from app.services.session_store import SessionData


def get_primary_goal(profile: UserProfile) -> LearningGoal | None:
    return profile.goals[0] if profile.goals else None


def get_or_create_chat_session(session_data: SessionData, user_id: str) -> ChatSession:
    if session_data.chat_sessions:
        return session_data.chat_sessions[0]
    chat = ChatSession(user_id=user_id)
    session_data.chat_sessions.append(chat)
    return chat


def pick_curriculum(session_data: SessionData) -> Curriculum | None:
    curricula = session_data.curricula or []
    if not curricula:
        return None

    primary_goal = get_primary_goal(session_data.user_profile)
    if primary_goal:
        for curriculum in curricula:
            if curriculum.goal_topic == primary_goal.topic:
                return curriculum

    return curricula[-1]

