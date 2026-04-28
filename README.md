# Thessla Green – Home Assistant integration (USB / Modbus RTU)

Fork of [aLAN-LDZ/ThesslaGreen_HA](https://github.com/aLAN-LDZ/ThesslaGreen_HA)
that talks to Thessla Green AirPack recuperators **directly over USB-RS485**
(Modbus RTU), instead of requiring a network Modbus TCP gateway.

## What's different from upstream

The upstream integration uses `AsyncModbusTcpClient` and expects an IP/port to a
Modbus TCP server. This fork swaps that for `AsyncModbusSerialClient`, so you
can plug a USB-RS485 dongle (e.g. Waveshare USB-to-RS485) straight into your
Home Assistant host and connect it to the recuperator's Modbus terminals.

No bridge, no `ser2net`, no extra add-on.

## Requirements

- Home Assistant OS / Supervised / Container with USB passthrough
- USB-RS485 converter (FT232 / CH340 chipsets confirmed working)
- Thessla Green AirPack with Modbus RTU enabled on its RS485 port
- HACS

## Installation

1. HACS → ⋮ → Custom repositories → add `https://github.com/Koxer1/ThesslaGreen_HA_USB`, category **Integration**
2. Search for "Thessla Green (USB / Modbus RTU)" in HACS and install
3. Restart Home Assistant
4. Settings → Devices & Services → Add Integration → "Thessla Green"

## Configuration

The config flow asks for:

| Field         | Default        | Notes                                     |
| ------------- | -------------- | ----------------------------------------- |
| Device        | `/dev/ttyUSB0` | Use `/dev/serial/by-id/...` for stability |
| Baudrate      | 9600           | Match the AirPack's Modbus settings       |
| Parity        | N              | N / E / O                                 |
| Stop bits     | 1              | 1 or 2                                    |
| Byte size     | 8              | 7 or 8                                    |
| Slave ID      | 10             | AirPack default; check your config        |
| Scan interval | 30 s           | Polling period                            |

## Finding the right device path

In a HA terminal (SSH add-on):
