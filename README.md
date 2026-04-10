# NATS Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Connects Home Assistant to a [NATS](https://nats.io) message broker, enabling bidirectional communication between Home Assistant and external systems.

- **State changes** are published to NATS so external systems can react to what happens in Home Assistant.
- **Service calls** can be triggered from NATS to control Home Assistant devices and automations.
- **State requests** can be made from NATS to query the current state of any entity on demand.

## Prerequisites

A running NATS broker (version 2.x or later) accessible from your Home Assistant instance. Authentication via username/password is required. TLS is supported and enabled by default.

> [!CAUTION]
> This integration allows anyone with access to the `ha.>` topics on the NATS broker to read and modify entity states in Home Assistant. You are responsible for properly securing your NATS broker.

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=acc0j&repository=home-assistant-nats)

1. Open HACS in Home Assistant.
2. Go to **Integrations** → **⋮** → **Custom repositories**.
3. Add `https://github.com/acc0j/home-assistant-nats` with category **Integration**.
4. Search for **NATS** and install it.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/nats_io` directory into your `<config>/custom_components/` folder.
2. Restart Home Assistant.

## Configuration

Go to **Settings** → **Devices & Services** → **Add Integration** and search for **NATS**.

| Field    | Description                                      | Default |
|----------|--------------------------------------------------|---------|
| Host     | Hostname or IP address of the NATS broker        | —       |
| Port     | Port number of the NATS broker                   | `4222`  |
| Username | Username for authenticating with the NATS broker | —       |
| Password | Password for authenticating with the NATS broker | —       |
| SSL      | Enable TLS encryption                            | `true`  |

## How it works

### State publishing

Every time a Home Assistant entity changes state, the integration publishes a message to NATS.

**Subject:** `ha.state.<area_id>.<entity_id>`

- `<area_id>` is the area the entity belongs to (via its device if not set directly). Falls back to `no_area` when no area is assigned.
- `<entity_id>` is the Home Assistant entity ID as-is (e.g. `light.living_room`).

**Payload:**

```json
{
  "timestamp": "2024-01-15T12:34:56.789012+00:00",
  "entity_id": "light.living_room",
  "device_id": "a1b2c3d4e5f6",
  "area_id": "living_room",
  "state": "on",
  "attributes": {
    "brightness": 128,
    "friendly_name": "Living Room Light"
  },
  "last_changed": "2024-01-15T12:34:56.789012+00:00"
}
```

**Wildcard examples:**

| Pattern                        | Matches                                    |
|--------------------------------|--------------------------------------------|
| `ha.state.>`                   | All state changes                          |
| `ha.state.living_room.>`       | All entities in the living room area       |
| `ha.state.*.light.living_room` | A specific entity across all areas         |
| `ha.state.no_area.>`           | All entities without an area assigned      |

### Service calls

Publish a message to `ha.service` to trigger any Home Assistant service.

**Subject:** `ha.service`

**Payload:**

```json
{
  "action": "<domain>.<service>",
  "target": { "entity_id": "light.living_room" },
  "data": { "brightness": 128 }
}
```

| Field    | Required | Description                                                 |
|----------|----------|-------------------------------------------------------------|
| `action` | Yes      | Service to call in `<domain>.<service>` format              |
| `target` | No       | [Target](https://www.home-assistant.io/docs/scripts/service-calls/#targeting-areas-and-devices) — entity, device, or area IDs |
| `data`   | No       | Service-specific parameters                                 |

**Examples:**

Turn on a light at 50% brightness:
```json
{
  "action": "light.turn_on",
  "target": { "entity_id": "light.living_room" },
  "data": { "brightness_pct": 50 }
}
```

Trigger an automation:
```json
{
  "action": "automation.trigger",
  "target": { "entity_id": "automation.good_morning" }
}
```

Send a notification:
```json
{
  "action": "notify.mobile_app_my_phone",
  "data": { "message": "Hello from NATS!" }
}
```

### State requests

Request the current state of any entity by publishing to `ha.request.state` with a reply subject set. The integration responds directly to the reply subject.

**Subject:** `ha.request.state`

**Request payload:**

```json
{
  "entity_id": "light.living_room"
}
```

**Response payload** (same fields as a state change event):

```json
{
  "timestamp": "2024-01-15T12:34:56.789012+00:00",
  "entity_id": "light.living_room",
  "device_id": "a1b2c3d4e5f6",
  "area_id": "living_room",
  "state": "on",
  "attributes": {
    "brightness": 128,
    "friendly_name": "Living Room Light"
  },
  "last_changed": "2024-01-15T12:34:56.789012+00:00"
}
```

If the entity is not found, the response is:

```json
{
  "error": "Entity 'light.unknown' not found"
}
```

> **Note:** The message must include a reply subject (NATS request/reply pattern). Messages without a reply subject are ignored.

## Troubleshooting

- **Cannot connect** — verify the broker host, port, and that it is reachable from Home Assistant. Check if TLS is correctly configured on both sides.
- **Invalid auth** — confirm the username and password against your NATS broker configuration.
- **Messages not received** — enable debug logging for `custom_components.nats_io` in `configuration.yaml`:

  ```yaml
  logger:
    logs:
      custom_components.nats_io: debug
  ```
