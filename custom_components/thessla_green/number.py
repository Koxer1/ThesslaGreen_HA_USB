from __future__ import annotations
import logging

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from . import DOMAIN
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    modbus_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: ThesslaGreenCoordinator = modbus_data["coordinator"]
    slave = modbus_data["slave"]

    async_add_entities([
        RekuperatorPredkoscNumber(coordinator=coordinator, slave=slave),
        RekuperatorPredkoscChwilowyNumber(coordinator=coordinator, slave=slave),
        RekuperatorTempNawiewuManualnyNumber(coordinator=coordinator, slave=slave),
    ])


class _BaseModbusNumber(NumberEntity):
    """Wspolna baza dla numerycznych encji Modbus."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        slave: int,
        address: int,
        name: str,
        unique_suffix: str,
        unit: str,
        min_value: float,
        max_value: float,
        step: float,
        scale: float = 1.0,
        icon: str | None = None,
    ):
        self.coordinator = coordinator
        self._address = address
        self._slave = slave
        self._scale = scale
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_icon = icon
        self._attr_unique_id = f"thessla_number_{slave}_{unique_suffix}_{address}"

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
    def native_value(self) -> float | None:
        raw = self.coordinator.safe_data.holding.get(self._address)
        if raw is None:
            return None
        return raw * self._scale

    async def async_set_native_value(self, value: float) -> None:
        try:
            raw = int(round(value / self._scale))
            success = await self.coordinator.controller.write_register(self._address, raw)
            if success:
                await self.coordinator.async_request_refresh()
        except Exception as e:
            _LOGGER.exception(f"Exception during setting {self._attr_name}: {e}")

    async def async_update(self):
        pass

    async def async_added_to_hass(self):
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))


class RekuperatorPredkoscNumber(_BaseModbusNumber):
    """Intensywnosc wentylacji - tryb MANUALNY (rejestr 0x1072)."""

    def __init__(self, coordinator: ThesslaGreenCoordinator, slave: int):
        # Zachowuje stary unique_id dla kompatybilnosci - bez suffixu w nazwie ID
        super().__init__(
            coordinator=coordinator,
            slave=slave,
            address=4210,
            name="Rekuperator Predkosc",
            unique_suffix="",
            unit="%",
            min_value=0,
            max_value=100,
            step=1,
            scale=1.0,
            icon="mdi:speedometer",
        )
        # Override unique_id zeby zachowac kompatybilnosc z poprzednia wersja
        self._attr_unique_id = f"thessla_number_{slave}_{self._address}"


class RekuperatorPredkoscChwilowyNumber(_BaseModbusNumber):
    """Intensywnosc wentylacji - tryb CHWILOWY (rejestr 0x1073).

    Dokumentacja Thessla: aby aktywowac tryb chwilowy nalezy zapisac wartosci w 3 rejestrach:
      0x1130 (4400) -> 2 (tryb CHWILOWY)
      0x1131 (4401) -> wybrana intensywnosc
      0x1132 (4402) -> 1 (aktywacja zmiany)
    Ten number ustawia tylko intensywnosc dla trybu chwilowego (rejestr 4211).
    """

    def __init__(self, coordinator: ThesslaGreenCoordinator, slave: int):
        super().__init__(
            coordinator=coordinator,
            slave=slave,
            address=4211,
            name="Rekuperator Predkosc Chwilowy",
            unique_suffix="chwilowy",
            unit="%",
            min_value=10,
            max_value=100,
            step=1,
            scale=1.0,
            icon="mdi:speedometer-medium",
        )


class RekuperatorTempNawiewuManualnyNumber(_BaseModbusNumber):
    """Zadana temperatura nawiewu - tryb MANUALNY (rejestr 0x1074, scale 0.5)."""

    def __init__(self, coordinator: ThesslaGreenCoordinator, slave: int):
        super().__init__(
            coordinator=coordinator,
            slave=slave,
            address=4212,
            name="Rekuperator Temp nawiewu manualny",
            unique_suffix="temp_man",
            unit="°C",
            min_value=10,
            max_value=45,
            step=0.5,
            scale=0.5,
            icon="mdi:thermometer-lines",
        )