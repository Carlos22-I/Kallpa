"""Raíz de composición: único lugar donde se eligen implementaciones concretas."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .application.use_cases import (
    AskAssistant,
    GetAlerts,
    GetFamilySummary,
    GetHealthDashboard,
    LogMeal,
    LogSupplement,
    PlanHomeVisits,
    PrioritizeChildren,
    RegisterChild,
    Settings,
    UpdateChildClinical,
)
from .application.ports import Clock
from .config import Config
from .infrastructure.adapters import (
    DbPhotoStorage,
    InMemoryEventBus,
    JsonFoodCatalog,
    JsonTerritory,
    LimaClock,
    LocalPhotoStorage,
)
from .infrastructure.ai.llm import ClaudeClient, LLMAssistant, LLMPlateAnalyzer, OpenAICompatibleClient, UsageMeter
from .infrastructure.ai.local import LocalAssistant, LocalPlateAnalyzer
from .infrastructure.ai.resilient import ResilientAnalyzer, ResilientAssistant
from .infrastructure.persistence.sqlite import (
    Database,
    SqliteChildRepository,
    SqliteMealRepository,
    SqliteSupplementRepository,
)

log = logging.getLogger("kallpa")


def build_clients(cfg: Config, meter: UsageMeter) -> list:
    """Factory: clientes LLM según la configuración. Orden de la cadena: Claude → OpenAI-compatible → local."""
    price = (cfg.ai_price_in, cfg.ai_price_out) if cfg.ai_price_in is not None and cfg.ai_price_out is not None else None
    clients = []
    if cfg.ai_provider in ("auto", "claude") and cfg.anthropic_api_key:
        clients.append(ClaudeClient(cfg.anthropic_api_key, cfg.anthropic_model, cfg.ai_timeout_s, meter,
                                    price if cfg.ai_provider == "claude" else None))
    if cfg.ai_provider in ("auto", "openai") and cfg.openai_api_key:
        clients.append(OpenAICompatibleClient(cfg.openai_api_key, cfg.openai_model, cfg.openai_base_url,
                                              cfg.ai_timeout_s, meter, price if cfg.ai_provider == "openai" else None,
                                              cfg.openai_reasoning_effort))
    return clients


def build_ai(cfg: Config, meter: UsageMeter | None = None) -> tuple[ResilientAnalyzer, ResilientAssistant]:
    """Strategy + cadena de responsabilidad: proveedores externos y, al final, el modelo local."""
    clients = build_clients(cfg, meter or UsageMeter())
    analyzers = [LLMPlateAnalyzer(c) for c in clients] + [LocalPlateAnalyzer()]
    assistants = [LLMAssistant(c) for c in clients] + [LocalAssistant()]
    log.info("Cadena de IA: %s", " -> ".join(a.name for a in analyzers))
    return ResilientAnalyzer(analyzers), ResilientAssistant(assistants)


@dataclass
class Container:
    cfg: Config
    register: RegisterChild
    log_meal: LogMeal
    log_supplement: LogSupplement
    family_summary: GetFamilySummary
    prioritize: PrioritizeChildren
    update_clinical: UpdateChildClinical
    plan_visits: PlanHomeVisits
    dashboard: GetHealthDashboard
    ask: AskAssistant
    alerts: GetAlerts
    children: SqliteChildRepository
    meals: SqliteMealRepository
    supplements: SqliteSupplementRepository
    catalog: JsonFoodCatalog
    territory: JsonTerritory
    bus: InMemoryEventBus
    analyzer: ResilientAnalyzer
    assistant: ResilientAssistant
    usage: UsageMeter
    clock: Clock
    db: object
    photos: object


def build_storage(cfg: Config):
    """Factory de persistencia: PostgreSQL si hay DATABASE_URL (producción), si no SQLite (local)."""
    if cfg.database_url:
        from .infrastructure.persistence.postgres import PostgresDatabase

        db = PostgresDatabase(cfg.database_url)
        return db, DbPhotoStorage(db)        # en Render el disco es efímero: las fotos van a la base
    return Database(cfg.database_path), LocalPhotoStorage(cfg.upload_dir)


def build_container(cfg: Config, clock: Clock | None = None) -> Container:
    clock = clock or LimaClock()
    db, photos = build_storage(cfg)
    children, meals, sups = SqliteChildRepository(db), SqliteMealRepository(db), SqliteSupplementRepository(db)
    catalog = JsonFoodCatalog(cfg.data_dir / "alimentos.json", cfg.data_dir / "recetas.json")
    territory = JsonTerritory(cfg.data_dir / "abancay.json")
    bus = InMemoryEventBus()
    usage = UsageMeter()
    analyzer, assistant = build_ai(cfg, usage)
    settings = Settings(review_threshold=cfg.review_threshold)
    prioritize = PrioritizeChildren(children, meals, sups, clock)
    knowledge = (cfg.data_dir / "conocimiento.md").read_text(encoding="utf-8")
    return Container(
        cfg=cfg,
        register=RegisterChild(children, territory, clock),
        log_meal=LogMeal(children, meals, analyzer, catalog, photos, bus, clock, settings),
        log_supplement=LogSupplement(children, sups, bus, clock),
        family_summary=GetFamilySummary(children, meals, sups, catalog, clock),
        prioritize=prioritize,
        update_clinical=UpdateChildClinical(children, bus),
        plan_visits=PlanHomeVisits(prioritize, territory),
        dashboard=GetHealthDashboard(prioritize, meals, clock),
        ask=AskAssistant(assistant, knowledge, children, clock),
        alerts=GetAlerts(children, sups, clock),
        children=children, meals=meals, supplements=sups, catalog=catalog, territory=territory,
        bus=bus, analyzer=analyzer, assistant=assistant, usage=usage, clock=clock, db=db, photos=photos,
    )
