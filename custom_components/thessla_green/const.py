DOMAIN = "thessla_green"

# Serial / Modbus RTU
CONF_DEVICE = "device"
CONF_BAUDRATE = "baudrate"
CONF_PARITY = "parity"
CONF_STOPBITS = "stopbits"
CONF_BYTESIZE = "bytesize"
CONF_SLAVE = "slave"
CONF_SCAN_INTERVAL = "scan_interval"

# Defaults dobrane pod typowy konwerter Waveshare USB-RS485 (FT232/CH340)
# i typowe ustawienia Modbus RTU dla Thessla Green AirPack.
DEFAULT_DEVICE = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 9600
DEFAULT_PARITY = "N"        # N = none, E = even, O = odd
DEFAULT_STOPBITS = 1
DEFAULT_BYTESIZE = 8
DEFAULT_SLAVE = 10
DEFAULT_SCAN_INTERVAL = 30

PARITY_OPTIONS = ["N", "E", "O"]
STOPBITS_OPTIONS = [1, 2]
BYTESIZE_OPTIONS = [7, 8]
BAUDRATE_OPTIONS = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]