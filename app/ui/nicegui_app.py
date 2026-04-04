from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from nicegui import app as nicegui_app
from nicegui import events, ui

from app.dependencies import (
    get_auth_service,
    get_env_settings,
    get_llm_service,
    get_openstax_service,
    get_openstax_store,
    get_pdf_service,
    get_session_store,
    get_settings,
    get_user_store,
    get_vector_store_service,
)
from app.models.account import UserAccount
from app.models.curriculum import Curriculum, CurriculumItem
from app.models.material import Material, MaterialSource
from app.models.user import LearningGoal, UserProfile
from app.modules.curriculum.service import CurriculumService
from app.modules.dialogue.service import DialogueService
from app.modules.gathering.service import GatheringService
from app.services.openstax_store import OpenStaxStore
from app.services.search import SearchService
from app.services.session_helpers import (
    get_or_create_chat_session,
    get_primary_goal,
    pick_curriculum,
)
from app.services.session_store import SessionData


def safe_notify(message: str, **kwargs) -> None:
    """Show a toast; no-op if the UI client is gone (e.g. user left during long async work)."""
    try:
        ui.notify(message, **kwargs)
    except RuntimeError:
        pass


_NICEGUI_READY = False

BASE_CSS = """
<style>
body {
  background:
    radial-gradient(circle at top left, #eef6ff 0%, #f7f8fb 42%, #f4efe7 100%);
  color: #0f172a;
  font-family: "IBM Plex Sans", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
}
.app-shell {
  max-width: 1600px;
  margin: 0 auto;
  padding: 1.5rem 1rem 2rem;
}
.panel-card {
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 14px 40px rgba(15, 23, 42, 0.07);
}
.panel-card .q-card__section--vert {
  padding: 1.1rem 1.2rem;
}
.hero-kicker {
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 0.74rem;
  color: #0f766e;
  font-weight: 700;
}
.hero-title {
  font-size: clamp(2rem, 2.5vw, 2.8rem);
  line-height: 1.02;
  font-weight: 800;
  margin: 0.2rem 0 0.5rem;
}
.hero-subtitle {
  color: #475569;
  font-size: 1rem;
  line-height: 1.7;
  max-width: 72rem;
}
.section-label {
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #64748b;
}
.muted-copy {
  color: #64748b;
  font-size: 0.92rem;
  line-height: 1.6;
}
.status-strip {
  border-left: 4px solid #2563eb;
  background: rgba(219, 234, 254, 0.72);
  color: #1e3a8a;
  padding: 0.8rem 1rem;
  border-radius: 14px;
  white-space: pre-wrap;
}
.source-pre {
  white-space: pre-wrap;
  font-size: 0.92rem;
  line-height: 1.75;
  color: #334155;
  margin: 0;
}
.chat-scroller {
  height: 680px;
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.82);
}
.viewer-pane {
  min-height: 280px;
  max-height: 420px;
  overflow: auto;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.84);
  padding: 1rem 1.05rem;
}
.table-shell {
  width: 100%;
}
.shell-actions {
  gap: 0.75rem;
}
.hero-row {
  gap: 1.25rem;
  align-items: flex-start;
}
.hero-copy {
  flex: 1 1 760px;
  min-width: 320px;
}
.account-card {
  flex: 0 0 430px;
  min-width: 320px;
}
.account-line {
  gap: 0.9rem;
  align-items: center;
  justify-content: space-between;
}
.account-meta {
  min-width: 0;
}
.account-email {
  font-size: 1.55rem;
  font-weight: 700;
  line-height: 1.2;
  word-break: break-word;
}
.sticky-summary {
  position: sticky;
  top: 1rem;
}
@media (max-width: 900px) {
  .app-shell {
    padding: 1rem 0.75rem 1.5rem;
  }
  .chat-scroller {
    height: 520px;
  }
  .viewer-pane {
    max-height: 320px;
  }
  .account-card {
    flex-basis: 100%;
  }
}
</style>
"""

TABLE_COLUMNS = {
    "materials": [
        {"name": "title", "label": "Title", "field": "title", "align": "left"},
        {"name": "source", "label": "Source", "field": "source", "align": "left"},
        {"name": "score", "label": "Score", "field": "score", "align": "left"},
        {"name": "summary", "label": "Summary", "field": "summary", "align": "left"},
    ],
    "syllabus": [
        {"name": "order", "label": "Order", "field": "order", "align": "left"},
        {"name": "title", "label": "Section", "field": "title", "align": "left"},
        {"name": "completed", "label": "Done", "field": "completed", "align": "left"},
        {"name": "sources", "label": "Sources", "field": "sources", "align": "left"},
    ],
    "openstax": [
        {"name": "title", "label": "Title", "field": "title", "align": "left"},
        {"name": "file_name", "label": "File", "field": "file_name", "align": "left"},
        {"name": "chunk_count", "label": "Chunks", "field": "chunk_count", "align": "left"},
    ],
    "admin": [
        {"name": "email", "label": "Email", "field": "email", "align": "left"},
        {"name": "role", "label": "Role", "field": "role", "align": "left"},
        {"name": "topics", "label": "Topics", "field": "topics", "align": "left"},
        {"name": "storage", "label": "Storage", "field": "storage", "align": "left"},
    ],
}


@dataclass
class WorkspaceState:
    user_id: str | None = None
    selected_session_id: str | None = None
    selected_curriculum_id: str | None = None
    selected_item_id: str | None = None
    selected_material_id: str | None = None
    selected_openstax_file_name: str | None = None
    selected_admin_email: str | None = None
    active_tab: str = "topic_studio"
    active_studio_tab: str = "materials"
    login_status: str = ""
    profile_status: str = ""
    studio_status: str = ""
    chat_status: str = ""
    openstax_status: str = ""
    admin_status: str = ""
    material_search_query: str = ""
    material_search_results: str = ""


@dataclass
class WorkspaceSnapshot:
    user: UserAccount | None
    session_data: SessionData | None
    curriculum: Curriculum | None
    item: CurriculumItem | None
    item_materials: list[Material]
    material: Material | None
    viewer_info: str
    viewer_text: str
    chat_history: list[dict[str, str]]


def init_nicegui(fastapi_app: FastAPI) -> None:
    global _NICEGUI_READY
    if _NICEGUI_READY:
        return
    _NICEGUI_READY = True

    settings = get_settings()
    env_settings = get_env_settings()
    auth_service = get_auth_service()
    user_store = get_user_store()
    session_store = get_session_store()
    pdf_service = get_pdf_service()
    vector_store = get_vector_store_service()
    openstax_store = get_openstax_store()
    openstax_service = get_openstax_service()

    def truncate_text(text: str, limit: int = 12000) -> str:
        cleaned = text.strip()
        if len(cleaned) <= limit:
            return cleaned
        return f"{cleaned[:limit].rstrip()}\n\n[Excerpt truncated for responsiveness.]"

    def get_user_or_none(state: WorkspaceState) -> UserAccount | None:
        if not state.user_id:
            return None
        return user_store.get_by_id(state.user_id)

    def require_user(state: WorkspaceState) -> UserAccount:
        user = get_user_or_none(state)
        if not user:
            raise ValueError("Sign in to continue.")
        return user

    def ensure_session_access(user: UserAccount, session_id: str | None) -> SessionData | None:
        if not session_id:
            return None
        if session_id not in user.session_ids and user.role != "admin":
            raise ValueError("You do not have access to that topic.")
        session_data = session_store.get(session_id)
        if not session_data:
            raise ValueError("Topic session not found.")
        return session_data

    def build_gathering_service() -> GatheringService:
        search_service = SearchService(
            env_settings.tavily_api_key,
            settings.gathering,
            get_llm_service().api_logger,
        )
        return GatheringService(
            get_llm_service(),
            search_service,
            settings.gathering,
            vector_store=vector_store,
            openstax_collection_name=settings.openstax.collection_name,
        )

    def build_curriculum_service() -> CurriculumService:
        return CurriculumService(get_llm_service(), settings.curriculum)

    def build_dialogue_service() -> DialogueService:
        return DialogueService(
            get_llm_service(),
            settings.dialogue,
        ).configure_retrieval(
            vector_store=vector_store,
            openstax_collection_name=settings.openstax.collection_name,
        )

    def topic_label(session_id: str) -> str:
        session_data = session_store.get(session_id)
        if not session_data:
            return session_id
        goal = get_primary_goal(session_data.user_profile)
        if not goal:
            return f"Untitled topic [{session_id[:8]}]"
        return f"{goal.topic} · {goal.depth}"

    def topic_options(user: UserAccount) -> dict[str, str]:
        return {session_id: topic_label(session_id) for session_id in user.session_ids}

    def curriculum_options(session_data: SessionData | None) -> dict[str, str]:
        if not session_data:
            return {}
        return {
            curriculum.id: f"{curriculum.goal_topic} · {len(curriculum.items)} sections"
            for curriculum in session_data.curricula
        }

    def item_options(curriculum: Curriculum | None) -> dict[str, str]:
        if not curriculum:
            return {}
        ordered_items = sorted(curriculum.items, key=lambda item: item.order)
        return {item.id: f"{item.order}. {item.title}" for item in ordered_items}

    def material_options(materials: list[Material]) -> dict[str, str]:
        return {
            material.id: f"{material.title} · {material.source.value}"
            for material in materials
        }

    def serialize_chat(messages) -> list[dict[str, str]]:
        return [
            {"role": message.role.value, "content": message.content}
            for message in messages
            if message.role.value in ("user", "assistant")
        ]

    def build_material_rows(materials: list[Material]) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for index, material in enumerate(materials, start=1):
            rows.append(
                {
                    "id": str(index),
                    "title": material.title,
                    "source": material.source.value,
                    "score": str(material.relevance_score or ""),
                    "summary": (material.summary or material.content[:240]).replace("\n", " "),
                }
            )
        return rows

    def build_syllabus_rows(curriculum: Curriculum | None) -> list[dict[str, str]]:
        if not curriculum:
            return []
        return [
            {
                "id": item.id,
                "order": str(item.order),
                "title": item.title,
                "completed": "Yes" if item.completed else "No",
                "sources": ", ".join(material_id[:8] for material_id in item.material_ids) or "Auto",
            }
            for item in sorted(curriculum.items, key=lambda item: item.order)
        ]

    def build_openstax_rows() -> list[dict[str, str]]:
        return [
            {
                "id": book.id,
                "title": book.title,
                "file_name": book.file_name,
                "chunk_count": str(book.chunk_count),
            }
            for book in openstax_service.list_books()
        ]

    def build_admin_rows() -> list[dict[str, str]]:
        return [
            {
                "id": entry.id,
                "email": entry.email,
                "role": entry.role,
                "topics": str(len(entry.session_ids)),
                "storage": f"{entry.total_upload_bytes / (1024 ** 2):.1f} MB",
            }
            for entry in user_store.list_users()
        ]

    def format_curriculum_analysis(curriculum: Curriculum | None) -> str:
        if not curriculum:
            return "No curriculum yet. Gather materials first, then generate a study plan."

        def flatten(text: str) -> str:
            return " ".join((text or "").split())

        concept_lines: list[str] = []
        for concept in curriculum.concepts:
            concept_lines.append(f"- **{concept.name}**")
            concept_lines.append(f"    - Description: {flatten(concept.description)}")
            if concept.prerequisites:
                concept_lines.append("    - Prerequisites:")
                concept_lines.extend(f"        - {flatten(prerequisite)}" for prerequisite in concept.prerequisites)
            concept_lines.append("")
        concepts = "\n".join(concept_lines).strip() or "- No concepts extracted yet."

        objective_lines: list[str] = []
        objective_lookup = {
            concept.id: concept.name
            for concept in curriculum.concepts
        }
        for objective in curriculum.objectives[:10]:
            objective_lines.append(f"- **{objective_lookup.get(objective.concept_id, 'General')}**")
            objective_lines.append(f"    - Bloom level: `{objective.bloom_level}`")
            objective_lines.append(f"    - Outcome: {flatten(objective.description)}")
            objective_lines.append("")
        objectives = "\n".join(objective_lines).strip() or "- No objectives extracted yet."

        item_lines: list[str] = []
        for item in sorted(curriculum.items, key=lambda entry: entry.order)[:10]:
            item_lines.append(f"- **{item.order}. {item.title}**")
            if item.content_outline:
                item_lines.append(f"    - Focus: {flatten(item.content_outline)}")
            if item.material_ids:
                item_lines.append("    - Source links:")
                item_lines.extend(f"        - `{material_id[:8]}`" for material_id in item.material_ids)
            item_lines.append("")
        items = "\n".join(item_lines).strip() or "- No sections generated yet."

        return (
            f"### Curriculum Analysis\n"
            f"- **Goal**\n"
            f"    - {flatten(curriculum.goal_topic)}\n\n"
            f"- **Concepts**\n"
            f"{concepts}\n\n"
            f"- **Objectives**\n"
            f"{objectives}\n\n"
            f"- **Study Path**\n"
            f"{items}"
        )

    def format_topic_summary(
        user: UserAccount,
        session_data: SessionData | None,
        curriculum: Curriculum | None,
    ) -> str:
        if not session_data:
            return "Create a topic to begin."
        goals = session_data.user_profile.goals or []
        primary_goal = goals[0] if goals else LearningGoal(topic="Untitled", depth="introductory")
        return (
            f"### Topic Summary\n"
            f"**Learner:** {user.email}\n\n"
            f"**Topic:** {primary_goal.topic}\n\n"
            f"**Depth:** {primary_goal.depth}\n\n"
            f"**Materials:** {len(session_data.materials)}\n\n"
            f"**Curricula:** {len(session_data.curricula)}\n\n"
            f"**Chat Messages:** {sum(len(chat.messages) for chat in session_data.chat_sessions)}\n\n"
            f"**Current Curriculum Sections:** {len(curriculum.items) if curriculum else 0}"
        )

    def resolve_curriculum(session_data: SessionData | None, state: WorkspaceState) -> Curriculum | None:
        if not session_data or not session_data.curricula:
            state.selected_curriculum_id = None
            return None

        selected_id = state.selected_curriculum_id
        curriculum = next((entry for entry in session_data.curricula if entry.id == selected_id), None)
        if curriculum is None:
            curriculum = pick_curriculum(session_data)
            state.selected_curriculum_id = curriculum.id if curriculum else None
        return curriculum

    def resolve_item(curriculum: Curriculum | None, state: WorkspaceState) -> CurriculumItem | None:
        if not curriculum or not curriculum.items:
            state.selected_item_id = None
            return None

        selected_id = state.selected_item_id
        ordered_items = sorted(curriculum.items, key=lambda item: item.order)
        item = next((entry for entry in ordered_items if entry.id == selected_id), None)
        if item is None:
            item = ordered_items[0]
            state.selected_item_id = item.id
        return item

    def resolve_item_materials(session_data: SessionData | None, item: CurriculumItem | None) -> list[Material]:
        if not session_data or not session_data.materials:
            return []
        if not item or not item.material_ids:
            return session_data.materials[:5]
        material_lookup = {material.id: material for material in session_data.materials}
        materials = [
            material_lookup[material_id]
            for material_id in item.material_ids
            if material_id in material_lookup
        ]
        return materials or session_data.materials[:5]

    def resolve_material(
        session_data: SessionData | None,
        materials: list[Material],
        state: WorkspaceState,
    ) -> Material | None:
        if not session_data or not materials:
            state.selected_material_id = None
            return None

        selected_id = state.selected_material_id
        material = next((entry for entry in materials if entry.id == selected_id), None)
        if material is None:
            material = materials[0]
            state.selected_material_id = material.id
        return material

    def viewer_payload(
        material: Material | None,
        session_data: SessionData | None,
        openstax_index: OpenStaxStore,
    ) -> tuple[str, str]:
        if not material:
            return "Select a curriculum section to inspect its source materials.", ""

        lines = [
            f"### {material.title}",
            f"**Source:** {material.source.value}",
        ]

        if material.source == MaterialSource.PDF_UPLOAD:
            raw_path = material.metadata.get("file_path")
            if not raw_path and session_data:
                source_material_id = material.metadata.get("material_id")
                source_material = next(
                    (entry for entry in session_data.materials if entry.id == source_material_id),
                    None,
                )
                if source_material:
                    raw_path = source_material.metadata.get("file_path")
            if isinstance(raw_path, str) and Path(raw_path).exists():
                lines.append(f"**File:** {Path(raw_path).name}")
            lines.append("Showing the currently selected chunk only.")
        elif material.source == MaterialSource.OPENSTAX:
            source_book_id = material.metadata.get("material_id")
            if isinstance(source_book_id, str):
                book = openstax_index.get_book(source_book_id)
                if book:
                    lines.append(f"**Book:** {book.title}")
            chapter = material.metadata.get("chapter")
            section = material.metadata.get("section")
            if chapter:
                lines.append(f"**Chapter:** {chapter}")
            if section:
                lines.append(f"**Section:** {section}")
            lines.append("Showing the retrieved OpenStax chunk instead of rendering the full textbook.")

        if material.url:
            lines.append(f"[Open source link]({material.url})")

        return "\n\n".join(lines), truncate_text(material.content or material.summary)

    def build_snapshot(state: WorkspaceState) -> WorkspaceSnapshot:
        user = get_user_or_none(state)
        if not user:
            return WorkspaceSnapshot(None, None, None, None, [], None, "", "", [])

        if user.session_ids:
            if state.selected_session_id not in user.session_ids:
                state.selected_session_id = user.session_ids[0]
        else:
            state.selected_session_id = None

        session_data = ensure_session_access(user, state.selected_session_id) if state.selected_session_id else None
        curriculum = resolve_curriculum(session_data, state)
        item = resolve_item(curriculum, state)
        item_materials = resolve_item_materials(session_data, item)
        material = resolve_material(session_data, item_materials, state)
        viewer_info, viewer_text = viewer_payload(material, session_data, openstax_store)

        chat_history: list[dict[str, str]] = []
        if session_data and session_data.chat_sessions:
            chat_history = serialize_chat(session_data.chat_sessions[0].messages)

        books = openstax_service.list_books()
        available_openstax = {book.file_name for book in books}
        if state.selected_openstax_file_name not in available_openstax:
            state.selected_openstax_file_name = books[0].file_name if books else None

        delete_choices = {
            entry.email
            for entry in user_store.list_users()
            if not user or entry.id != user.id
        }
        if state.selected_admin_email not in delete_choices:
            state.selected_admin_email = None

        return WorkspaceSnapshot(
            user=user,
            session_data=session_data,
            curriculum=curriculum,
            item=item,
            item_materials=item_materials,
            material=material,
            viewer_info=viewer_info,
            viewer_text=viewer_text,
            chat_history=chat_history,
        )

    @ui.page("/")
    async def workspace_page() -> None:
        ui.colors(
            primary="#2563eb",
            secondary="#475569",
            accent="#0f766e",
            positive="#15803d",
            negative="#b91c1c",
            warning="#b45309",
        )
        ui.add_head_html(BASE_CSS)
        state = WorkspaceState()

        def set_status(field: str, message: str) -> None:
            setattr(state, field, message)

        def clear_status(*fields: str) -> None:
            for field in fields:
                setattr(state, field, "")

        def remember_login(email: str, password: str) -> None:
            nicegui_app.storage.user["login_cache"] = {
                "email": email.strip().lower(),
                "password": password,
            }

        def clear_login_cache() -> None:
            nicegui_app.storage.user.pop("login_cache", None)

        def handle_error(field: str, exc: Exception) -> None:
            message = str(exc) or "The request failed."
            set_status(field, message)
            safe_notify(message, type="negative", multi_line=True, close_button=True)

        def authenticate(
            email: str,
            password: str,
            *,
            remember: bool = True,
            notify: bool = True,
        ) -> None:
            normalized_email = email.strip().lower()
            user = user_store.get_by_email(normalized_email)
            if not user or not auth_service.check_password(password, user.password_hash):
                raise ValueError("Invalid email or password.")

            state.user_id = user.id
            state.selected_session_id = None
            state.selected_curriculum_id = None
            state.selected_item_id = None
            state.selected_material_id = None
            state.selected_admin_email = None
            state.selected_openstax_file_name = None
            clear_status(
                "login_status",
                "profile_status",
                "studio_status",
                "chat_status",
                "openstax_status",
                "admin_status",
            )
            if remember:
                remember_login(normalized_email, password)
            if notify:
                safe_notify(f"Signed in as {user.email}.", type="positive")

        def restore_cached_login() -> None:
            cached = nicegui_app.storage.user.get("login_cache") or {}
            email = cached.get("email", "").strip().lower()
            password = cached.get("password", "")
            if not email or not password:
                return
            try:
                authenticate(email, password, remember=False, notify=False)
            except Exception:
                clear_login_cache()

        def render_status(message: str) -> None:
            if message:
                ui.html(f'<div class="status-strip">{html.escape(message)}</div>')

        def render_chat_messages(container, history: list[dict[str, str]]) -> None:
            container.clear()
            with container:
                if not history:
                    with ui.element("div").classes("muted-copy"):
                        ui.label("The tutoring chat will appear here once you start asking questions.")
                    return

                for message in history:
                    sender = message["role"]
                    with ui.chat_message(
                        name="You" if sender == "user" else "Tutor",
                        sent=sender == "user",
                    ).classes("w-full"):
                        ui.markdown(message["content"] or "").classes("w-full")

        restore_cached_login()

        @ui.refreshable
        def render_shell() -> None:
            with ui.column().classes("app-shell w-full gap-5"):
                user = get_user_or_none(state)
                if not user:
                    ui.html('<div class="hero-kicker">Learner-Aware Study Workspace</div>')
                    ui.html('<div class="hero-title">LLM Tutor</div>')
                    ui.html(
                        '<div class="hero-subtitle">'
                        'A learner-aware workspace for topic setup, research, curriculum design, and long-form tutoring.'
                        '</div>'
                    )
                    with ui.row(wrap=True).classes("w-full items-stretch gap-6"):
                        with ui.card().classes("panel-card").style("flex: 1 1 380px; min-width: 320px;"):
                            ui.label("Sign In").classes("text-2xl font-bold")
                            ui.label("Cached sign-in is enabled so long study sessions reopen cleanly.").classes("muted-copy")
                            login_cache = nicegui_app.storage.user.get("login_cache") or {}
                            email_input = ui.input(
                                "Email",
                                value=login_cache.get("email", ""),
                                placeholder="admin@example.com",
                            ).props("outlined").classes("w-full")
                            password_input = ui.input(
                                "Password",
                                value=login_cache.get("password", ""),
                                password=True,
                                password_toggle_button=True,
                            ).props("outlined").classes("w-full")
                            render_status(state.login_status)

                            async def handle_login() -> None:
                                try:
                                    authenticate(email_input.value or "", password_input.value or "")
                                    clear_status("login_status")
                                    render_shell.refresh()
                                except Exception as exc:
                                    handle_error("login_status", exc)
                                    render_shell.refresh()

                            ui.button("Sign In", on_click=handle_login, color="primary").props("unelevated").classes("w-full")

                        with ui.card().classes("panel-card").style("flex: 2 1 560px; min-width: 320px;"):
                            ui.label("Workspace Design").classes("text-2xl font-bold")
                            ui.markdown(
                                """
`Topic Studio` keeps topic creation, material intake, search, and curriculum analysis separate from `Learning Session`.

`Learning Session` focuses on syllabus navigation, source inspection, and a chat layout that remains usable over long study blocks.

`OpenStax Library` is isolated from study flow so indexing and reindexing do not block active tutoring work.
                                """
                            ).classes("w-full")
                    return

                snapshot = build_snapshot(state)
                user = snapshot.user
                assert user is not None

                with ui.row(wrap=True).classes("w-full hero-row"):
                    with ui.column().classes("hero-copy gap-1"):
                        ui.html('<div class="hero-kicker">Learner-Aware Study Workspace</div>')
                        ui.html('<div class="hero-title">LLM Tutor</div>')
                        ui.html(
                            '<div class="hero-subtitle">'
                            'A learner-aware workspace for topic setup, research, curriculum design, and long-form tutoring.'
                            '</div>'
                        )

                    with ui.card().classes("panel-card account-card"):
                        with ui.row(wrap=True).classes("w-full account-line"):
                            with ui.column().classes("account-meta gap-1"):
                                ui.label("Signed in").classes("section-label")
                                ui.html(f'<div class="account-email">{html.escape(user.email)} ({html.escape(user.role)})</div>')
                            with ui.row().classes("items-center gap-3"):
                                ui.button(
                                    "Refresh",
                                    on_click=lambda: (
                                        topic_panel.refresh(),
                                        learning_panel.refresh(),
                                        openstax_panel.refresh(),
                                        admin_panel.refresh(),
                                        profile_panel.refresh(),
                                    ),
                                ).props("outline")

                                def handle_logout() -> None:
                                    clear_login_cache()
                                    state.user_id = None
                                    state.selected_session_id = None
                                    state.selected_curriculum_id = None
                                    state.selected_item_id = None
                                    state.selected_material_id = None
                                    state.selected_openstax_file_name = None
                                    state.selected_admin_email = None
                                    clear_status(
                                        "login_status",
                                        "profile_status",
                                        "studio_status",
                                        "chat_status",
                                        "openstax_status",
                                        "admin_status",
                                    )
                                    render_shell.refresh()

                                ui.button("Sign Out", on_click=handle_logout).props("outline")

                with ui.tabs(
                    value=state.active_tab,
                    on_change=lambda e: setattr(state, "active_tab", e.value),
                ).classes("w-full") as tabs:
                    ui.tab("profile", "Profile")
                    ui.tab("topic_studio", "Topic Studio")
                    ui.tab("learning_session", "Learning Session")
                    ui.tab("openstax_library", "OpenStax Library")
                    ui.tab("admin", "Admin")

                with ui.tab_panels(tabs, value=state.active_tab, keep_alive=True).classes("w-full"):
                    with ui.tab_panel("profile"):
                        profile_panel()
                    with ui.tab_panel("topic_studio"):
                        topic_panel()
                    with ui.tab_panel("learning_session"):
                        learning_panel()
                    with ui.tab_panel("openstax_library"):
                        openstax_panel()
                    with ui.tab_panel("admin"):
                        admin_panel()

        @ui.refreshable
        def profile_panel() -> None:
            user = require_user(state)
            with ui.column().classes("w-full gap-4"):
                render_status(state.profile_status)
                with ui.card().classes("panel-card w-full"):
                    ui.label("Account Background").classes("text-xl font-semibold")
                    ui.label("This background seeds all new topics unless the topic-specific context overrides it.").classes("muted-copy")
                    background = ui.textarea(
                        "Account Background",
                        value=user.background,
                        placeholder="Background that should seed all new topics...",
                    ).props("outlined autogrow").classes("w-full")

                    def save_background() -> None:
                        try:
                            user_store.update_background(user.id, background.value or "")
                            set_status("profile_status", "Saved account background.")
                            safe_notify("Account background saved.", type="positive")
                            profile_panel.refresh()
                        except Exception as exc:
                            handle_error("profile_status", exc)
                            profile_panel.refresh()

                    ui.button("Save Account Background", on_click=save_background, color="primary").props("unelevated")

        @ui.refreshable
        def topic_panel() -> None:
            snapshot = build_snapshot(state)
            user = require_user(state)
            with ui.column().classes("w-full gap-4"):
                render_status(state.studio_status)
                with ui.row(wrap=True).classes("w-full gap-6 items-start"):
                    with ui.card().classes("panel-card sticky-summary").style("flex: 1 1 320px; min-width: 300px;"):
                        ui.label("Topic Studio").classes("text-xl font-semibold")
                        topic_select = ui.select(
                            topic_options(user),
                            value=state.selected_session_id,
                            label="Active Topic",
                            on_change=lambda e: (
                                setattr(state, "selected_session_id", e.value),
                                setattr(state, "selected_curriculum_id", None),
                                setattr(state, "selected_item_id", None),
                                setattr(state, "selected_material_id", None),
                                clear_status("studio_status", "chat_status"),
                                topic_panel.refresh(),
                                learning_panel.refresh(),
                            ),
                        ).props("outlined").classes("w-full")
                        topic_select.update()
                        ui.markdown(format_topic_summary(user, snapshot.session_data, snapshot.curriculum)).classes("w-full")

                        topic_background = ui.textarea(
                            "Topic-Specific Background",
                            value=snapshot.session_data.user_profile.background if snapshot.session_data else "",
                            placeholder="Add context specific to this topic...",
                        ).props("outlined autogrow").classes("w-full")

                        def save_topic_background() -> None:
                            try:
                                session_data = ensure_session_access(user, state.selected_session_id)
                                if not session_data:
                                    raise ValueError("Select a topic first.")
                                session_data.user_profile.background = topic_background.value or ""
                                session_store.save(session_data.session_id)
                                set_status("studio_status", "Saved topic-specific background.")
                                safe_notify("Topic background saved.", type="positive")
                                topic_panel.refresh()
                            except Exception as exc:
                                handle_error("studio_status", exc)
                                topic_panel.refresh()

                        ui.button("Save Topic Background", on_click=save_topic_background).props("outline")

                        ui.separator()
                        new_topic = ui.input("New Topic", placeholder="Molecular biology foundations").props("outlined").classes("w-full")
                        new_depth = ui.radio(
                            {
                                "introductory": "Introductory",
                                "comprehensive": "Comprehensive",
                                "expert": "Expert",
                            },
                            value="introductory",
                        ).props("inline")

                        def create_topic() -> None:
                            try:
                                if not (new_topic.value or "").strip():
                                    raise ValueError("Enter a topic name.")
                                profile = UserProfile(
                                    background=(topic_background.value or "").strip() or user.background or "",
                                    goals=[LearningGoal(topic=(new_topic.value or "").strip(), depth=new_depth.value)],
                                )
                                session_store.create(profile)
                                user_store.add_session(user.id, profile.id)
                                state.selected_session_id = profile.id
                                state.selected_curriculum_id = None
                                state.selected_item_id = None
                                state.selected_material_id = None
                                set_status("studio_status", f"Created topic `{(new_topic.value or '').strip()}`.")
                                safe_notify("Topic created.", type="positive")
                                topic_panel.refresh()
                                learning_panel.refresh()
                            except Exception as exc:
                                handle_error("studio_status", exc)
                                topic_panel.refresh()

                        ui.button("Create Topic", on_click=create_topic, color="primary").props("unelevated")

                    with ui.column().classes("gap-6").style("flex: 2 1 760px; min-width: 320px;"):
                        with ui.tabs(
                            value=state.active_studio_tab,
                            on_change=lambda e: setattr(state, "active_studio_tab", e.value),
                        ).classes("w-full") as studio_tabs:
                            ui.tab("materials", "Materials")
                            ui.tab("curriculum", "Curriculum Analysis")

                        with ui.tab_panels(studio_tabs, value=state.active_studio_tab, keep_alive=True).classes("w-full"):
                            with ui.tab_panel("materials"):
                                async def run_gathering() -> None:
                                    try:
                                        session_data = ensure_session_access(user, state.selected_session_id)
                                        if not session_data:
                                            raise ValueError("Select a topic first.")
                                        goal = get_primary_goal(session_data.user_profile)
                                        if not goal:
                                            raise ValueError("Add a learning goal before gathering materials.")
                                        set_status("studio_status", "Gathering materials...")
                                        topic_panel.refresh()
                                        service = build_gathering_service()
                                        materials = await service.run_gathering(
                                            profile=session_data.user_profile,
                                            goal_topic=goal.topic,
                                            depth=goal.depth,
                                        )
                                        session_data.materials.extend(materials)
                                        await service.index_materials(materials, session_id=session_data.session_id)
                                        session_store.save(session_data.session_id)
                                        set_status("studio_status", f"Gathering complete. Added {len(materials)} materials.")
                                        safe_notify("Material gathering complete.", type="positive")
                                        topic_panel.refresh()
                                        learning_panel.refresh()
                                    except Exception as exc:
                                        handle_error("studio_status", exc)
                                        topic_panel.refresh()

                                with ui.card().classes("panel-card w-full"):
                                    with ui.row(wrap=True).classes("w-full items-center justify-between gap-4"):
                                        with ui.column().classes("gap-1"):
                                            ui.label("Primary Action").classes("section-label")
                                            ui.label("Run material gathering before hand-curating sources when you want the system to build the evidence base for the topic.").classes("muted-copy")
                                        ui.button("Run Material Gathering", on_click=run_gathering, color="primary").props("unelevated")

                                with ui.row(wrap=True).classes("w-full gap-6 items-start"):
                                    with ui.card().classes("panel-card").style("flex: 1 1 420px; min-width: 320px;"):
                                        ui.label("Material Intake").classes("text-xl font-semibold")
                                        ui.label("Add a focused PDF, manual note, or let the gathering pipeline pull supporting material.").classes("muted-copy")
                                        if snapshot.session_data:
                                            pdf_upload = ui.upload(
                                                label="Upload PDF",
                                                auto_upload=True,
                                                max_file_size=settings.pdf.max_file_size_mb * 1024 * 1024,
                                            ).props("accept=.pdf").classes("w-full")

                                            async def handle_pdf_upload(event: events.UploadEventArguments) -> None:
                                                try:
                                                    session_data = ensure_session_access(user, state.selected_session_id)
                                                    if not session_data:
                                                        raise ValueError("Choose a topic before uploading a PDF.")
                                                    content = await event.file.read()
                                                    if user.total_upload_bytes + len(content) > settings.auth.max_upload_bytes_per_user:
                                                        raise ValueError("Upload would exceed the per-user storage limit.")

                                                    safe_name = Path(event.file.name).name
                                                    saved_path = pdf_service.save_bytes(safe_name, content, session_data.session_id)
                                                    parsed = pdf_service.parse_pdf_document(saved_path)
                                                    if not parsed.text.strip():
                                                        saved_path.unlink(missing_ok=True)
                                                        raise ValueError("PDF contains no extractable text.")

                                                    material = Material(
                                                        source=MaterialSource.PDF_UPLOAD,
                                                        title=Path(safe_name).stem.replace("_", " ").replace("-", " ").title(),
                                                        file_name=safe_name,
                                                        content=parsed.text[:5000],
                                                        metadata={
                                                            "file_path": str(saved_path),
                                                            "total_length": len(parsed.text),
                                                            "toc_entries": len(parsed.toc_entries),
                                                        },
                                                    )
                                                    chunks = pdf_service.chunk_pdf(
                                                        parsed.text,
                                                        parsed.toc_entries,
                                                        safe_name,
                                                        material.id,
                                                        page_texts=parsed.page_texts,
                                                    )
                                                    await vector_store.index_chunks(chunks, session_id=session_data.session_id)
                                                    session_data.materials.append(material)
                                                    session_store.save(session_data.session_id)
                                                    user_store.update_upload_bytes(user.id, len(content))
                                                    set_status("studio_status", f"Uploaded `{safe_name}` and indexed {len(chunks)} chunks.")
                                                    safe_notify("PDF uploaded and indexed.", type="positive")
                                                    pdf_upload.reset()
                                                    topic_panel.refresh()
                                                    learning_panel.refresh()
                                                except Exception as exc:
                                                    handle_error("studio_status", exc)
                                                    topic_panel.refresh()

                                            pdf_upload.on_upload(handle_pdf_upload)
                                        else:
                                            ui.label("Create a topic before uploading PDF material.").classes("muted-copy")

                                        manual_title = ui.input("Manual Material Title").props("outlined").classes("w-full")
                                        manual_content = ui.textarea(
                                            "Manual Material Content",
                                            placeholder="Paste source notes, copied extracts, or a distilled explanation here.",
                                        ).props("outlined autogrow").classes("w-full")
                                        manual_url = ui.input(
                                            "Reference URL",
                                            placeholder="https://...",
                                        ).props("outlined").classes("w-full")

                                        def add_manual_material() -> None:
                                            try:
                                                session_data = ensure_session_access(user, state.selected_session_id)
                                                if not session_data:
                                                    raise ValueError("Select a topic first.")
                                                if not (manual_title.value or "").strip() or not (manual_content.value or "").strip():
                                                    raise ValueError("Manual materials need both a title and content.")
                                                session_data.materials.append(
                                                    Material(
                                                        source=MaterialSource.USER_UPLOAD,
                                                        title=(manual_title.value or "").strip(),
                                                        content=(manual_content.value or "").strip(),
                                                        url=(manual_url.value or "").strip() or None,
                                                    )
                                                )
                                                session_store.save(session_data.session_id)
                                                set_status("studio_status", "Added manual material.")
                                                safe_notify("Manual material added.", type="positive")
                                                topic_panel.refresh()
                                                learning_panel.refresh()
                                            except Exception as exc:
                                                handle_error("studio_status", exc)
                                                topic_panel.refresh()

                                        with ui.row().classes("w-full gap-3"):
                                            ui.button("Add Manual Material", on_click=add_manual_material).props("outline")

                                    with ui.card().classes("panel-card").style("flex: 1 1 360px; min-width: 320px;"):
                                        ui.label("Material Search").classes("text-xl font-semibold")
                                        ui.label("Search across indexed uploads, gathered materials, and the shared OpenStax library.").classes("muted-copy")
                                        query_input = ui.input(
                                            "Search Indexed Materials",
                                            value=state.material_search_query,
                                            placeholder="photosynthesis light reactions",
                                        ).props("outlined").classes("w-full")

                                        async def search_materials() -> None:
                                            try:
                                                state.material_search_query = query_input.value or ""
                                                if not state.material_search_query.strip():
                                                    state.material_search_results = "Enter a query to search indexed materials."
                                                    topic_panel.refresh()
                                                    return
                                                session_data = ensure_session_access(user, state.selected_session_id)
                                                if not session_data:
                                                    raise ValueError("Select a topic first.")
                                                results = await vector_store.query_hybrid(
                                                    state.material_search_query.strip(),
                                                    top_k=5,
                                                    session_id=session_data.session_id,
                                                )
                                                shared_results = await vector_store.query_hybrid(
                                                    state.material_search_query.strip(),
                                                    top_k=3,
                                                    session_id=session_data.session_id,
                                                    collection_name=settings.openstax.collection_name,
                                                )
                                                combined = results + shared_results
                                                if not combined:
                                                    state.material_search_results = "No indexed material matched that query."
                                                else:
                                                    lines = ["### Search Results"]
                                                    for index, result in enumerate(combined, start=1):
                                                        chapter = result["metadata"].get("chapter") or ""
                                                        section = result["metadata"].get("section") or ""
                                                        label = " / ".join(part for part in [chapter, section] if part) or "Excerpt"
                                                        lines.append(
                                                            f"{index}. **{label}**\n\n"
                                                            f"{result['content'][:380].replace(chr(10), ' ')}"
                                                        )
                                                    state.material_search_results = "\n\n".join(lines)
                                                topic_panel.refresh()
                                            except Exception as exc:
                                                handle_error("studio_status", exc)
                                                topic_panel.refresh()

                                        ui.button("Search", on_click=search_materials).props("outline")
                                        ui.markdown(
                                            state.material_search_results or "Search results will appear here."
                                        ).classes("w-full")

                                with ui.card().classes("panel-card table-shell"):
                                    ui.label("Current Materials").classes("text-xl font-semibold")
                                    ui.table(
                                        rows=build_material_rows(snapshot.session_data.materials if snapshot.session_data else []),
                                        columns=TABLE_COLUMNS["materials"],
                                        row_key="id",
                                        pagination=8,
                                    ).props("flat bordered wrap-cells").classes("w-full")

                            with ui.tab_panel("curriculum"):
                                with ui.card().classes("panel-card w-full"):
                                    ui.label("Curriculum Analysis").classes("text-xl font-semibold")
                                    ui.label("Generate a structured learning path once the topic has enough source material.").classes("muted-copy")
                                    curriculum_select = ui.select(
                                        curriculum_options(snapshot.session_data),
                                        value=state.selected_curriculum_id,
                                        label="Curriculum",
                                        on_change=lambda e: (
                                            setattr(state, "selected_curriculum_id", e.value),
                                            setattr(state, "selected_item_id", None),
                                            setattr(state, "selected_material_id", None),
                                            topic_panel.refresh(),
                                            learning_panel.refresh(),
                                        ),
                                    ).props("outlined").classes("w-full")
                                    curriculum_select.update()

                                    async def generate_curriculum() -> None:
                                        try:
                                            session_data = ensure_session_access(user, state.selected_session_id)
                                            if not session_data:
                                                raise ValueError("Select a topic first.")
                                            goal = get_primary_goal(session_data.user_profile)
                                            if not goal:
                                                raise ValueError("Add a learning goal before generating curriculum.")
                                            if not session_data.materials:
                                                raise ValueError("Gather or add materials before generating curriculum.")
                                            set_status("studio_status", "Generating curriculum...")
                                            topic_panel.refresh()
                                            curriculum = await build_curriculum_service().generate_curriculum(
                                                profile=session_data.user_profile,
                                                materials=session_data.materials,
                                                goal_topic=goal.topic,
                                                depth=goal.depth,
                                            )
                                            session_data.curricula.append(curriculum)
                                            session_store.save(session_data.session_id)
                                            state.selected_curriculum_id = curriculum.id
                                            state.selected_item_id = None
                                            state.selected_material_id = None
                                            set_status("studio_status", f"Generated curriculum with {len(curriculum.items)} sections.")
                                            safe_notify("Curriculum generated.", type="positive")
                                            topic_panel.refresh()
                                            learning_panel.refresh()
                                        except Exception as exc:
                                            handle_error("studio_status", exc)
                                            topic_panel.refresh()

                                    ui.button("Generate Curriculum", on_click=generate_curriculum, color="primary").props("unelevated")
                                    ui.markdown(format_curriculum_analysis(snapshot.curriculum)).classes("w-full")
                                    ui.table(
                                        rows=build_syllabus_rows(snapshot.curriculum),
                                        columns=TABLE_COLUMNS["syllabus"],
                                        row_key="id",
                                        pagination=8,
                                    ).props("flat bordered wrap-cells").classes("w-full")

        @ui.refreshable
        def learning_panel() -> None:
            snapshot = build_snapshot(state)
            user = require_user(state)
            with ui.column().classes("w-full gap-4"):
                render_status(state.chat_status)
                with ui.row(wrap=True).classes("w-full gap-6 items-start"):
                    with ui.card().classes("panel-card").style("flex: 1 1 440px; min-width: 320px;"):
                        ui.label("Learning Session").classes("text-xl font-semibold")
                        ui.label("Keep the source excerpt visible while you work through the active section.").classes("muted-copy")

                        item_select = ui.select(
                            item_options(snapshot.curriculum),
                            value=state.selected_item_id,
                            label="Study Section",
                            on_change=lambda e: (
                                setattr(state, "selected_item_id", e.value),
                                setattr(state, "selected_material_id", None),
                                learning_panel.refresh(),
                            ),
                        ).props("outlined").classes("w-full")
                        item_select.update()

                        ui.markdown(
                            f"### {snapshot.item.title}\n\n{snapshot.item.content_outline}"
                            if snapshot.item
                            else "Select a curriculum section to start studying."
                        ).classes("w-full")

                        material_select = ui.select(
                            material_options(snapshot.item_materials),
                            value=state.selected_material_id,
                            label="Source Material",
                            on_change=lambda e: (
                                setattr(state, "selected_material_id", e.value),
                                learning_panel.refresh(),
                            ),
                        ).props("outlined").classes("w-full")
                        material_select.update()

                        ui.markdown(
                            snapshot.viewer_info or "Select a curriculum section to inspect its source materials."
                        ).classes("w-full")

                        with ui.element("div").classes("viewer-pane w-full"):
                            ui.html(f'<pre class="source-pre">{html.escape(snapshot.viewer_text)}</pre>')

                    with ui.card().classes("panel-card").style("flex: 1 1 520px; min-width: 320px;"):
                        ui.label("Tutor Chat").classes("text-xl font-semibold")
                        ui.label("Chat stays on the right so longer sessions still feel anchored to the lesson context.").classes("muted-copy")
                        with ui.scroll_area().classes("chat-scroller"):
                            chat_container = ui.column().classes("w-full gap-3 p-3")
                        render_chat_messages(chat_container, snapshot.chat_history)

                        chat_input = ui.textarea(
                            "Ask the Tutor",
                            placeholder="Use the chat once you have a section selected.",
                        ).props("outlined autogrow").classes("w-full")

                        status_label = ui.label(state.chat_status).classes("muted-copy")

                        async def send_chat() -> None:
                            try:
                                message = (chat_input.value or "").strip()
                                if not message:
                                    raise ValueError("Enter a message to continue the tutoring session.")

                                session_data = ensure_session_access(user, state.selected_session_id)
                                if not session_data:
                                    raise ValueError("Select a topic first.")

                                dialogue = build_dialogue_service()
                                curriculum = resolve_curriculum(session_data, state)
                                chat_session = get_or_create_chat_session(session_data, session_data.session_id)
                                item = resolve_item(curriculum, state)
                                if item:
                                    chat_session.active_item_id = item.id

                                rag_context, rag_chunk_ids = await dialogue.build_rag_context(
                                    profile=session_data.user_profile,
                                    message=message,
                                    curriculum=curriculum,
                                    active_item_id=chat_session.active_item_id,
                                )

                                history = serialize_chat(chat_session.messages)
                                history.append({"role": "user", "content": message})
                                history.append({"role": "assistant", "content": ""})
                                render_chat_messages(chat_container, history)
                                chat_input.value = ""
                                chat_input.update()
                                status_label.set_text("Tutor is responding...")
                                set_status("chat_status", "Tutor is responding...")

                                async for token in dialogue.chat_stream(
                                    profile=session_data.user_profile,
                                    chat_session=chat_session,
                                    message=message,
                                    curriculum=curriculum,
                                    active_item_id=chat_session.active_item_id,
                                    rag_context=rag_context,
                                    rag_chunk_ids=rag_chunk_ids,
                                ):
                                    history[-1]["content"] = f"{history[-1]['content']}{token}"
                                    render_chat_messages(chat_container, history)

                                session_store.save(session_data.session_id)
                                clear_status("chat_status")
                                status_label.set_text("")
                                learning_panel.refresh()
                            except Exception as exc:
                                handle_error("chat_status", exc)
                                status_label.set_text(state.chat_status)

                        chat_input.on(
                            "keydown.enter",
                            lambda: send_chat(),
                            js_handler="""
                                (event) => {
                                    if (!event.shiftKey) {
                                        event.preventDefault();
                                        emit();
                                    }
                                }
                            """,
                        )
                        ui.button("Send", on_click=send_chat, color="primary").props("unelevated")

        @ui.refreshable
        def openstax_panel() -> None:
            user = require_user(state)
            books = openstax_service.list_books()
            with ui.column().classes("w-full gap-4"):
                render_status(state.openstax_status)
                if user.role == "admin":
                    with ui.card().classes("panel-card w-full"):
                        ui.label("OpenStax Library").classes("text-xl font-semibold")
                        ui.label("Upload or reindex shared textbooks without repainting the whole workspace.").classes("muted-copy")
                        upload = ui.upload(
                            label="Upload OpenStax PDF",
                            auto_upload=True,
                            max_file_size=settings.pdf.max_file_size_mb * 1024 * 1024,
                        ).props("accept=.pdf").classes("w-full")

                        async def handle_openstax_upload(event: events.UploadEventArguments) -> None:
                            try:
                                content = await event.file.read()
                                safe_name = Path(event.file.name).name
                                book = await openstax_service.upload_book(safe_name, content)
                                state.selected_openstax_file_name = book.file_name
                                set_status("openstax_status", f"Uploaded OpenStax book `{book.title}`.")
                                safe_notify("OpenStax book uploaded.", type="positive")
                                upload.reset()
                                openstax_panel.refresh()
                            except Exception as exc:
                                handle_error("openstax_status", exc)
                                openstax_panel.refresh()

                        upload.on_upload(handle_openstax_upload)

                        select_options = {book.file_name: book.title for book in books}
                        book_select = ui.select(
                            select_options,
                            value=state.selected_openstax_file_name,
                            label="Existing Book",
                            on_change=lambda e: setattr(state, "selected_openstax_file_name", e.value),
                        ).props("outlined").classes("w-full")
                        book_select.update()

                        async def reindex_book() -> None:
                            try:
                                if not state.selected_openstax_file_name:
                                    raise ValueError("Select an existing OpenStax book.")
                                book = next(
                                    (
                                        entry
                                        for entry in openstax_service.list_books()
                                        if entry.file_name == state.selected_openstax_file_name
                                    ),
                                    None,
                                )
                                if not book:
                                    raise ValueError("Select an existing OpenStax book.")
                                await openstax_service.reindex_book(book.id)
                                set_status("openstax_status", f"Re-indexed `{book.title}`.")
                                safe_notify("OpenStax book reindexed.", type="positive")
                                openstax_panel.refresh()
                            except Exception as exc:
                                handle_error("openstax_status", exc)
                                openstax_panel.refresh()

                        async def delete_book() -> None:
                            try:
                                if not state.selected_openstax_file_name:
                                    raise ValueError("Select an existing OpenStax book.")
                                book = next(
                                    (
                                        entry
                                        for entry in openstax_service.list_books()
                                        if entry.file_name == state.selected_openstax_file_name
                                    ),
                                    None,
                                )
                                if not book:
                                    raise ValueError("Select an existing OpenStax book.")
                                await openstax_service.delete_book(book.id)
                                state.selected_openstax_file_name = None
                                set_status("openstax_status", f"Deleted `{book.title}`.")
                                safe_notify("OpenStax book deleted.", type="positive")
                                openstax_panel.refresh()
                            except Exception as exc:
                                handle_error("openstax_status", exc)
                                openstax_panel.refresh()

                        with ui.row().classes("gap-3"):
                            ui.button("Reindex Book", on_click=reindex_book).props("outline")
                            ui.button("Delete Book", on_click=delete_book).props("outline")

                with ui.card().classes("panel-card table-shell"):
                    ui.label("Available Books").classes("text-xl font-semibold")
                    ui.table(
                        rows=build_openstax_rows(),
                        columns=TABLE_COLUMNS["openstax"],
                        row_key="id",
                        pagination=8,
                    ).props("flat bordered").classes("w-full")

        @ui.refreshable
        def admin_panel() -> None:
            user = require_user(state)
            with ui.column().classes("w-full gap-4"):
                render_status(state.admin_status)
                if user.role != "admin":
                    with ui.card().classes("panel-card w-full"):
                        ui.label("Admin tools are only available to admin accounts.").classes("muted-copy")
                    return

                with ui.card().classes("panel-card w-full"):
                    ui.label("User Administration").classes("text-xl font-semibold")
                    with ui.row(wrap=True).classes("w-full gap-4 items-start"):
                        with ui.column().style("flex: 1 1 320px; min-width: 280px;"):
                            create_email = ui.input("New User Email").props("outlined").classes("w-full")
                            create_password = ui.input(
                                "Temporary Password",
                                password=True,
                                password_toggle_button=True,
                            ).props("outlined").classes("w-full")
                            create_role = ui.radio({"user": "User", "admin": "Admin"}, value="user").props("inline")

                            def create_user() -> None:
                                try:
                                    normalized_email = (create_email.value or "").strip().lower()
                                    if "@" not in normalized_email:
                                        raise ValueError("Enter a valid email.")
                                    if len(create_password.value or "") < 8:
                                        raise ValueError("Passwords must be at least 8 characters.")
                                    if user_store.get_by_email(normalized_email):
                                        raise ValueError("That email is already registered.")
                                    user_store.create_user(
                                        normalized_email,
                                        auth_service.hash_password(create_password.value or ""),
                                        role=create_role.value,
                                    )
                                    set_status("admin_status", f"Created `{normalized_email}`.")
                                    safe_notify("User created.", type="positive")
                                    admin_panel.refresh()
                                except Exception as exc:
                                    handle_error("admin_status", exc)
                                    admin_panel.refresh()

                            ui.button("Create User", on_click=create_user, color="primary").props("unelevated")

                        with ui.column().style("flex: 1 1 320px; min-width: 280px;"):
                            delete_options = {
                                entry.email: entry.email
                                for entry in user_store.list_users()
                                if entry.id != user.id
                            }
                            delete_select = ui.select(
                                delete_options,
                                value=state.selected_admin_email,
                                label="Delete User",
                                on_change=lambda e: setattr(state, "selected_admin_email", e.value),
                            ).props("outlined").classes("w-full")
                            delete_select.update()

                            async def delete_user() -> None:
                                try:
                                    if not state.selected_admin_email:
                                        raise ValueError("Select an existing user email.")
                                    target = user_store.get_by_email(state.selected_admin_email.strip().lower())
                                    if not target:
                                        raise ValueError("Select an existing user email.")
                                    if target.id == user.id:
                                        raise ValueError("Admins cannot delete themselves from this UI.")
                                    from app.routers.admin_users import delete_user as delete_user_route

                                    await delete_user_route(
                                        target.id,
                                        admin_user=user,
                                        store=user_store,
                                        session_store=session_store,
                                        vector_store=vector_store,
                                        settings=settings,
                                    )
                                    state.selected_admin_email = None
                                    set_status("admin_status", f"Deleted `{target.email}`.")
                                    safe_notify("User deleted.", type="positive")
                                    admin_panel.refresh()
                                except Exception as exc:
                                    handle_error("admin_status", exc)
                                    admin_panel.refresh()

                            ui.button("Delete User", on_click=delete_user).props("outline")

                    ui.table(
                        rows=build_admin_rows(),
                        columns=TABLE_COLUMNS["admin"],
                        row_key="id",
                        pagination=8,
                    ).props("flat bordered").classes("w-full")

        render_shell()

    storage_secret = env_settings.jwt_secret or settings.auth.jwt_secret
    ui.run_with(
        fastapi_app,
        mount_path="/",
        title="LLM Tutor",
        storage_secret=storage_secret,
        show_welcome_message=False,
        dark=False,
    )
