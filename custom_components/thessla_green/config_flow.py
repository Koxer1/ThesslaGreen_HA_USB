import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_DEVICE,
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_STOPBITS,
    CONF_BYTESIZE,
    CONF_SLAVE,
    CONF_SCAN_INTERVAL,
    DEFAULT_DEVICE,
    DEFAULT_BAUDRATE,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    DEFAULT_BYTESIZE,
    DEFAULT_SLAVE,
    DEFAULT_SCAN_INTERVAL,
    BAUDRATE_OPTIONS,
    PARITY_OPTIONS,
    STOPBITS_OPTIONS,
    BYTESIZE_OPTIONS,
)


class ThesslaGreenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Thessla Green (USB / Modbus RTU)."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            # Unikalne ID = sciezka urzadzenia + slave (zeby ten sam port nie byl
            # podpiety dwa razy do tej samej Theslli przez przypadek).
            unique_id = f"{user_input[CONF_DEVICE]}::{user_input[CONF_SLAVE]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Thessla Green ({user_input[CONF_DEVICE]})",
                data=user_input,
            )

        schema = vol.Schema({
            vol.Required(CONF_DEVICE, default=DEFAULT_DEVICE): str,
            vol.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE):
                vol.In(BAUDRATE_OPTIONS),
            vol.Required(CONF_PARITY, default=DEFAULT_PARITY):
                vol.In(PARITY_OPTIONS),
            vol.Required(CONF_STOPBITS, default=DEFAULT_STOPBITS):
                vol.In(STOPBITS_OPTIONS),
            vol.Required(CONF_BYTESIZE, default=DEFAULT_BYTESIZE):
                vol.In(BYTESIZE_OPTIONS),
            vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE):
                vol.All(int, vol.Range(min=1, max=247)),
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
                vol.All(int, vol.Range(min=5, max=600)),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Link to options flow handler."""
        from .options_flow import ThesslaGreenOptionsFlowHandler
        return ThesslaGreenOptionsFlowHandler(config_entry)