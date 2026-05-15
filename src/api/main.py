"""FastAPI application for Ragbot.

Provides REST API endpoints for chat, workspaces, models, and configuration.
Supports SSE streaming for chat responses.

Lifespan wiring (Phase 5)
-------------------------

The lifespan handler is the single place that turns the substrate primitives
(:mod:`synthesis_engine.tasks`, :mod:`synthesis_engine.observability`,
:mod:`synthesis_engine.mcp`) on at process start and off at process stop.
Production deployments rely on this hook; tests that do not need the full
wiring construct their own FastAPI app and skip it.

Startup contract
~~~~~~~~~~~~~~~~

1.  Call :func:`synthesis_engine.observability.init_tracer` so the
    OpenTelemetry tracer + meter providers are wired before any later
    startup step (or any HTTP request) emits spans or records metrics.
    Exporter selection is driven by env vars: ``OTEL_EXPORTER_OTLP_ENDPOINT``
    routes spans to an OTLP collector (the bundled docker-compose stack
    points this at Jaeger on ``http://jaeger:4317``); without it, spans
    fall through to OTEL's no-op tracer and observability is silently
    disabled. The Prometheus reader is always attached so ``/api/metrics``
    works regardless of exporter configuration.

2.  Call :meth:`BackgroundTaskManager.recover_crashed_tasks` so any task left
    in ``running`` state by a previous (crashed) process gets a deterministic
    ``crashed`` terminal line before any new task starts. The task substrate's
    contract — every task that started can ALWAYS be observed in a terminal
    state — relies on this running before the first :func:`start_task` of a
    new process.

3.  Register the built-in task factories (``tasks.heartbeat`` and
    ``memory.consolidate_recent_idle``) on the process-singleton registry so
    YAML-declared schedules can resolve their task names.

4.  Opt-in scheduler: when ``RAGBOT_SCHEDULER`` is truthy, construct a
    :class:`SchedulerLoop`, call :meth:`SchedulerLoop.start`, and stash the
    loop on ``app.state.scheduler_loop`` so shutdown can find it. Without the
    env var, no scheduler runs — test suites and dev installs stay quiet.

5.  Touch the MCP client singleton once so the agent loop's MCP tools resolve
    against the same client every router uses. The substrate already
    lazy-constructs a client on first use; this step exists so a misconfigured
    ``~/.synthesis/mcp.yaml`` surfaces at startup, not on the first agent call.

6.  Construct an :class:`AgentLoop` wired to the lifespan's LLM backend,
    the just-resolved MCP client, and a :class:`FilesystemCheckpointStore`;
    register it via :func:`api.routers.agent.set_default_loop` so the
    ``/api/agent/*`` routes resolve against this instance. Without this
    step the router returns ``"Agent loop is not configured"`` on every
    call, which was the behaviour through v3.4. The loop is stashed on
    ``app.state.agent_loop`` so shutdown can clear the registration.

Shutdown contract
~~~~~~~~~~~~~~~~~

1.  Clear the agent-loop singleton (``set_default_loop(None)``) so the
    router does not retain a reference to a teared-down LLM backend or
    MCP client past the app's lifetime.
2.  If the scheduler is running, call :meth:`SchedulerLoop.stop`.
3.  Call :func:`synthesis_engine.observability.shutdown_tracer` so the
    OpenTelemetry exporter has a chance to flush pending spans —
    BUT only when ``app.state.owns_tracer`` is true, i.e., when the
    lifespan itself initialised the tracer. Tests and embedders install
    their own tracer before the lifespan fires; tearing it down at app
    shutdown would invalidate the host's instrumentation.

The audit log writes synchronously per event (see
``synthesis_engine.policy.audit``) so it has no buffered state to flush.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

# Add src directory to path
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from ragbot import VERSION, HealthResponse

from .dependencies import get_settings, check_rag_available
from .routers import agent, chat, workspaces, models, config, preferences, memory, mcp, metrics, policy, skills, tasks

logger = logging.getLogger("api.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.

    Wires the observability substrate, the background-task substrate, the
    opt-in scheduler, the MCP client, and the agent loop at process start;
    tears them down at process stop. See the module docstring for the full
    contract.
    """
    # ----- Startup ----------------------------------------------------------
    settings = get_settings()
    logger.info("Ragbot API v%s starting...", VERSION)
    logger.info("AI Knowledge root: %s", settings.ai_knowledge_root)
    logger.info("RAG available: %s", check_rag_available())

    # 1. Observability — initialise the tracer + meter providers FIRST so
    #    every later startup step (and every HTTP request that follows)
    #    runs under live instrumentation. Exporter selection comes from
    #    the OTEL standard env vars (OTEL_EXPORTER_OTLP_ENDPOINT,
    #    OTEL_SERVICE_NAME, etc.). When no endpoint is configured the
    #    tracer is a no-op; metrics still flow to /api/metrics because
    #    the Prometheus reader is always attached.
    #
    #    Ownership semantics: if a tracer is ALREADY initialised when the
    #    lifespan starts (this happens in tests where a session-scoped
    #    fixture has installed an InMemorySpanExporter, or in embedding
    #    scenarios where the host process owns the tracer), the lifespan
    #    leaves it alone and records that it does NOT own the tracer.
    #    The shutdown handler reads ``app.state.owns_tracer`` to decide
    #    whether to call ``shutdown_tracer`` — calling it unconditionally
    #    would tear down a tracer the embedder still needs.
    app.state.owns_tracer = False
    try:
        from synthesis_engine.observability import (
            get_tracer_provider,
            init_tracer,
        )

        prior_provider = get_tracer_provider()
        provider = init_tracer(service_name="ragbot-api")
        # We own the tracer iff init_tracer just created (or replaced) it
        # for us. The substrate's explicit-exporter guard returns the same
        # provider when an explicit exporter was already wired in, which
        # is how we detect the test/embedder case.
        app.state.owns_tracer = (
            prior_provider is None or provider is not prior_provider
        )

        otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if provider is None:
            logger.info(
                "OpenTelemetry SDK not installed; tracer is no-op.",
            )
        elif not app.state.owns_tracer:
            logger.info(
                "Tracer already initialised by host; lifespan deferring.",
            )
        elif otlp_endpoint:
            logger.info(
                "Tracer initialised; OTLP endpoint=%s service=%s",
                otlp_endpoint,
                os.environ.get("OTEL_SERVICE_NAME", "ragbot-api"),
            )
        else:
            logger.info(
                "Tracer initialised; no OTLP endpoint configured "
                "(set OTEL_EXPORTER_OTLP_ENDPOINT to export spans).",
            )
    except Exception as exc:  # noqa: BLE001 — startup must keep going
        logger.warning("Tracer initialisation failed: %s", exc)

    # 2. Crash recovery — must run BEFORE any new task starts so a task
    #    started later this process doesn't get mis-classified as crashed
    #    when the recovery walker sees its in-progress 'running' line.
    try:
        from synthesis_engine.tasks import default_manager

        manager = default_manager()
        recovered = manager.recover_crashed_tasks()
        if recovered:
            logger.info(
                "Marked %d task(s) crashed from a prior run.", len(recovered),
            )
        app.state.task_manager = manager
    except Exception as exc:  # noqa: BLE001 — startup must keep going
        logger.warning("Task manager startup failed: %s", exc)
        app.state.task_manager = None

    # 3. Register built-in task factories on the process-singleton registry.
    try:
        from synthesis_engine.tasks.registry import (
            register_default_task_factories,
        )

        registry = register_default_task_factories()
        logger.info(
            "Registered task factories: %s", ", ".join(registry.names()),
        )
        app.state.task_registry = registry
    except Exception as exc:  # noqa: BLE001
        logger.warning("Task-factory registration failed: %s", exc)
        app.state.task_registry = None

    # 4. Scheduler loop (opt-in via RAGBOT_SCHEDULER).
    app.state.scheduler_loop = None
    try:
        from synthesis_engine.tasks.scheduler import (
            SchedulerLoop,
            scheduler_enabled,
        )

        if scheduler_enabled():
            loop_obj = SchedulerLoop()
            loop_obj.start()
            app.state.scheduler_loop = loop_obj
            tasks.set_scheduler_loop(loop_obj)
            logger.info(
                "Scheduler started; registered schedules: %s",
                loop_obj.registered_ids,
            )
        else:
            logger.info(
                "Scheduler disabled (set RAGBOT_SCHEDULER=1 to enable).",
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Scheduler startup failed: %s", exc)

    # 5. MCP client — singleton resolution. The substrate lazy-builds the
    #    client on first use; we touch it here so a malformed mcp.yaml fails
    #    loudly at startup instead of on the first agent call.
    try:
        from synthesis_engine.mcp import get_default_client, set_default_client
        from synthesis_engine.mcp.client import MCPClient
        from synthesis_engine.mcp import load_mcp_config

        if get_default_client() is None:
            try:
                config_obj = load_mcp_config()
                set_default_client(MCPClient(config=config_obj))
            except Exception as exc:  # noqa: BLE001 — empty/missing config is fine
                logger.info(
                    "MCP client not initialised at startup: %s "
                    "(will lazy-construct on first use).",
                    exc,
                )
    except Exception as exc:  # noqa: BLE001
        logger.debug("MCP startup probe failed: %s", exc)

    # 6. Agent loop — construct an AgentLoop wired to the lifespan's LLM
    #    backend, the just-resolved MCP client (may be None — the loop
    #    tolerates that and skips MCP tool calls), and a
    #    FilesystemCheckpointStore so /api/agent/run can persist and
    #    replay sessions. Register it via set_default_loop() so the
    #    /api/agent/* routes resolve against this instance instead of
    #    returning the "not configured" error the router emits when the
    #    singleton is None. App.state holds a reference so shutdown can
    #    clear the registration without leaking the singleton.
    app.state.agent_loop = None
    try:
        from synthesis_engine.agent import (
            AgentLoop,
            FilesystemCheckpointStore,
        )
        from synthesis_engine.llm import get_llm_backend
        from synthesis_engine.mcp import get_default_client as _get_mcp
        from .routers.agent import set_default_loop as _set_default_loop

        llm_backend = get_llm_backend()
        mcp_client = _get_mcp()  # may be None
        checkpoint_store = FilesystemCheckpointStore()
        agent_loop = AgentLoop(
            llm_backend=llm_backend,
            mcp_client=mcp_client,
            checkpoint_store=checkpoint_store,
            default_mcp_server="local",
        )
        _set_default_loop(agent_loop)
        app.state.agent_loop = agent_loop
        logger.info(
            "Agent loop initialised; /api/agent/run is live "
            "(mcp_client=%s).",
            "wired" if mcp_client is not None else "unset",
        )
    except Exception as exc:  # noqa: BLE001 — startup must keep going
        logger.warning(
            "Agent loop initialisation failed: %s "
            "(/api/agent/run will return 'not configured').",
            exc,
        )

    try:
        yield
    finally:
        # ----- Shutdown -----------------------------------------------------
        logger.info("Ragbot API shutting down...")

        # Clear the agent-loop singleton so the router does not hold a
        # reference to a teared-down LLM backend / MCP client past app
        # lifetime. Tests that build successive apps rely on this clearing
        # so the next app gets a fresh AgentLoop.
        if getattr(app.state, "agent_loop", None) is not None:
            try:
                from .routers.agent import set_default_loop as _set_default_loop

                _set_default_loop(None)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Agent-loop teardown raised: %s", exc)
            finally:
                app.state.agent_loop = None

        # Stop the scheduler if it is running.
        sched_loop = getattr(app.state, "scheduler_loop", None)
        if sched_loop is not None:
            try:
                sched_loop.stop()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Scheduler shutdown raised: %s", exc)
            finally:
                tasks.set_scheduler_loop(None)
                app.state.scheduler_loop = None

        # Flush observability. The audit log writes synchronously per event
        # and has no buffer of its own, so there is nothing to flush there.
        # Only shut the tracer down when the lifespan owns it — tests and
        # embedders install their own tracer before the lifespan fires and
        # rely on it surviving past the FastAPI app's lifetime.
        if getattr(app.state, "owns_tracer", False):
            try:
                from synthesis_engine.observability import shutdown_tracer

                shutdown_tracer()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Tracer shutdown raised: %s", exc)


app = FastAPI(
    title="Ragbot API",
    description="REST API for Ragbot - AI Knowledge Assistant",
    version=VERSION,
    lifespan=lifespan,
)

# Configure CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router)
app.include_router(workspaces.router)
app.include_router(models.router)
app.include_router(config.router)
app.include_router(preferences.router)
app.include_router(memory.router)
app.include_router(mcp.router)
app.include_router(metrics.router)
app.include_router(agent.router)
app.include_router(policy.router)
app.include_router(skills.router)
app.include_router(tasks.router)


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Health check endpoint.

    Reports overall status, RAG availability, and pgvector backend health
    (connectivity, schema version, workspace count).
    """
    backend_health = {}
    try:
        from synthesis_engine.vectorstore import get_vector_store

        vs = get_vector_store()
        if vs is not None:
            backend_health = vs.healthcheck()
    except Exception as exc:  # pragma: no cover - defensive
        backend_health = {"backend": "unknown", "ok": False, "reason": str(exc)}

    from ragbot.demo import is_demo_mode, DEMO_WORKSPACE_NAME, DEMO_SKILLS_WORKSPACE_NAME

    # In demo mode, the host's true workspaces count would leak through
    # the healthcheck metadata. Override with the count of demo-visible
    # collections so screenshots cannot reveal that other workspaces
    # exist on the same vector store.
    if is_demo_mode():
        try:
            from synthesis_engine.vectorstore import get_vector_store as _vs

            v = _vs()
            allowed = {DEMO_WORKSPACE_NAME, DEMO_SKILLS_WORKSPACE_NAME}
            if v is not None:
                visible = sum(1 for c in v.list_collections() if c in allowed)
                if isinstance(backend_health, dict):
                    backend_health = dict(backend_health)
                    backend_health["workspaces"] = visible
        except Exception:
            pass

    return HealthResponse(
        status="ok",
        version=VERSION,
        rag_available=check_rag_available(),
        vector_backend=backend_health,
        demo_mode=is_demo_mode(),
    )


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Ragbot API",
        "version": VERSION,
        "docs": "/docs",
        "health": "/health",
    }


# For running with uvicorn directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
