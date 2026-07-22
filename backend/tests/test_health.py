from fastapi.testclient import TestClient

from app.main import create_app


def test_health() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert "rosbridgeConnected" in payload


def test_robot_and_parameter_endpoints() -> None:
    with TestClient(create_app()) as client:
        robots = client.get("/api/robots")
        assert robots.status_code == 200
        assert len(robots.json()) == 5

        disconnected = client.get("/api/parameters", params={"robotId": "Hexa-UAV"})
        assert disconnected.status_code == 409
        assert disconnected.json()["detail"]["code"] == "DEVICE_NOT_CONNECTED"

        connected = client.post(
            "/api/robots/Hexa-UAV/connection",
            json={"method": "network", "host": "192.0.2.10", "port": 9090},
        )
        assert connected.status_code == 200

        parameters = client.get("/api/parameters", params={"robotId": "Hexa-UAV"})
        assert parameters.status_code == 200
        assert len(parameters.json()) == 6


def test_telemetry_websocket_initial_snapshot() -> None:
    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws/telemetry") as websocket:
            message = websocket.receive_json()
            assert message["type"] == "robot_state"
            assert len(message["data"]) == 5
