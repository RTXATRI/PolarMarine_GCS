from fastapi import APIRouter, HTTPException

from app.models.schemas import Alarm, LogEntry
from app.services.state import state_service

router = APIRouter()


@router.get("/logs", response_model=list[LogEntry])
def list_logs() -> list[LogEntry]:
    return state_service.list_logs()


@router.post("/logs/clear", response_model=LogEntry)
def clear_logs() -> LogEntry:
    return state_service.clear_logs()


@router.get("/alarms", response_model=list[Alarm])
def list_alarms() -> list[Alarm]:
    return state_service.list_alarms()


@router.post("/alarms/{alarm_id}/ack", response_model=Alarm)
def ack_alarm(alarm_id: int) -> Alarm:
    alarm = state_service.ack_alarm(alarm_id)
    if not alarm:
        raise HTTPException(status_code=404, detail="alarm not found")
    return alarm
