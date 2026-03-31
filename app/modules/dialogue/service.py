import logging
from collections.abc import AsyncGenerator

from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.user import UserProfile
from app.models.curriculum import Curriculum
from app.services.llm import LLMService
from app.config import DialogueSettings

logger = logging.getLogger("llm_tutor.dialogue")


class DialogueService:
    def __init__(self, llm_service: LLMService, settings: DialogueSettings):
        self.llm = llm_service
        self.settings = settings

    def _build_background_summary(self, profile: UserProfile) -> str:
        return profile.background or "No background provided"

    def _build_system_prompt(
        self,
        profile: UserProfile,
        curriculum: Curriculum | None = None,
        active_item_id: str | None = None,
        rag_context: str | None = None,
    ) -> str:
        background_summary = self._build_background_summary(profile)
        current_topic = ""
        current_section = ""

        if curriculum:
            current_topic = curriculum.goal_topic
            if active_item_id:
                for item in curriculum.items:
                    if item.id == active_item_id:
                        current_section = f"{item.title}: {item.content_outline}"
                        break

        if not current_topic and profile.goals:
            current_topic = profile.goals[0].topic

        if rag_context:
            template = self.llm.get_prompt_template("dialogue", "rag_augmented")
            socratic_prompt = self.llm.get_prompt_template("dialogue", "socratic_system")
            if isinstance(socratic_prompt, str):
                socratic_formatted = socratic_prompt.format(
                    background_summary=background_summary,
                    current_topic=current_topic or "General",
                    current_section=current_section or "Introduction",
                )
            else:
                socratic_formatted = socratic_prompt.system.format(
                    background_summary=background_summary,
                    current_topic=current_topic or "General",
                    current_section=current_section or "Introduction",
                )
            if isinstance(template, str):
                return template.format(
                    socratic_system_prompt=socratic_formatted,
                    rag_context=rag_context,
                )
            return template.system.format(
                socratic_system_prompt=socratic_formatted,
                rag_context=rag_context,
            )
        else:
            template = self.llm.get_prompt_template("dialogue", "socratic_system")
            if isinstance(template, str):
                return template.format(
                    background_summary=background_summary,
                    current_topic=current_topic or "General",
                    current_section=current_section or "Introduction",
                )
            return template.system.format(
                background_summary=background_summary,
                current_topic=current_topic or "General",
                current_section=current_section or "Introduction",
            )

    def _build_chat_messages(
        self,
        system_prompt: str,
        chat_session: ChatSession,
        new_message: str,
    ) -> list[dict]:
        messages = [{"role": "system", "content": system_prompt}]

        history = chat_session.messages[-self.settings.max_history_messages :]
        for msg in history:
            if msg.role != MessageRole.SYSTEM:
                messages.append({"role": msg.role.value, "content": msg.content})

        messages.append({"role": "user", "content": new_message})
        return messages

    async def chat_stream(
        self,
        profile: UserProfile,
        chat_session: ChatSession,
        message: str,
        curriculum: Curriculum | None = None,
        active_item_id: str | None = None,
        rag_context: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a Socratic dialogue response."""
        system_prompt = self._build_system_prompt(
            profile, curriculum, active_item_id, rag_context
        )
        messages = self._build_chat_messages(system_prompt, chat_session, message)

        user_msg = ChatMessage(
            role=MessageRole.USER,
            content=message,
            curriculum_item_id=active_item_id,
        )
        chat_session.messages.append(user_msg)

        full_response = ""
        async for token in self.llm.completion_stream(
            module="dialogue",
            operation="chat",
            messages=messages,
            session_id=profile.id,
        ):
            full_response += token
            yield token

        assistant_msg = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=full_response,
            curriculum_item_id=active_item_id,
        )
        chat_session.messages.append(assistant_msg)
