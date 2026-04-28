import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict

from pymodbus.client import AsyncModbusSerialClient

_LOGGER = logging.getLogger(__name__)


@dataclass
class ControllerData:
    holding: Dict[int, int] = field(default_factory=dict)
    input: Dict[int, int] = field(default_factory=dict)
    coil: Dict[int, bool] = field(default_factory=dict)
    update_interval: float = 0.0


class ControllerException(Exception):
    def __init__(self, message):
        super().__init__(message)


class ThesslaGreenModbusController:
    """Modbus RTU controller for Thessla Green AirPack via USB-RS485.

    Mapowanie rejestrow zgodne z dokumentacja AirPack4 (08.2022.01).
    """

    def __init__(
        self,
        device: str,
        baudrate: int,
        parity: str,
        stopbits: int,
        bytesize: int,
        slave_id: int,
        update_interval: int = 30,
    ):
        self._device = device
        self._baudrate = baudrate
        self._parity = parity
        self._stopbits = stopbits
        self._bytesize = bytesize
        self._slave = slave_id
        self._update_interval = update_interval

        self._client = AsyncModbusSerialClient(
            port=self._device,
            baudrate=self._baudrate,
            parity=self._parity,
            stopbits=self._stopbits,
            bytesize=self._bytesize,
            timeout=3,
            reconnect_delay=1,
            reconnect_delay_max=300,
            retries=3,
        )
        self._controller_lock = asyncio.Lock()

        self._last_update_timestamp: float = 0
        self._last_update_interval: float = 0

        # Bloki rejestrow holding (start, count) - max 16 rejestrow w jednym odczycie.
        # Komentarze wskazuja zawartosc bloku.
        self._holding_blocks = [
            (256, 2),         # supplyAirFlow, exhaustAirFlow
            (1280, 2),        # dac_supply, dac_exhaust (PWM wentylatorow)
            (4192, 2),        # antifreezMode, ...
            (4198, 1),        # antifreezStage
            (4208, 7),        # mode, seasonMode, airFlowRateManual, airFlowRateTemporary, ...
            (4224, 1),        # specialMode
            (4263, 1),        # gwcMode
            (4304, 2),        # comfortModePanel, comfortMode
            (4320, 1),        # bypassOff
            (4330, 1),        # bypassMode
            (4384, 1),        # stopAhuCode
            (4387, 1),        # onOffPanelMode
            (4482, 2),        # cfgSZF_FN_new, cfgSZF_FW_new (zuzycie filtrow %) - NOWE v0.4.1
            (4660, 1),        # filter_supply_date_limit_get (data wymiany filtra naw) - NOWE v0.4.1
            (4662, 1),        # filter_exhaust_date_limit_get (data wymiany filtra wyw) - NOWE v0.4.1
            (4704, 1),        # postHeater_on (status nagrzewnicy wtornej ERV) - NOWE v0.4.1
            (4711, 1),        # cfgPostHeaterMode (tryb ERV)
            (8192, 2),        # alarm, error
            (8208, 1),        # S16
            (8222, 2),        # S30, S31
            (8300, 1),        # E108 (czujnik TW) - NOWE v0.4.1
            (8330, 14),       # E138-F151 (CF, filtry, przeplyw, alarmy filtrow) - NOWE v0.4.1
            (8344, 1),        # E152
            (8348, 2),        # E156, E157 (czas uzytkowania filtrow) - NOWE v0.4.1
            (8444, 1),        # E252
        ]

        # Input registers
        self._input_blocks = [
            (16, 7),          # outside_temperature, supply, exhaust, fpx, duct_supply, gwc, ambient
            (22, 1),          # ambient_temperature - duplikat ostatniego z bloku (16,7), zachowany dla kompat.
        ]

        # Coil registers
        self._coil_blocks = [(9, 3)]

    async def stop(self):
        async with self._controller_lock:
            _LOGGER.info("Stopping Modbus RTU controller for %s", self._device)
            self._client.close()

    async def fetch_data(self) -> ControllerData:
        async with self._controller_lock:
            await self._ensure_connected()

            data_holding: dict[int, int] = {}
            data_input: dict[int, int] = {}
            data_coil: dict[int, bool] = {}

            now = time.time()
            if self._last_update_timestamp:
                self._last_update_interval = now - self._last_update_timestamp
                _LOGGER.debug("Time since last update: %.2f seconds", self._last_update_interval)
            self._last_update_timestamp = now

            _LOGGER.debug("Reading all register blocks for slave %d", self._slave)

            # Read holding registers
            for start, count in self._holding_blocks:
                try:
                    result = await self._client.read_holding_registers(
                        address=start, count=count, device_id=self._slave
                    )
                    if result.isError():
                        raise ControllerException(
                            f"Error reading holding registers {start}-{start + count - 1}"
                        )
                    for i, val in enumerate(result.registers):
                        data_holding[start + i] = val
                    _LOGGER.debug(
                        "Holding registers %d-%d read: %s",
                        start, start + count - 1, result.registers
                    )
                except Exception as e:
                    raise ControllerException(
                        f"Exception reading holding registers {start}-{start + count - 1}: {e}"
                    ) from e

            # Read input registers
            for start, count in self._input_blocks:
                try:
                    result = await self._client.read_input_registers(
                        address=start, count=count, device_id=self._slave
                    )
                    if result.isError():
                        raise ControllerException(
                            f"Error reading input registers {start}-{start + count - 1}"
                        )
                    for i, val in enumerate(result.registers):
                        data_input[start + i] = val
                    _LOGGER.debug(
                        "Input registers %d-%d read: %s",
                        start, start + count - 1, result.registers
                    )
                except Exception as e:
                    raise ControllerException(
                        f"Exception reading input registers {start}-{start + count - 1}: {e}"
                    ) from e

            # Read coils
            for start, count in self._coil_blocks:
                try:
                    result = await self._client.read_coils(
                        address=start, count=count, device_id=self._slave
                    )
                    if result.isError():
                        raise ControllerException(
                            f"Error reading coils {start}-{start + count - 1}"
                        )
                    for i, val in enumerate(result.bits):
                        data_coil[start + i] = bool(val)
                    _LOGGER.debug(
                        "Coils %d-%d read: %s",
                        start, start + count - 1, result.bits
                    )
                except Exception as e:
                    raise ControllerException(
                        f"Exception reading coils {start}-{start + count - 1}: {e}"
                    ) from e

            return ControllerData(
                holding=data_holding,
                input=data_input,
                coil=data_coil,
                update_interval=round(self._last_update_interval, 2)
            )

    async def write_register(self, address: int, value: int) -> bool:
        async with self._controller_lock:
            await self._ensure_connected()

            try:
                _LOGGER.debug("Writing register %d = %s (slave=%d)", address, value, self._slave)
                result = await self._client.write_register(
                    address=address, value=value, device_id=self._slave
                )
                if result.isError():
                    raise ControllerException(
                        f"Failed to write register {address} with value {value}"
                    )
                _LOGGER.info("Successfully wrote register %d = %s", address, value)
                return True
            except Exception as e:
                raise ControllerException(
                    f"Exception writing register {address} = {value}: {e}"
                ) from e

    async def _ensure_connected(self):
        if self._client.connected:
            return

        _LOGGER.info(
            "Attempting connection to Modbus RTU device %s @ %d %d%s%d",
            self._device, self._baudrate, self._bytesize, self._parity, self._stopbits
        )
        try:
            if await self._client.connect():
                _LOGGER.info("Successfully connected to Modbus RTU device %s", self._device)
                return
        except Exception as e:
            raise ControllerException(
                f"Exception during Modbus RTU connection to {self._device}: {e}"
            ) from e

        raise ControllerException(f"Failed to connect to Modbus RTU device {self._device}")