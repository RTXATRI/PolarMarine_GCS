from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.models.schemas import NetworkConnectionProfile, RosTelemetryData
from app.services.state import StateService
from tests.conftest import FakeRosbridgeFactory, make_ros_envelope


ROBOT_ID = 'CL-USV'
PROFILE = {'method': 'network', 'host': '192.168.1.249', 'port': 9090}


def wait_for_relay(client: TestClient, expected: bool | None) -> dict:
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        robot = client.get(f'/api/robots/{ROBOT_ID}').json()
        if robot['relayEnabled'] is expected:
            return robot
        time.sleep(0.01)
    raise AssertionError(f'relayEnabled did not become {expected!r}')


def test_live_telemetry_maps_relay_only_for_cl_usv(
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> None:
    fake_rosbridge_factory.configure(
        '192.168.1.249',
        9090,
        make_ros_envelope(ROBOT_ID, relayEnabled=False),
    )

    with TestClient(create_app()) as client:
        connected = client.post(f'/api/robots/{ROBOT_ID}/connection', json=PROFILE)
        assert connected.status_code == 200
        assert connected.json()['relayEnabled'] is False

        session = fake_rosbridge_factory.sessions[0]
        session.emit_envelope(make_ros_envelope(ROBOT_ID, relayEnabled=True))
        assert wait_for_relay(client, True)['relayEnabled'] is True

        session.emit_envelope(make_ros_envelope(ROBOT_ID))
        assert wait_for_relay(client, None)['connection']['state'] == 'connected'

    state = StateService()
    profile = NetworkConnectionProfile(method='network', host='192.168.1.250', port=9090)
    state.mark_connected('MricoCV-USV', profile, 'live', 'virtual')
    state.apply_live_telemetry(
        'MricoCV-USV',
        RosTelemetryData(sourceConnected=True, relayEnabled=True),
    )
    assert state.get_robot('MricoCV-USV').relayEnabled is None


def test_electromagnetic_fix_waits_for_matching_telemetry(
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> None:
    fake_rosbridge_factory.configure(
        '192.168.1.249',
        9090,
        make_ros_envelope(ROBOT_ID, relayEnabled=False),
    )

    with TestClient(create_app()) as client:
        assert client.post(f'/api/robots/{ROBOT_ID}/connection', json=PROFILE).status_code == 200
        session = fake_rosbridge_factory.sessions[0]
        session.on_publish_bool = lambda _topic, enabled: session.emit_envelope(
            make_ros_envelope(ROBOT_ID, relayEnabled=enabled)
        )

        enabled = client.post(
            '/api/commands/electromagnetic-fix',
            json={'robotId': ROBOT_ID, 'enabled': True},
        )
        disabled = client.post(
            '/api/commands/electromagnetic-fix',
            json={'robotId': ROBOT_ID, 'enabled': False},
        )

        assert enabled.status_code == 200
        assert enabled.json()['relayEnabled'] is True
        assert disabled.status_code == 200
        assert disabled.json()['relayEnabled'] is False
        assert session.published_bools == [
            ('/usv_std/relay/set_enabled', True),
            ('/usv_std/relay/set_enabled', False),
        ]


def test_electromagnetic_fix_rejects_unknown_state_and_other_devices(
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> None:
    fake_rosbridge_factory.configure(
        '192.168.1.249',
        9090,
        make_ros_envelope(ROBOT_ID),
    )

    with TestClient(create_app()) as client:
        assert client.post(f'/api/robots/{ROBOT_ID}/connection', json=PROFILE).status_code == 200
        unavailable = client.post(
            '/api/commands/electromagnetic-fix',
            json={'robotId': ROBOT_ID, 'enabled': True},
        )
        unsupported = client.post(
            '/api/commands/electromagnetic-fix',
            json={'robotId': 'Hexa-UAV', 'enabled': True},
        )

        assert unavailable.status_code == 409
        assert unavailable.json()['detail']['code'] == 'RELAY_STATE_UNAVAILABLE'
        assert fake_rosbridge_factory.sessions[0].published_bools == []
        assert unsupported.status_code == 409
        assert unsupported.json()['detail']['code'] == 'ACTION_NOT_SUPPORTED'


def test_electromagnetic_fix_reports_publish_failure(
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> None:
    fake_rosbridge_factory.configure(
        '192.168.1.249',
        9090,
        make_ros_envelope(ROBOT_ID, relayEnabled=False),
    )

    with TestClient(create_app()) as client:
        assert client.post(f'/api/robots/{ROBOT_ID}/connection', json=PROFILE).status_code == 200
        fake_rosbridge_factory.sessions[0].publish_error = RuntimeError('publish denied')
        response = client.post(
            '/api/commands/electromagnetic-fix',
            json={'robotId': ROBOT_ID, 'enabled': True},
        )

        assert response.status_code == 502
        assert response.json()['detail']['code'] == 'RELAY_COMMAND_PUBLISH_FAILED'
        assert client.get(f'/api/robots/{ROBOT_ID}').json()['relayEnabled'] is False


def test_electromagnetic_fix_cancels_confirmation_when_session_drops(
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> None:
    fake_rosbridge_factory.configure(
        '192.168.1.249',
        9090,
        make_ros_envelope(ROBOT_ID, relayEnabled=False),
    )

    with TestClient(create_app()) as client:
        assert client.post(f'/api/robots/{ROBOT_ID}/connection', json=PROFILE).status_code == 200
        session = fake_rosbridge_factory.sessions[0]
        session.on_publish_bool = lambda _topic, _enabled: session.drop('relay test drop')

        response = client.post(
            '/api/commands/electromagnetic-fix',
            json={'robotId': ROBOT_ID, 'enabled': True},
        )

        assert response.status_code == 409
        assert response.json()['detail']['code'] == 'DEVICE_NOT_CONNECTED'
        assert session.published_bools == [('/usv_std/relay/set_enabled', True)]


def test_electromagnetic_fix_keeps_state_when_confirmation_times_out(
    monkeypatch,
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> None:
    monkeypatch.setenv('USV_RELAY_CONFIRMATION_TIMEOUT_SEC', '0.1')
    get_settings.cache_clear()
    fake_rosbridge_factory.configure(
        '192.168.1.249',
        9090,
        make_ros_envelope(ROBOT_ID, relayEnabled=False),
    )

    with TestClient(create_app()) as client:
        assert client.post(f'/api/robots/{ROBOT_ID}/connection', json=PROFILE).status_code == 200
        response = client.post(
            '/api/commands/electromagnetic-fix',
            json={'robotId': ROBOT_ID, 'enabled': True},
        )

        assert response.status_code == 504
        assert response.json()['detail']['code'] == 'RELAY_CONFIRMATION_TIMEOUT'
        assert fake_rosbridge_factory.sessions[0].published_bools == [
            ('/usv_std/relay/set_enabled', True)
        ]
        assert client.get(f'/api/robots/{ROBOT_ID}').json()['relayEnabled'] is False
