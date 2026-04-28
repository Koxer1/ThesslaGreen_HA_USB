from __future__ import annotations
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from . import DOMAIN
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)

# Alarmy filtrow w AirPack4 - rejestry 8332-8351 (E140-E157)
# Wszystkie z device_class="problem" (czerwone w UI gdy on)
BINARY_SENSORS = [
    # Odczyt z COILS
    {"name": "Rekuperator Silownik bypassu", "address": 9, "input_type": "coil", "icon_on": "mdi:valve-open", "icon_off": "mdi:valve-closed"},
    {"name": "Rekuperator Potwierdzenie pracy", "address": 11, "input_type": "coil", "icon_on": "mdi:check-circle", "icon_off": "mdi:circle-outline"},

    # Odczyt z HOLDING REGISTERS - alarmy ogolne
    {"name": "Rekuperator Alarm", "address": 8192, "input_type": "holding", "device_class": "problem"},
    {"name": "Rekuperator Error", "address": 8193, "input_type": "holding", "device_class": "problem"},
    {"name": "Rekuperator FPX zabezpieczenie termiczne", "address": 8208, "input_type": "holding", "device_class": "safety"},
    {"name": "Rekuperator Awaria Wentylatora Nawiewu", "address": 8222, "input_type": "holding", "device_class": "problem"},
    {"name": "Rekuperator Awaria Wentylatora Wywiewu", "address": 8223, "input_type": "holding", "device_class": "problem"},
    {"name": "Rekuperator Awaria CF Nawiewu", "address": 8330, "input_type": "holding", "device_class": "problem"},
    {"name": "Rekuperator Awaria CF Wywiewu", "address": 8331, "input_type": "holding", "device_class": "problem"},

    # NOWE v0.4.1: alarmy filtrow (AirPack4)
    {"name": "Rekuperator Awaria CF filtra nawiewnego", "address": 8332, "input_type": "holding", "device_class": "problem"},
    {"name": "Rekuperator Awaria CF filtra wywiewnego", "address": 8333, "input_type": "holding", "device_class": "problem"},
    {"name": "Rekuperator Brak filtra nawiewnego", "address": 8334, "input_type": "holding", "device_class": "problem"},
    {"name": "Rekuperator Brak filtra wywiewnego", "address": 8335, "input_type": "holding", "device_class": "problem"},
    {"name": "Rekuperator Blad przeplywu nawiew", "address": 8336, "input_type": "holding", "device_class": "problem"},
    {"name": "Rekuperator Blad przeplywu wywiew", "address": 8337, "input_type": "holding", "device_class": "problem"},
    {"name": "Rekuperator Wymiana filtra nawiewnego", "address": 8338, "input_type": "holding", "icon_on": "mdi:air-filter", "icon_off": "mdi:fan"},
    {"name": "Rekuperator Wymiana filtra wywiewnego", "address": 8339, "input_type": "holding", "icon_on": "mdi:air-filter", "icon_off": "mdi:fan"},
    {"name": "Rekuperator Zuzycie filtra nawiewnego krytyczne", "address": 8340, "input_type": "holding", "device_class": "problem"},
    {"name": "Rekuperator Zuzycie filtra wywiewnego krytyczne", "address": 8341, "input_type": "holding", "device_class": "problem"},
    {"name": "Rekuperator Wymiana filtra nawiewnego (E150)", "address": 8342, "input_type": "holding", "icon_on": "mdi:air-filter", "icon_off": "mdi:fan"},
    {"name": "Rekuperator Wymiana filtra wywiewnego (E151)", "address": 8343, "input_type": "holding", "icon_on": "mdi:air-filter", "icon_off": "mdi:fan"},
    {"name": "Rekuperator Czas filtra nawiewnego przekroczony", "address": 8348, "input_type": "holding", "device_class": "problem"},
    {"name": "Rekuperator Czas filtra wywiewnego przekroczony", "address": 8349, "input_type": "holding", "device_class": "problem"},

    # BYPASS: tutaj wartość 0 oznacza "ON" (otwarty) – odwracamy logikę przez on_value=0
    {"name": "Rekuperator Bypass", "address": 4320, "input_type": "holding", "on_value": 0, "icon_on": "mdi:valve-open", "icon_off": "mdi:valve-closed"},

    {"name": "Rekuperator fpx flaga", "address": 4192, "input_type": "holding", "icon_on": "mdi:flag", "icon_off": "mdi:flag-outline"},
    {"name": "Rekuperator FPX tryb", "address": 4198, "input_type": "holding", "icon_on": "mdi:fan-alert", "icon_off": "mdi:fan"},
    {"name": "Rekuperator lato zima", "address": 4209, "input_type": "holding", "icon_on": "mdi:sun-thermometer", "icon_off": "mdi:snowflake"},
    {"name": "Rekuperator Wymiana Filtrów", "address": 8444, "input_type": "holding", "icon_on": "mdi:air-filter", "icon_off": "mdi:fan-alert"},
    {"name": "Rekuperator Status ERV", "address": 4704, "input_type": "holding", "on_value": 0, "icon_on": "mdi:radiator", "icon_off": "mdi:radiator-off"},
]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    modbus_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: ThesslaGreenCoordinator = modbus_data["coordinator"]
    slave = modbus_data["slave"]

    entities = [
        ModbusBinarySensor(coordinator=coordinator, slave=slave, **sensor)
        for sensor in BINARY_SENSORS
    ]

    async_add_entities(entities)


class ModbusBinarySensor(BinarySensorEntity):
    """Representation of a Modbus binary sensor."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        name: str,
        address: int,
        input_type: str = "coil",
        slave: int = 1,
        device_class: str | None = None,
        icon_on: str | None = None,
        icon_off: str | None = None,
        on_value: int | None = None,
    ):
        self.coordinator = coordinator
        self._attr_name = name
        self._address = address
        self._input_type = input_type
        self._slave = slave
        self._icon_on = icon_on
        self._icon_off = icon_off

        # Jeśli nie podano, przyjmij standard: 1 = ON
        self._on_value = 1 if on_value is None else on_value

        self._attr_unique_id = f"thessla_binary_sensor_{slave}_{address}"
        self._attr_device_class = device_class

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{slave}")},
            "name": "Rekuperator Thessla",
            "manufacturer": "Thessla Green",
            "model": "Modbus Rekuperator",
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self._input_type == "coil":
            val = self.coordinator.safe_data.coil.get(self._address)
            if val is None:
                return None
            try:
                return int(bool(val)) == self._on_value
            except Exception:
                return bool(val)

        elif self._input_type == "holding":
            value = self.coordinator.safe_data.holding.get(self._address)
            if value is None:
                return None
            return value == self._on_value

        _LOGGER.error("Unknown input_type '%s' for %s", self._input_type, self._attr_name)
        return None

    @property
    def icon(self) -> str | None:
        """Return the icon to use."""
        if self.is_on is None:
            return None
        return self._icon_on if self.is_on else self._icon_off

    async def async_update(self):
        """No manual polling needed — coordinator handles data updates."""
        pass

    async def async_added_to_hass(self):
        """Register entity with coordinator updates."""
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))