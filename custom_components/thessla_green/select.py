from __future__ import annotations
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from . import DOMAIN
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)

# Tryb pracy AirPack (rejestr 0x1070 / 4208) - wg dokumentacji Thessla
TRYB_PRACY = {
    "Automatyczny": 0,  # rekuperator wybiera predkosc z harmonogramu LATO/ZIMA
    "Manualny": 1,      # slucha airFlowRateManual (rejestr 4210)
    "Chwilowy": 2,      # slucha airFlowRateTemporary (rejestr 4211)
}

# Funkcje specjalne (rejestr 0x1080 / 4224)
MODES = {
    "Brak trybu": 0,
    "Wietrzenie": 7,
    "Pusty Dom": 11,
    "Kominek": 2,
    "Okna": 10,
}

SEASONS = {
    "Lato": 0,
    "Zima": 1,
}

ERV_MODES = {
    "ERV nieaktywny": 0,
    "ERV tryb 1": 1,
    "ERV tryb 2": 2,
}

COMFORT_MODES = {
    "EKO": 0,
    "KOMFORT": 1,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities."""
    modbus_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: ThesslaGreenCoordinator = modbus_data["coordinator"]
    slave = modbus_data["slave"]

    async_add_entities([
        RekuperatorTrybPracySelect(coordinator=coordinator, slave=slave),
        RekuperatorTrybSelect(coordinator=coordinator, slave=slave),
        RekuperatorSezonSelect(coordinator=coordinator, slave=slave),
        RekuperatorErvTrybSelect(coordinator=coordinator, slave=slave),
        RekuperatorKomfortSelect(coordinator=coordinator, slave=slave),
    ])


class _BaseModbusSelect(SelectEntity):
    """Wspolna baza dla select-ow Modbus z prostym map: tekst -> wartosc rejestru."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        slave: int,
        address: int,
        name: str,
        unique_prefix: str,
        options_map: dict,
    ):
        self.coordinator = coordinator
        self._address = address
        self._slave = slave
        self._attr_name = name
        self._attr_options = list(options_map.keys())
        self._reverse_map = options_map
        self._value_map = {v: k for k, v in options_map.items()}
        self._attr_unique_id = f"thessla_{unique_prefix}_select_{slave}_{address}"

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
    def current_option(self) -> str | None:
        value = self.coordinator.safe_data.holding.get(self._address)
        if value is None:
            return None
        return self._value_map.get(value)

    async def async_select_option(self, option: str) -> None:
        try:
            code = self._reverse_map.get(option)
            if code is None:
                _LOGGER.error(f"Unknown option selected for {self._attr_name}: {option}")
                return

            success = await self.coordinator.controller.write_register(self._address, code)
            if success:
                await self.coordinator.async_request_refresh()
        except Exception as e:
            _LOGGER.exception(f"Exception during selection on {self._attr_name}: {e}")

    async def async_update(self):
        pass

    async def async_added_to_hass(self):
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))


class RekuperatorTrybPracySelect(_BaseModbusSelect):
    """Tryb pracy AirPack (Automatyczny/Manualny/Chwilowy) - rejestr 0x1070 / 4208."""

    def __init__(self, coordinator: ThesslaGreenCoordinator, slave: int):
        super().__init__(
            coordinator=coordinator,
            slave=slave,
            address=4208,
            name="Rekuperator Tryb pracy",
            unique_prefix="tryb_pracy",
            options_map=TRYB_PRACY,
        )
        self._attr_icon = "mdi:cog-transfer"


class RekuperatorTrybSelect(_BaseModbusSelect):
    """Funkcja specjalna (Okap/Kominek/Wietrzenie/...) - rejestr 0x1080 / 4224."""

    def __init__(self, coordinator: ThesslaGreenCoordinator, slave: int):
        super().__init__(
            coordinator=coordinator,
            slave=slave,
            address=4224,
            name="Rekuperator Tryb",
            unique_prefix="",  # zachowuje stary unique_id dla kompatybilnosci
            options_map=MODES,
        )
        # Stary unique_id schemat zeby nie tworzyc nowej encji
        self._attr_unique_id = f"thessla_select_{slave}_{self._address}"


class RekuperatorSezonSelect(_BaseModbusSelect):
    """Wybor harmonogramu LATO/ZIMA - rejestr 0x1071 / 4209."""

    def __init__(self, coordinator: ThesslaGreenCoordinator, slave: int):
        super().__init__(
            coordinator=coordinator,
            slave=slave,
            address=4209,
            name="Rekuperator Sezon",
            unique_prefix="sezon",
            options_map=SEASONS,
        )


class RekuperatorErvTrybSelect(_BaseModbusSelect):
    """ERV tryb (jesli centrala wyposazona w wymiennik entalpiczny)."""

    def __init__(self, coordinator: ThesslaGreenCoordinator, slave: int):
        super().__init__(
            coordinator=coordinator,
            slave=slave,
            address=4711,
            name="Rekuperator ERV tryb",
            unique_prefix="erv",
            options_map=ERV_MODES,
        )


class RekuperatorKomfortSelect(_BaseModbusSelect):
    """ECO/KOMFORT - rejestr 0x10D0 / 4304."""

    def __init__(self, coordinator: ThesslaGreenCoordinator, slave: int):
        super().__init__(
            coordinator=coordinator,
            slave=slave,
            address=4304,
            name="Rekuperator ECO/KOMFORT",
            unique_prefix="komfort",
            options_map=COMFORT_MODES,
        )