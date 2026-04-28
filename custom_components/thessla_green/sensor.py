from __future__ import annotations
import logging
from datetime import date
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTemperature, UnitOfTime, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_state_change_event

from . import DOMAIN
from .modbus_controller import ThesslaGreenModbusController
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)

# Mapowania dla sensorow z wartosciami enum (wg dokumentacji Thessla AirPack4)
GWC_STATUS_MAP = {
    0: "GWC nieaktywny",
    1: "Tryb zima",
    2: "Tryb lato",
}

KOMFORT_STATUS_MAP = {
    0: "KOMFORT nieaktywny",
    1: "Funkcja grzania",
    2: "Funkcja chlodzenia",
}

BYPASS_STATUS_MAP = {
    0: "Bypass nieaktywny",
    1: "Funkcja grzania (freeheating)",
    2: "Funkcja chlodzenia (freecooling)",
}

POSTHEATER_STATUS_MAP = {
    0: "Nieaktywna",
    1: "Aktywna",
}

# Sensory standardowe (numeryczne).
# v0.4.1: zmieniono nazwe "Temperatura PCB" -> "Temperatura otoczenia"
# (rejestr 22 wg dokumentacji to ambient_temperature TO, nie temperatura PCB).
SENSORS = [
    # Temperatury (input registers, scale 0.1)
    {"name": "Rekuperator Temperatura Czerpnia", "address": 16, "input_type": "input", "scale": 0.1, "precision": 1, "unit": UnitOfTemperature.CELSIUS, "icon": "mdi:thermometer"},
    {"name": "Rekuperator Temperatura Nawiew", "address": 17, "input_type": "input", "scale": 0.1, "precision": 1, "unit": UnitOfTemperature.CELSIUS, "icon": "mdi:thermometer"},
    {"name": "Rekuperator Temperatura Wywiew", "address": 18, "input_type": "input", "scale": 0.1, "precision": 1, "unit": UnitOfTemperature.CELSIUS, "icon": "mdi:thermometer"},
    {"name": "Rekuperator Temperatura za FPX", "address": 19, "input_type": "input", "scale": 0.1, "precision": 1, "unit": UnitOfTemperature.CELSIUS, "icon": "mdi:thermometer"},
    {"name": "Rekuperator Temperatura kanal nawiew", "address": 20, "input_type": "input", "scale": 0.1, "precision": 1, "unit": UnitOfTemperature.CELSIUS, "icon": "mdi:thermometer"},
    {"name": "Rekuperator Temperatura otoczenia", "address": 22, "input_type": "input", "scale": 0.1, "precision": 1, "unit": UnitOfTemperature.CELSIUS, "icon": "mdi:home-thermometer"},

    # Przeplywy (holding registers)
    {"name": "Rekuperator Strumien nawiew", "address": 256, "input_type": "holding", "scale": 1, "precision": 1, "unit": "m3/h", "icon": "mdi:fan"},
    {"name": "Rekuperator Strumien wywiew", "address": 257, "input_type": "holding", "scale": 1, "precision": 1, "unit": "m3/h", "icon": "mdi:fan"},

    # PWM wentylatorow (holding, scale 0.00244 V/jednostka)
    {"name": "Rekuperator PWM nawiew", "address": 1280, "input_type": "holding", "scale": 0.00244, "precision": 2, "unit": "V", "icon": "mdi:sine-wave"},
    {"name": "Rekuperator PWM wywiew", "address": 1281, "input_type": "holding", "scale": 0.00244, "precision": 2, "unit": "V", "icon": "mdi:sine-wave"},

    # Statusy i flagi (holding registers)
    {"name": "Rekuperator tryb pracy", "address": 4208, "input_type": "holding", "icon": "mdi:cog"},
    {"name": "Rekuperator speedmanual", "address": 4210, "input_type": "holding", "unit": "%", "icon": "mdi:speedometer"},
    {"name": "Rekuperator Predkosc chwilowy", "address": 4211, "input_type": "holding", "unit": "%", "icon": "mdi:speedometer-medium"},
    {"name": "Rekuperator Kod alarmu", "address": 4384, "input_type": "holding", "icon": "mdi:alert-circle"},

    # NOWE v0.4.1: zuzycie filtrow (% - tylko AirPack4, rejestry 0-127)
    {"name": "Rekuperator Filtr nawiewny zuzycie", "address": 4482, "input_type": "holding", "scale": 1, "precision": 0, "unit": "%", "icon": "mdi:air-filter"},
    {"name": "Rekuperator Filtr wywiewny zuzycie", "address": 4483, "input_type": "holding", "scale": 1, "precision": 0, "unit": "%", "icon": "mdi:air-filter"},
]

# Sensory z mapowaniem wartosci na opisowy tekst
ENUM_SENSORS = [
    {"name": "Rekuperator GWC status", "address": 4263, "value_map": GWC_STATUS_MAP, "icon": "mdi:earth"},
    {"name": "Rekuperator KOMFORT status", "address": 4305, "value_map": KOMFORT_STATUS_MAP, "icon": "mdi:thermostat"},
    {"name": "Rekuperator Bypass status", "address": 4330, "value_map": BYPASS_STATUS_MAP, "icon": "mdi:debug-step-over"},
    # NOWE v0.4.1: status nagrzewnicy wtornej (postHeater)
    {"name": "Rekuperator postHeater status", "address": 4704, "value_map": POSTHEATER_STATUS_MAP, "icon": "mdi:radiator"},
]

# Sensory dat wymiany filtrow (rejestry 4660, 4662)
# Wartosc to zapakowana data: dzien (b0-b4), miesiac (b5-b8), rok (b9-b15) gdzie rok = 2000+rok
FILTER_DATE_SENSORS = [
    {"name": "Rekuperator Filtr nawiewny data wymiany", "address": 4660, "icon": "mdi:calendar-clock"},
    {"name": "Rekuperator Filtr wywiewny data wymiany", "address": 4662, "icon": "mdi:calendar-clock"},
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    modbus_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: ThesslaGreenCoordinator = modbus_data["coordinator"]
    slave = modbus_data["slave"]

    entities = [
        ModbusGenericSensor(coordinator=coordinator, slave=slave, **sensor)
        for sensor in SENSORS
    ]

    entities.extend([
        ModbusEnumSensor(coordinator=coordinator, slave=slave, **sensor)
        for sensor in ENUM_SENSORS
    ])

    entities.extend([
        ModbusFilterDateSensor(coordinator=coordinator, slave=slave, **sensor)
        for sensor in FILTER_DATE_SENSORS
    ])

    # Sensor diagnostyczny
    entities.append(ModbusUpdateIntervalSensor(coordinator=coordinator, slave=slave))

    # Metryki obliczane
    power_entity = entry.options.get("sensor_power")
    if not power_entity:
        _LOGGER.warning("Nie skonfigurowano 'sensor_power' w opcjach integracji - COP bedzie 'unavailable'.")

    entities.extend([
        RekuEfficiencySensor(coordinator=coordinator, slave=slave),
        RekuRecoveryPowerSensor(coordinator=coordinator, slave=slave),
        RekuCOPSensor(coordinator=coordinator, slave=slave, power_entity=power_entity),
    ])

    async_add_entities(entities)


class ModbusGenericSensor(SensorEntity):
    """Representation of a standard Modbus sensor."""

    def __init__(self, coordinator: ThesslaGreenCoordinator, name, address, input_type="holding", scale=1.0, precision=0, unit=None, icon=None, slave=1):
        self.coordinator = coordinator
        self._address = address
        self._input_type = input_type
        self._scale = scale
        self._precision = precision
        self._unit = unit
        self._slave = slave
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_native_value = None
        self._attr_icon = icon
        # Bez suffixu - zachowuje kompatybilnosc ze starymi encjami
        self._attr_unique_id = f"thessla_sensor_{slave}_{address}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{slave}")},
            "name": "Rekuperator Thessla",
            "manufacturer": "Thessla Green",
            "model": "Modbus Rekuperator",
        }

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        if self._input_type == "input":
            raw_value = self.coordinator.safe_data.input.get(self._address)
        else:
            raw_value = self.coordinator.safe_data.holding.get(self._address)

        if raw_value is None:
            return None

        # Wartosc 0x8000 = brak odczytu temperatury (wg dokumentacji Thessla)
        if raw_value == 0x8000:
            return None

        # Konwersja na signed int16
        raw = raw_value
        if raw > 0x7FFF:
            raw -= 0x10000

        value = raw * self._scale
        return round(value, self._precision)

    async def async_update(self):
        pass

    async def async_added_to_hass(self):
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))


class ModbusEnumSensor(SensorEntity):
    """Sensor mapujacy wartosc rejestru na opisowy tekst (np. status GWC, bypass)."""

    def __init__(self, coordinator: ThesslaGreenCoordinator, name, address, value_map, icon=None, slave=1):
        self.coordinator = coordinator
        self._address = address
        self._value_map = value_map
        self._slave = slave
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"thessla_enum_{slave}_{address}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{slave}")},
            "name": "Rekuperator Thessla",
            "manufacturer": "Thessla Green",
            "model": "Modbus Rekuperator",
        }

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        raw = self.coordinator.safe_data.holding.get(self._address)
        if raw is None:
            return None
        return self._value_map.get(raw, f"Nieznany ({raw})")

    async def async_update(self):
        pass

    async def async_added_to_hass(self):
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))


class ModbusFilterDateSensor(SensorEntity):
    """Sensor dekodujacy spakowana date wymiany filtra z 16-bitowego rejestru.

    Format wg dokumentacji AirPack4:
      bity b0-b4   = dzien (5 bitow, 0-31)
      bity b5-b8   = miesiac (4 bity, 1-12)
      bity b9-b15  = rok (7 bitow, offset od 2000)

    Przyklad: 0x2d62 = 0010110 1011 00010
      rok = 2000 + 22 = 2022
      miesiac = 11
      dzien = 2
      -> 2022-11-02
    """

    _attr_device_class = "date"

    def __init__(self, coordinator: ThesslaGreenCoordinator, name, address, icon=None, slave=1):
        self.coordinator = coordinator
        self._address = address
        self._slave = slave
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"thessla_filterdate_{slave}_{address}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{slave}")},
            "name": "Rekuperator Thessla",
            "manufacturer": "Thessla Green",
            "model": "Modbus Rekuperator",
        }

    @property
    def available(self):
        return self.coordinator.last_update_success and self.native_value is not None

    @property
    def native_value(self):
        raw = self.coordinator.safe_data.holding.get(self._address)
        if raw is None or raw == 0:
            return None

        try:
            day = raw & 0x1F             # bity b0-b4
            month = (raw >> 5) & 0x0F    # bity b5-b8
            year = 2000 + ((raw >> 9) & 0x7F)  # bity b9-b15

            # Walidacja
            if not (1 <= day <= 31) or not (1 <= month <= 12) or not (2000 <= year <= 2099):
                _LOGGER.debug(
                    "Niepoprawna data filtra w rejestrze %d: raw=0x%04x -> %d-%02d-%02d",
                    self._address, raw, year, month, day
                )
                return None

            return date(year, month, day)
        except (ValueError, TypeError) as e:
            _LOGGER.debug("Blad dekodowania daty filtra (rejestr %d, raw=%s): %s", self._address, raw, e)
            return None

    async def async_update(self):
        pass

    async def async_added_to_hass(self):
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))


class ModbusUpdateIntervalSensor(SensorEntity):
    """Diagnostic sensor showing time between full Modbus updates."""

    def __init__(self, coordinator: ThesslaGreenCoordinator, slave: int):
        self.coordinator = coordinator
        self._slave = slave
        self._attr_name = "Modbus Update Interval"
        self._attr_native_unit_of_measurement = UnitOfTime.SECONDS
        self._attr_unique_id = f"thessla_update_interval_{slave}"
        self._attr_icon = "mdi:clock-time-eight"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{slave}")},
            "name": "Rekuperator Thessla",
            "manufacturer": "Thessla Green",
            "model": "Modbus Rekuperator",
        }

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        return self.coordinator.safe_data.update_interval

    async def async_update(self):
        pass

    async def async_added_to_hass(self):
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))


# =============================
#  Metryki: sprawnosc / moc / COP
# =============================

class _BaseComputedSensor(SensorEntity):
    """Baza dla sensorow liczonych z koordynatora."""
    _attr_should_poll = False

    def __init__(self, coordinator: ThesslaGreenCoordinator, slave: int):
        self.coordinator = coordinator
        self._slave = slave
        self._attr_native_value = None
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{slave}")},
            "name": "Rekuperator Thessla",
            "manufacturer": "Thessla Green",
            "model": "Modbus Rekuperator",
        }

    @property
    def available(self):
        return self.coordinator.last_update_success and self._attr_native_value is not None

    async def async_added_to_hass(self):
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_coordinator_update))
        self._recalc()
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self):
        self._recalc()
        self.async_write_ha_state()

    def _read_temp_czerpnia(self) -> float | None:
        return self._read_input_scaled(addr=16, scale=0.1, precision=1)

    def _read_temp_nawiew(self) -> float | None:
        return self._read_input_scaled(addr=17, scale=0.1, precision=1)

    def _read_temp_wywiew(self) -> float | None:
        return self._read_input_scaled(addr=18, scale=0.1, precision=1)

    def _read_flow_nawiew(self) -> float | None:
        return self._read_holding_scaled(addr=256, scale=1.0)

    def _read_input_scaled(self, addr: int, scale: float, precision: int) -> float | None:
        raw = self.coordinator.safe_data.input.get(addr)
        if raw is None or raw == 0x8000:
            return None
        if raw > 0x7FFF:
            raw -= 0x10000
        return round(raw * scale, precision)

    def _read_holding_scaled(self, addr: int, scale: float) -> float | None:
        raw = self.coordinator.safe_data.holding.get(addr)
        if raw is None:
            return None
        if raw > 0x7FFF:
            raw -= 0x10000
        return float(raw) * scale

    def _recalc(self):
        raise NotImplementedError


class RekuEfficiencySensor(_BaseComputedSensor):
    """Sprawnosc [%] = ((Tnawiew - Tczerpnia) / (Twywiew - Tczerpnia)) * 100"""
    def __init__(self, coordinator: ThesslaGreenCoordinator, slave: int):
        super().__init__(coordinator, slave)
        self._attr_name = "Rekuperator Sprawnosc"
        self._attr_unique_id = f"thessla_efficiency_{slave}"
        self._attr_icon = "mdi:percent"
        self._attr_native_unit_of_measurement = "%"

    def _recalc(self):
        To = self._read_temp_czerpnia()
        Te = self._read_temp_wywiew()
        Ts = self._read_temp_nawiew()
        if None in (To, Te, Ts):
            self._attr_native_value = None
            return
        denom = Te - To
        if abs(denom) < 0.5:
            self._attr_native_value = None
            return
        self._attr_native_value = round(((Ts - To) / denom) * 100.0, 1)


class RekuRecoveryPowerSensor(_BaseComputedSensor):
    """Moc odzysku [kW]"""
    def __init__(self, coordinator: ThesslaGreenCoordinator, slave: int):
        super().__init__(coordinator, slave)
        self._attr_name = "Rekuperator Moc Odzysku"
        self._attr_unique_id = f"thessla_recovery_power_{slave}"
        self._attr_icon = "mdi:fire"
        self._attr_native_unit_of_measurement = "kW"

    def _recalc(self):
        To = self._read_temp_czerpnia()
        Ts = self._read_temp_nawiew()
        flow = self._read_flow_nawiew()
        if None in (To, Ts) or flow is None or flow <= 0:
            self._attr_native_value = None
            return
        q_kw = 0.000335 * flow * (Ts - To)
        self._attr_native_value = round(q_kw, 3)


class RekuCOPSensor(_BaseComputedSensor):
    """COP = (moc odzysku [kW]) / (pobor elektryczny [kW])"""

    def __init__(self, coordinator: ThesslaGreenCoordinator, slave: int, power_entity: str | None):
        super().__init__(coordinator, slave)
        self._attr_name = "Rekuperator COP"
        self._attr_unique_id = f"thessla_cop_{slave}"
        self._attr_icon = "mdi:chart-line"
        self._attr_native_unit_of_measurement = "x"
        self._power_entity = power_entity
        self._last_power_val = None
        self._last_power_unit = None

    @property
    def extra_state_attributes(self):
        return {
            "power_entity": self._power_entity,
            "power_value_raw": self._last_power_val,
            "power_unit": self._last_power_unit,
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if self._power_entity:
            @callback
            def _on_power_change(event):
                self._recalc()
                self.async_write_ha_state()

            unsub = async_track_state_change_event(
                self.hass,
                [self._power_entity],
                _on_power_change,
            )
            self.async_on_remove(unsub)

    def _read_power_kw(self) -> float | None:
        if not self._power_entity:
            return None
        st = self.hass.states.get(self._power_entity)
        if not st:
            return None

        unit = (st.attributes.get("unit_of_measurement") or "").strip()
        self._last_power_unit = unit

        try:
            val = float(st.state)
        except (TypeError, ValueError):
            self._last_power_val = st.state
            return None

        self._last_power_val = val
        u = unit.lower()

        if u in ("w", "watt"):
            return val / 1000.0
        if u == "kw":
            return val
        if "kwh" in u:
            _LOGGER.warning(
                "Wybrany sensor '%s' podaje energie (%s), a nie moc. COP wymaga mocy chwilowej w W/kW.",
                self._power_entity, unit
            )
            return None
        _LOGGER.debug("Sensor mocy '%s' ma jednostke '%s' - przyjmuje jako kW.", self._power_entity, unit)
        return val

    def _recalc(self):
        To = self._read_temp_czerpnia()
        Ts = self._read_temp_nawiew()
        flow = self._read_flow_nawiew()
        p_kw = self._read_power_kw()

        if None in (To, Ts) or flow is None or flow <= 0 or p_kw is None or p_kw <= 0:
            self._attr_native_value = None
            return

        q_kw = 0.000335 * flow * (Ts - To)
        self._attr_native_value = round(q_kw / p_kw, 2) if q_kw > 0 else None