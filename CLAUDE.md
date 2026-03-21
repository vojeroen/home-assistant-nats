# CLAUDE.md

## Project overview

This is a Home Assistant custom integration (`nats_io`) that bridges Home Assistant with a NATS message broker. It publishes all HA state changes to NATS and subscribes to `ha.service` to receive service call commands from external systems.

**Key files:**
- `custom_components/nats_io/__init__.py` — setup/teardown, NATS subscription, state publisher
- `custom_components/nats_io/config_flow.py` — UI config flow and connection validation
- `custom_components/nats_io/const.py` — domain and default port constants
- `custom_components/nats_io/manifest.json` — integration metadata and pip requirements
- `custom_components/nats_io/strings.json` — UI strings (source of truth; translations derive from this)
- `custom_components/nats_io/translations/en.json` — English translations
- `tests/nats_io/conftest.py` — shared test fixtures
- `tests/nats_io/test_config_flow.py` — config flow tests

## Development

**Run tests:**
```bash
pytest tests/
```

Tests use `pytest-asyncio` in auto mode (`asyncio_mode = auto` in `pytest.ini`). Mock `nats.connect` via `unittest.mock.patch` — do not hit a real broker in tests.

**Deploy to HA instance:**
```bash
bash deploy.sh
```
This rsync's `custom_components/nats_io/` to the configured HA host. The target host is set in `deploy.sh`.

## NATS message contracts

### State publishing
- **Subject:** `ha.state.<area_id>.<entity_id>`
  - `<area_id>`: area slug, or `no_area` if unassigned
  - `<entity_id>`: the Home Assistant entity ID as-is (e.g. `light.living_room`)
- **Payload fields:** `timestamp`, `entity_id`, `device_id`, `area_id`, `state`, `attributes`, `last_changed`

### Service commands
- **Subject:** `ha.service`
- **Payload:** `{ "action": "<domain>.<service>", "target": {...}, "data": {...} }`
  - `action` is required; `target` and `data` are optional

### State requests
- **Subject:** `ha.request.state`
- **Request payload:** `{ "entity_id": "<entity_id>" }` — `entity_id` is required
- **Response payload:** same fields as a state change event (`timestamp`, `entity_id`, `device_id`, `area_id`, `state`, `attributes`, `last_changed`), or `{ "error": "..." }` if the entity is not found
- Requires a NATS reply subject; messages without one are ignored

**If the subject format or payload schema changes, update `README.md` accordingly.**

## Code conventions

Follow standard Home Assistant integration patterns:
- Use `entry.runtime_data` to store runtime objects (e.g. the NATS client).
- Register cleanup with `entry.async_on_unload(...)`.
- Use `ConfigEntryNotReady` when the broker is unreachable at setup time.
- Use `drain()` (not `close()`) to shut down the NATS connection gracefully.
- Keep imports ordered: stdlib → third-party → homeassistant → local.

## Versioning

Before every commit, bump the `version` field in `custom_components/nats_io/manifest.json` following [semver](https://semver.org/):
- **Patch** (`0.0.x`) — bug fixes, internal refactors with no behaviour change
- **Minor** (`0.x.0`) — new features or subjects, backwards-compatible
- **Major** (`x.0.0`) — breaking changes to message contracts or config

Propose the version increment and confirm with the user before committing. After the commit, attach a git tag in the format `vX.Y.Z` to that commit.

## README

`README.md` is rendered by HACS as the integration's store page (`"render_readme": true` in `hacs.json`). **Keep it up to date whenever you make changes that affect:**
- The NATS subject format or payload schema
- Config flow fields or their defaults
- Installation or setup steps
- Supported features or behavior
