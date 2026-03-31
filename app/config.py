import os
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings
import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"


class EnvSettings(BaseSettings):
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    tavily_api_key: str = ""
    cors_origins: str = "http://localhost:5173"
    jwt_secret: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


class ModelConfig(BaseModel):
    model: str = ""
    max_tokens: int = 2000
    stream: bool = False
    reasoning_effort: str = "low"
    response_format: dict | None = None


class ModelsConfig(BaseModel):
    defaults: dict[str, str] = {}
    module_overrides: dict[str, dict[str, ModelConfig]] = {}

    def get_model_config(self, module: str, operation: str) -> ModelConfig:
        overrides = self.module_overrides.get(module, {})
        if operation in overrides:
            cfg = overrides[operation]
            if not cfg.model:
                cfg.model = self.defaults.get("primary_model", "openai/gpt-5.4-mini")
            return cfg
        return ModelConfig(model=self.defaults.get("primary_model", "openai/gpt-5.4-mini"))


class PromptTemplate(BaseModel):
    system: str = ""
    user: str = ""


class PromptsConfig(BaseModel):
    gathering: dict[str, PromptTemplate] = {}
    curriculum: dict[str, PromptTemplate] = {}
    dialogue: dict[str, str] = {}

    def get_prompt(self, module: str, operation: str) -> PromptTemplate | str:
        section = getattr(self, module, {})
        if isinstance(section, dict):
            return section.get(operation, PromptTemplate())
        return PromptTemplate()


class QdrantSettings(BaseModel):
    mode: str = "memory"
    path: str | None = None
    host: str = "localhost"
    port: int = 6333
    collection_name: str = "tutor_materials"
    embedding_dimension: int = 1536


class GatheringSettings(BaseModel):
    max_iterations: int = 3
    queries_per_iteration: int = 5
    min_relevance_score: int = 3
    tavily_search_depth: str = "advanced"
    max_materials: int = 20


class CurriculumSettings(BaseModel):
    max_concepts: int = 10
    max_objectives_per_concept: int = 3
    chunk_size: int = 512
    chunk_overlap: int = 50


class DialogueSettings(BaseModel):
    max_history_messages: int = 20
    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.7


class LoggingSettings(BaseModel):
    log_dir: str = "data/logs"
    log_full_payloads: bool = True


class AppSettings(BaseModel):
    name: str = "LLM Tutor"
    debug: bool = True
    data_dir: str = "data"


class PDFSettings(BaseModel):
    upload_dir: str = "data/uploads"
    chunk_size: int = 800
    chunk_overlap: int = 100
    max_file_size_mb: int = 50


class AuthSettings(BaseModel):
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 72
    max_upload_bytes_per_user: int = 1_073_741_824  # 1GB


class OpenStaxSettings(BaseModel):
    upload_dir: str = "data/openstax"
    collection_name: str = "openstax_materials"
    chunk_size: int = 1500
    chunk_overlap: int = 150


class Settings(BaseModel):
    app: AppSettings = AppSettings()
    auth: AuthSettings = AuthSettings()
    qdrant: QdrantSettings = QdrantSettings()
    gathering: GatheringSettings = GatheringSettings()
    curriculum: CurriculumSettings = CurriculumSettings()
    dialogue: DialogueSettings = DialogueSettings()
    pdf: PDFSettings = PDFSettings()
    openstax: OpenStaxSettings = OpenStaxSettings()
    logging: LoggingSettings = LoggingSettings()


def _load_yaml(filename: str) -> dict:
    path = Path(filename)
    if not path.is_absolute():
        path = CONFIG_DIR / filename
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


def load_models_config() -> ModelsConfig:
    data = _load_yaml("models.yaml")
    overrides = {}
    for module, ops in data.get("module_overrides", {}).items():
        overrides[module] = {op: ModelConfig(**cfg) for op, cfg in ops.items()}
    return ModelsConfig(
        defaults=data.get("defaults", {}),
        module_overrides=overrides,
    )


def load_prompts_config() -> PromptsConfig:
    data = _load_yaml("prompts.yaml")
    gathering = {}
    for op, tmpl in data.get("gathering", {}).items():
        if isinstance(tmpl, dict):
            gathering[op] = PromptTemplate(**tmpl)
        else:
            gathering[op] = PromptTemplate(system=str(tmpl))

    curriculum = {}
    for op, tmpl in data.get("curriculum", {}).items():
        if isinstance(tmpl, dict):
            curriculum[op] = PromptTemplate(**tmpl)
        else:
            curriculum[op] = PromptTemplate(system=str(tmpl))

    dialogue = data.get("dialogue", {})

    return PromptsConfig(gathering=gathering, curriculum=curriculum, dialogue=dialogue)


def load_settings() -> Settings:
    settings_file = os.getenv("SETTINGS_FILE", "").strip()
    if settings_file:
        data = _load_yaml(settings_file)
    else:
        app_env = os.getenv("APP_ENV", "").strip().lower()
        filename = "settings.prod.yaml" if app_env == "production" else "settings.yaml"
        data = _load_yaml(filename)
    return Settings(**data)
