"""Smart home control skills for MARS using Home Assistant and MQTT."""

import os
from typing import Any


def _ha_headers() -> dict[str, str]:
    """Build Home Assistant authorization headers from environment."""
    token = os.environ.get("HOME_ASSISTANT_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _ha_url(endpoint: str = "") -> str:
    """Construct a Home Assistant API URL."""
    base = os.environ.get("HOME_ASSISTANT_URL", "http://homeassistant.local:8123").rstrip("/")
    return f"{base}/api{endpoint}"


def _check_config() -> str | None:
    """Return an error message if HA config is missing, else None."""
    if not os.environ.get("HOME_ASSISTANT_URL"):
        return "HOME_ASSISTANT_URL environment variable is not set."
    if not os.environ.get("HOME_ASSISTANT_TOKEN"):
        return "HOME_ASSISTANT_TOKEN environment variable is not set."
    return None


def get_home_states() -> str:
    """Retrieve all entity states from Home Assistant.

    Returns:
        A formatted summary of home entity states.
    """
    err = _check_config()
    if err:
        return err

    try:
        import requests

        response = requests.get(_ha_url("/states"), headers=_ha_headers(), timeout=10)
        if response.status_code != 200:
            return f"Home Assistant returned status {response.status_code}: {response.text[:200]}"

        states: list[dict[str, Any]] = response.json()
        if not states:
            return "No entities found in Home Assistant."

        lines: list[str] = []
        for entity in states[:30]:
            eid = entity.get("entity_id", "unknown")
            state = entity.get("state", "unknown")
            lines.append(f"{eid}: {state}")

        extra = f"\n...and {len(states) - 30} more entities." if len(states) > 30 else ""
        return f"Home states ({len(states)} entities):\n" + "\n".join(lines) + extra
    except Exception as e:
        return f"Failed to get home states: {e}"


def control_light(entity_id: str, action: str) -> str:
    """Turn a light on, off, or toggle it.

    Args:
        entity_id: Home Assistant entity ID (e.g., 'light.living_room').
        action: One of 'on', 'off', or 'toggle'.

    Returns:
        Result of the action as a string.
    """
    err = _check_config()
    if err:
        return err

    action = action.lower().strip()
    if action not in ("on", "off", "toggle"):
        return f"Invalid action '{action}'. Use 'on', 'off', or 'toggle'."

    service = f"turn_{action}" if action != "toggle" else "toggle"
    return control_device(entity_id, action)


def control_device(entity_id: str, action: str) -> str:
    """Control any Home Assistant entity.

    Args:
        entity_id: Home Assistant entity ID (e.g., 'switch.kitchen', 'light.bedroom').
        action: One of 'on', 'off', or 'toggle'.

    Returns:
        Result of the action as a string.
    """
    err = _check_config()
    if err:
        return err

    action = action.lower().strip()
    if action not in ("on", "off", "toggle"):
        return f"Invalid action '{action}'. Use 'on', 'off', or 'toggle'."

    domain = entity_id.split(".")[0] if "." in entity_id else "homeassistant"
    service = "toggle" if action == "toggle" else f"turn_{action}"
    url = _ha_url(f"/services/{domain}/{service}")

    try:
        import requests

        response = requests.post(
            url,
            headers=_ha_headers(),
            json={"entity_id": entity_id},
            timeout=10,
        )
        if response.status_code in (200, 201):
            return f"Successfully sent '{action}' to '{entity_id}'."
        return f"Home Assistant returned status {response.status_code}: {response.text[:200]}"
    except Exception as e:
        return f"Failed to control device: {e}"


def get_sensor_data(entity_id: str) -> str:
    """Read the current state/value of a Home Assistant sensor.

    Args:
        entity_id: Home Assistant sensor entity ID (e.g., 'sensor.temperature').

    Returns:
        Sensor value and attributes as a string.
    """
    err = _check_config()
    if err:
        return err

    try:
        import requests

        response = requests.get(
            _ha_url(f"/states/{entity_id}"), headers=_ha_headers(), timeout=10
        )
        if response.status_code == 404:
            return f"Entity '{entity_id}' not found in Home Assistant."
        if response.status_code != 200:
            return f"Home Assistant returned status {response.status_code}."

        data = response.json()
        state = data.get("state", "unknown")
        attrs: dict[str, Any] = data.get("attributes", {})
        unit = attrs.get("unit_of_measurement", "")
        friendly_name = attrs.get("friendly_name", entity_id)
        last_changed = data.get("last_changed", "")[:19].replace("T", " ")

        lines = [f"{friendly_name}: {state}{' ' + unit if unit else ''}"]
        if last_changed:
            lines.append(f"Last updated: {last_changed}")
        for k, v in list(attrs.items())[:5]:
            if k not in ("unit_of_measurement", "friendly_name", "icon"):
                lines.append(f"  {k}: {v}")

        return "\n".join(lines)
    except Exception as e:
        return f"Failed to get sensor data: {e}"


def publish_mqtt(topic: str, message: str) -> str:
    """Publish a message to an MQTT topic.

    Requires MQTT_BROKER (host), and optionally MQTT_PORT, MQTT_USERNAME,
    MQTT_PASSWORD environment variables.

    Args:
        topic: MQTT topic to publish to.
        message: Message payload.

    Returns:
        Confirmation or error message.
    """
    broker = os.environ.get("MQTT_BROKER", "")
    if not broker:
        return "MQTT_BROKER environment variable is not set."

    port = int(os.environ.get("MQTT_PORT", "1883"))
    username = os.environ.get("MQTT_USERNAME", "")
    password = os.environ.get("MQTT_PASSWORD", "")

    try:
        import paho.mqtt.publish as publish  # type: ignore

        auth = {"username": username, "password": password} if username else None
        publish.single(
            topic,
            payload=message,
            hostname=broker,
            port=port,
            auth=auth,
        )
        return f"Published to '{topic}': {message}"
    except ImportError:
        return "paho-mqtt is not installed. Run: pip install paho-mqtt"
    except Exception as e:
        return f"MQTT publish failed: {e}"
