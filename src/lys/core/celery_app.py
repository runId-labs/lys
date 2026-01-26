from celery import Celery, current_app, signals

from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.managers.pubsub import PubSubManager
from lys.core.models import PubSubConfig


def create_celery_app(settings, app_manager=None, component_types=None) -> Celery:
    """
    Create and configure Celery application.

    Args:
        settings: Application settings with Celery configuration
        app_manager: Optional AppManager instance for testing.
                     If None, uses LysAppManager singleton (production)
        component_types: Optional list of component types to load.
                         If None, defaults to [ENTITIES, SERVICES]

    Returns:
        Configured Celery app with app_manager attached

    Raises:
        RuntimeError: If Celery is not configured in settings

    Example:
        # Production (uses singleton)
        from lys.core.configs import settings
        celery_app = create_celery_app(settings)

        # Testing (inject mock)
        test_app_manager = AppManager(test_settings)
        celery_app = create_celery_app(test_settings, app_manager=test_app_manager)
    """
    if settings.celery is None:
        raise RuntimeError("Celery is not configured. Set settings.celery first.")

    settings.celery.validate()

    # Create Celery app
    celery_app = Celery('lys')

    # Configure from settings
    celery_config = {
        'broker_url': settings.celery.broker_url,
        'result_backend': settings.celery.result_backend,
        'broker_connection_retry_on_startup': settings.celery.broker_connection_retry_on_startup,
        'task_serializer': settings.celery.task_serializer,
        'result_serializer': settings.celery.result_serializer,
        'accept_content': settings.celery.accept_content,
        'task_track_started': settings.celery.task_track_started,
        'task_time_limit': settings.celery.task_time_limit,
        'task_soft_time_limit': settings.celery.task_soft_time_limit,
        'beat_schedule': settings.celery.beat_schedule,
        'timezone': settings.celery.timezone,
        'enable_utc': settings.celery.enable_utc,
        'worker_prefetch_multiplier': settings.celery.worker_prefetch_multiplier,
        'worker_max_tasks_per_child': settings.celery.worker_max_tasks_per_child,
        'imports': settings.celery.tasks,
    }

    celery_app.config_from_object(celery_config)

    # Attach app_manager to celery_app
    if app_manager is not None:
        # Testing: use injected app_manager
        celery_app.app_manager = app_manager
    else:
        # Production: use singleton LysAppManager
        # Local import to avoid circular dependency: celery_app <- app_manager <- celery_app
        from lys.core.managers.app import LysAppManager
        celery_app.app_manager = LysAppManager()

    # Load components for workers
    # Default: ENTITIES and SERVICES only (FIXTURES not needed in workers)
    if component_types is None:
        component_types = [
            AppComponentTypeEnum.ENTITIES,
            AppComponentTypeEnum.SERVICES,
        ]
    celery_app.app_manager.configure_component_types(component_types)
    celery_app.app_manager.load_all_components()

    return celery_app


@signals.worker_process_init.connect
def init_worker_process(**kwargs):
    """
    Initialize worker process.

    This signal is called when a new worker process is spawned.
    Each worker process gets its own database connection and pubsub client.
    """
    if hasattr(current_app, 'app_manager'):
        # Reset database connection for this worker process
        current_app.app_manager.database.reset_database_connection()

        # Initialize pubsub if configured (Celery doesn't run _app_lifespan)
        pubsub_config = current_app.app_manager.settings.get_plugin_config("pubsub")
        if pubsub_config:
            validated_config = PubSubConfig(**pubsub_config)
            current_app.app_manager.pubsub = PubSubManager(
                redis_url=validated_config.redis_url,
                channel_prefix=validated_config.channel_prefix
            )
            current_app.app_manager.pubsub.initialize_sync()


@signals.worker_process_shutdown.connect
def shutdown_worker_process(**kwargs):
    """
    Shutdown worker process.

    This signal is called when a worker process is shutting down.
    Cleanly closes pubsub connections.
    """
    if hasattr(current_app, 'app_manager'):
        # Shutdown pubsub sync client if initialized
        if current_app.app_manager.pubsub:
            current_app.app_manager.pubsub.shutdown_sync()