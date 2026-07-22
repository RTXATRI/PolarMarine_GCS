from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.services.connections import ConnectionManager
from app.services.mock_simulator import MockSimulator
from app.services import connections as connections_module
from app.services.rosbridge import RosSessionFactory
from app.services.virtual_tasks import VirtualTaskSimulator
from app.ws.telemetry import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    simulator: MockSimulator | None = None
    task_simulator = VirtualTaskSimulator(
        step_sec=settings.virtual_task_step_sec,
        tick_sec=settings.virtual_task_tick_sec,
    )
    manager = ConnectionManager(
        profile_path=settings.device_profiles_path,
        monitor_interval_sec=settings.serial_monitor_interval_sec,
        ros_session_factory=getattr(app.state, "ros_session_factory", None),
        ros_topic_state=settings.ros_topic_state,
        ros_connect_timeout_sec=settings.rosbridge_connect_timeout_sec,
        ros_first_message_timeout_sec=settings.rosbridge_first_message_timeout_sec,
        ros_stale_timeout_sec=settings.rosbridge_stale_timeout_sec,
        ros_watchdog_interval_sec=settings.rosbridge_watchdog_interval_sec,
        ros_reconnect_delays_sec=settings.rosbridge_reconnect_delays,
        dock_test_ip=settings.dock_test_ip,
        usv_relay_command_topic=settings.usv_relay_command_topic,
        usv_relay_confirmation_timeout_sec=settings.usv_relay_confirmation_timeout_sec,
    )
    connections_module.connection_manager = manager
    await manager.start()

    if settings.mock_simulator_enabled:
        simulator = MockSimulator(settings.mock_tick_interval_sec)
        simulator.start()
    task_simulator.start()

    app.state.simulator = simulator
    app.state.task_simulator = task_simulator
    app.state.connection_manager = manager
    app.state.rosbridge = manager
    try:
        yield
    finally:
        if simulator:
            await simulator.stop()
        await task_simulator.stop()
        await manager.stop()
        connections_module.connection_manager = None


def create_app(*, ros_session_factory: RosSessionFactory | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.ros_session_factory = ros_session_factory
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(ws_router)
    return app


app = create_app()
