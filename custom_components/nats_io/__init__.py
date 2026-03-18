"""The NATS integration."""

from __future__ import annotations

import json
import logging
import ssl
from datetime import UTC, datetime
from typing import Any

import nats
from nats.aio.client import Client as NatsClient
from nats.aio.msg import Msg as NatsMsg

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    EVENT_STATE_CHANGED,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

_LOGGER = logging.getLogger(__name__)

type NatsIoConfigEntry = ConfigEntry[NatsClient]


async def async_setup_entry(hass: HomeAssistant, entry: NatsIoConfigEntry) -> bool:
    """Set up NATS from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    use_tls = entry.data[CONF_SSL]
    scheme = "tls" if use_tls else "nats"
    tls_context = ssl.create_default_context() if use_tls else None

    async def _error_cb(err: Exception) -> None:
        _LOGGER.warning("NATS connection error: %s", err)

    async def _disconnected_cb() -> None:
        _LOGGER.warning("Disconnected from NATS broker at %s:%s", host, port)

    async def _reconnected_cb() -> None:
        _LOGGER.info("Reconnected to NATS broker at %s:%s", host, port)

    try:
        nc = await nats.connect(
            servers=[f"{scheme}://{host}:{port}"],
            user=username,
            password=password,
            tls=tls_context,
            error_cb=_error_cb,
            disconnected_cb=_disconnected_cb,
            reconnected_cb=_reconnected_cb,
        )
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Cannot connect to NATS broker at {host}:{port}"
        ) from err

    entry.runtime_data = nc

    async def _async_service_command_handler(msg: NatsMsg) -> None:
        """Handle incoming NATS messages and call the corresponding HA service.

        Expected subject: ha.service
        Expected payload: JSON object with required "action" key (<domain>.<service>)
        and optional "target" and "data" keys,
        e.g. {"action": "light.turn_on", "target": {"entity_id": "light.living_room"}, "data": {"brightness": 128}}
        """
        try:
            payload: dict[str, Any] = json.loads(msg.data.decode()) if msg.data else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            _LOGGER.warning(
                "Failed to decode NATS message payload on subject %s", msg.subject
            )
            return

        action: str = payload.get("action", "")
        action_parts = action.split(".", 1)
        if len(action_parts) != 2:
            _LOGGER.warning(
                "Received service command with missing or invalid 'action' field: %r", action
            )
            return

        domain, service = action_parts

        if not hass.services.has_service(domain, service):
            _LOGGER.warning(
                "Received command for unknown service %s.%s", domain, service
            )
            return

        target: dict[str, Any] | None = payload.get("target")
        service_data: dict[str, Any] | None = payload.get("data")

        _LOGGER.debug(
            "Calling service %s.%s target=%s data=%s from NATS",
            domain,
            service,
            target,
            service_data,
        )
        await hass.services.async_call(domain, service, service_data, target=target)

    await nc.subscribe("ha.service", cb=_async_service_command_handler)

    def _build_state_payload(entity_id: str) -> dict[str, Any] | None:
        """Build the state payload for an entity, or return None if not found."""
        state = hass.states.get(entity_id)
        if state is None:
            return None

        area_id: str | None = None
        device_id: str | None = None
        entity_entry = er.async_get(hass).async_get(entity_id)
        if entity_entry:
            area_id = entity_entry.area_id
            device_id = entity_entry.device_id
            if area_id is None and device_id:
                device = dr.async_get(hass).async_get(device_id)
                if device:
                    area_id = device.area_id

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "entity_id": state.entity_id,
            "device_id": device_id,
            "area_id": area_id,
            "state": state.state,
            "attributes": dict(state.attributes),
            "last_changed": state.last_changed.isoformat(),
        }

    async def _async_state_request_handler(msg: NatsMsg) -> None:
        """Handle incoming state requests on ha.request.state.

        Expected payload: JSON object with required "entity_id" key,
        e.g. {"entity_id": "light.living_room"}
        Response payload mirrors the ha.state.* publish format.
        """
        if not msg.reply:
            _LOGGER.warning("Received ha.request.state message without a reply subject")
            return

        try:
            payload: dict[str, Any] = json.loads(msg.data.decode()) if msg.data else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            _LOGGER.warning(
                "Failed to decode NATS message payload on subject %s", msg.subject
            )
            return

        entity_id: str = payload.get("entity_id", "")
        if not entity_id:
            _LOGGER.warning("Received ha.request.state message without 'entity_id'")
            return

        state_payload = _build_state_payload(entity_id)
        if state_payload is None:
            response: dict[str, Any] = {"error": f"Entity {entity_id!r} not found"}
        else:
            response = state_payload

        try:
            await nc.publish(msg.reply, json.dumps(response).encode())
        except Exception as err:
            _LOGGER.warning("Failed to publish state response to NATS: %s", err)

    await nc.subscribe("ha.request.state", cb=_async_state_request_handler)

    async def _async_state_changed_listener(event: Event[EventStateChangedData]) -> None:
        """Publish state changes to NATS."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        state_payload = _build_state_payload(new_state.entity_id)
        if state_payload is None:
            return

        subject = f"ha.state.{state_payload['area_id'] or 'no_area'}.{new_state.entity_id}"
        payload = state_payload

        try:
            await nc.publish(subject, json.dumps(payload).encode())
        except Exception as err:
            _LOGGER.warning("Failed to publish state change to NATS: %s", err)

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_STATE_CHANGED, _async_state_changed_listener)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NatsIoConfigEntry) -> bool:
    """Unload a NATS config entry."""
    await entry.runtime_data.drain()
    return True
