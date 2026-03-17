"""Config flow for the NATS integration."""

from __future__ import annotations

import logging
import ssl
from typing import Any

import nats
import nats.errors
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_SSL, CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SSL, default=True): bool,
    }
)


async def validate_input(data: dict[str, Any]) -> None:
    """Validate the user input by connecting to the NATS broker."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    use_tls = data[CONF_SSL]
    scheme = "tls" if use_tls else "nats"
    tls_context = ssl.create_default_context() if use_tls else None

    try:
        nc = await nats.connect(
            servers=[f"{scheme}://{host}:{port}"],
            user=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
            connect_timeout=5,
            tls=tls_context,
        )
    except nats.errors.NoServersError as err:
        raise CannotConnect from err
    except nats.errors.AuthorizationError as err:
        raise InvalidAuth from err
    except Exception as err:
        if "Authorization" in str(err):
            raise InvalidAuth from err
        raise
    else:
        await nc.close()


class NatsIoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NATS."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                host = user_input[CONF_HOST]
                port = user_input[CONF_PORT]
                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=host, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
