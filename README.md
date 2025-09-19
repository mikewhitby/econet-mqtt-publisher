# Econet MQTT Publisher

A Python-based MQTT publisher that reads data from an Econet heat pump controller and publishes the metrics to an MQTT broker.

**Docker Hub:** `mwhitby/econet-mqtt-publisher:latest`

## Features

- Configurable via environment variables
- Polls Econet endpoint at configurable intervals
- Publishes 13 different heat pump metrics to MQTT topics
- **Home Assistant MQTT discovery** - automatic entity creation
- Runs in Docker container
- Graceful shutdown handling
- Comprehensive logging

## Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `MQTT_HOST` | `localhost` | No | MQTT broker hostname |
| `MQTT_PORT` | `1883` | No | MQTT broker port |
| `MQTT_USERNAME` | `""` | No | MQTT broker username |
| `MQTT_PASSWORD` | `""` | No | MQTT broker password |
| `MQTT_TOPIC_PREFIX` | `econet/` | No | Prefix for all MQTT topics |
| `ECONET_ENDPOINT` | - | **Yes** | Econet controller IP/hostname (without http://) |
| `POLLING_INTERVAL` | `10` | No | Polling interval in seconds |
| `HA_DISCOVERY_MESSAGES` | `true` | No | Enable Home Assistant MQTT discovery |
| `HA_DISCOVERY_NAME` | `Grant R290 ASHP` | No | Device name for Home Assistant discovery |

## Published Topics

The following MQTT topics are published with the configured prefix:

- `econet/ashp_circuit1_calculated_set_temp` - Circuit 1 calculated set temperature
- `econet/ashp_compressor_freq` - Compressor frequency
- `econet/ashp_fan_speed` - Fan speed
- `econet/ashp_flow_temp` - Flow temperature
- `econet/ashp_outlet_water_pressure` - Outlet water pressure
- `econet/ashp_pump_active` - Upper pump status
- `econet/ashp_return_temp` - Return temperature
- `econet/ashp_target_temp` - Target temperature
- `econet/ashp_work_state` - Work state
- `econet/circuit1_thermostat` - Circuit 1 thermostat
- `econet/dhw_temp` - Domestic hot water temperature
- `econet/outdoor_temp` - Outdoor temperature
- `econet/three_way_valve_state` - Three way valve state

## Home Assistant Integration

When `HA_DISCOVERY_MESSAGES` is enabled (default), the publisher automatically creates Home Assistant entities via MQTT discovery. This means:

- **No manual configuration needed** - entities appear automatically in Home Assistant
- **Proper device classes** - temperature sensors show with °C, pressure with bar, etc.
- **Meaningful names** - "ASHP Flow Temperature" instead of technical topic names
- **Appropriate icons** - thermometers for temperatures, fans for fan speed, etc.
- **Device grouping** - all sensors appear under a single device (configurable name, defaults to "Grant R290 ASHP")

### Supported Entity Types

- **Temperature sensors**: All temperature readings with proper °C units and thermometer icons
- **Binary sensors**: Pump active status with on/off states
- **Regular sensors**: Frequencies, pressures, speeds, and state values

### Discovery Topics

Discovery messages are published to `homeassistant/sensor/econet_*/config` and `homeassistant/binary_sensor/econet_*/config` topics with retain flag for persistence.

To disable Home Assistant discovery, set `HA_DISCOVERY_MESSAGES=false`.

## Usage

### Quick Start with Docker Hub Image

The easiest way to get started is using the pre-built image from Docker Hub:

```bash
docker run -d \
  --name econet-mqtt-publisher \
  -e ECONET_ENDPOINT=192.168.1.100 \
  -e MQTT_HOST=mqtt.local \
  -e MQTT_USERNAME=myuser \
  -e MQTT_PASSWORD=mypass \
  mwhitby/econet-mqtt-publisher:latest
```

### Running with Docker (Build Locally)

1. Clone this repository:
```bash
git clone https://github.com/yourusername/econet-mqtt-publisher.git
cd econet-mqtt-publisher
```

2. Build the Docker image:
```bash
docker build -t econet-mqtt-publisher .
```

3. Run the container:
```bash
docker run -d \
  --name econet-mqtt-publisher \
  -e ECONET_ENDPOINT=192.168.1.100 \
  -e MQTT_HOST=mqtt.local \
  -e MQTT_USERNAME=myuser \
  -e MQTT_PASSWORD=mypass \
  econet-mqtt-publisher
```

### Running with Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: '3.8'
services:
  econet-mqtt-publisher:
    image: mwhitby/econet-mqtt-publisher:latest
    container_name: econet-mqtt-publisher
    environment:
      - ECONET_ENDPOINT=192.168.1.100
      - MQTT_HOST=mqtt.local
      - MQTT_USERNAME=myuser
      - MQTT_PASSWORD=mypass
      - POLLING_INTERVAL=30
      - HA_DISCOVERY_NAME=My Heat Pump
    restart: unless-stopped
```

Then run:
```bash
docker-compose up -d
```

**Alternative: Build from source**
```yaml
version: '3.8'
services:
  econet-mqtt-publisher:
    build: .  # Build from local source instead of using Docker Hub image
    # ... rest of configuration
```

### Running Locally

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables and run:
```bash
export ECONET_ENDPOINT=192.168.1.100
export MQTT_HOST=mqtt.local
python mqtt_publisher.py
```

## Logging

- Standard output: Normal operation logs including polled values
- Standard error: Error messages and exceptions
- All logs include timestamps and log levels

## Graceful Shutdown

The publisher handles `SIGTERM` and `SIGINT` signals for graceful shutdown, ensuring proper cleanup of MQTT connections.

## Requirements

- Python 3.11+
- Access to Econet controller on the network
- MQTT broker accessible from the container/host
