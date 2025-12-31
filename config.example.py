"""
Configuration file for Nibe 360P communication

Copy this to config.py and adjust for your setup
"""

# Serial port configuration
# Windows: 'COM3', 'COM4', etc.
# Linux: '/dev/ttyUSB0', '/dev/ttyAMA0', etc.
# macOS: '/dev/tty.usbserial-XXXX'
SERIAL_PORT = "COM3"

# Baud rate (typically 9600 for Nibe heat pumps)
BAUDRATE = 9600

# Read timeout in seconds
READ_TIMEOUT = 5.0

# Delay between register reads (in seconds)
READ_INTERVAL = 1.0

# Continuous monitoring mode
MONITOR_MODE = True

# Logging configuration
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Data logging
ENABLE_DATA_LOGGING = False
LOG_FILE = "nibe_data.csv"

# MQTT configuration (optional)
ENABLE_MQTT = False
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_USERNAME = ""
MQTT_PASSWORD = ""
MQTT_TOPIC_PREFIX = "nibe/360p"

# Home Assistant MQTT Discovery (optional)
ENABLE_HA_DISCOVERY = False
HA_DISCOVERY_PREFIX = "homeassistant"

# Web API configuration (optional)
ENABLE_WEB_API = False
WEB_API_HOST = "0.0.0.0"
WEB_API_PORT = 8080

# Monitoring intervals (in seconds)
FAST_POLL_INTERVAL = 10  # For frequently changing values (temperatures, frequencies)
SLOW_POLL_INTERVAL = 60  # For slowly changing values (operation times, counters)
STATUS_POLL_INTERVAL = 5  # For status and alarms

# Registers to monitor continuously (by address)
MONITORED_REGISTERS = [
    40004,  # Outdoor temperature
    40008,  # Supply temperature
    40012,  # Return temperature
    40013,  # Hot water temperature
    43005,  # Degree minutes
    43136,  # Compressor frequency
    45001,  # Alarm status
]

# Alarm notification
ENABLE_ALARM_NOTIFICATION = False
ALARM_NOTIFICATION_EMAIL = ""
ALARM_NOTIFICATION_WEBHOOK = ""

# Data export
ENABLE_INFLUXDB = False
INFLUXDB_HOST = "localhost"
INFLUXDB_PORT = 8086
INFLUXDB_DATABASE = "nibe"
INFLUXDB_USERNAME = ""
INFLUXDB_PASSWORD = ""
