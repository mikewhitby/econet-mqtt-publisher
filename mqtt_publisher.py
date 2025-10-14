#!/usr/bin/env python3

import os
import sys
import time
import json
import signal
import logging
import requests
from typing import Dict, Any, Optional
import paho.mqtt.client as mqtt
from requests.auth import HTTPBasicAuth

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class EconetMQTTPublisher:
    def __init__(self):
        # Load configuration from environment variables
        self.mqtt_host = os.getenv('MQTT_HOST', 'localhost')
        self.mqtt_port = int(os.getenv('MQTT_PORT', '1883'))
        self.mqtt_username = os.getenv('MQTT_USERNAME', '')
        self.mqtt_password = os.getenv('MQTT_PASSWORD', '')
        self.mqtt_topic_prefix = os.getenv('MQTT_TOPIC_PREFIX', 'econet/')
        self.econet_endpoint = os.getenv('ECONET_ENDPOINT')
        self.polling_interval = int(os.getenv('POLLING_INTERVAL', '10'))
        self.ha_discovery = os.getenv('HA_DISCOVERY_MESSAGES', 'true').lower() == 'true'
        self.ha_discovery_name = os.getenv('HA_DISCOVERY_NAME', 'Grant R290')

        # Validate required configuration
        if not self.econet_endpoint:
            logger.error("ECONET_ENDPOINT environment variable is required")
            sys.exit(1)

        # Ensure topic prefix ends with /
        if not self.mqtt_topic_prefix.endswith('/'):
            self.mqtt_topic_prefix += '/'

        # MQTT client setup
        self.mqtt_client = mqtt.Client()
        if self.mqtt_username:
            self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)

        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_disconnect = self._on_mqtt_disconnect

        # MQTT availability (LWT) setup
        # Use a single availability topic for this publisher
        self.availability_topic = f"{self.mqtt_topic_prefix}availability"
        # Set Last Will to offline, retained, so HA marks entities unavailable if we disconnect unexpectedly
        self.mqtt_client.will_set(self.availability_topic, payload="offline", retain=True)

        # Econet credentials (fixed as per instructions)
        self.econet_auth = HTTPBasicAuth('admin', 'admin')

        # Topic mapping: topic_name -> JSON path
        self.topic_mappings = {
            'ashp_ambient_air_temp': ['curr', 'AxenOutdoorTemp'],
            'ashp_circuit1_calculated_set_temp': ['tilesParams', 29, 0, 0],
            'ashp_compressor_freq': ['curr', 'AxenCompressorFreq'],
            'ashp_fan_speed': ['tilesParams', 3, 0, 0],
            'ashp_flow_temp': ['curr', 'AxenOutgoingTemp'],
            'ashp_outlet_water_pressure': ['tilesParams', 76, 0, 0],
            'ashp_pump_active': ['curr', 'AxenUpperPump'],
            'ashp_return_temp': ['curr', 'AxenReturnTemp'],
            'ashp_target_temp': ['curr', 'HeatSourceCalcPresetTemp'],
            'ashp_work_state': ['curr', 'AxenWorkState'],
            'circuit1_thermostat': ['curr', 'Circuit1thermostat'],
            'dhw_temp': ['curr', 'TempCWU'],
            'outdoor_temp': ['curr', 'TempWthr'],
            'three_way_valve_state': ['curr', 'flapValveStates']
        }

        # Home Assistant discovery metadata
        self.ha_discovery_configs = {
            'ashp_ambient_air_temp': {
                'name': 'ASHP Ambient Air Temperature',
                'device_class': 'temperature',
                'state_class': 'measurement',
                'unit_of_measurement': '°C',
                'icon': 'mdi:thermometer'
            },
            'ashp_circuit1_calculated_set_temp': {
                'name': 'ASHP Circuit 1 Calculated Set Temperature',
                'device_class': 'temperature',
                'state_class': 'measurement',
                'unit_of_measurement': '°C',
                'icon': 'mdi:thermometer'
            },
            'ashp_compressor_freq': {
                'name': 'ASHP Compressor Frequency',
                'device_class': 'frequency',
                'state_class': 'measurement',
                'unit_of_measurement': 'Hz',
                'icon': 'mdi:sine-wave'
            },
            'ashp_fan_speed': {
                'name': 'ASHP Fan Speed',
                'state_class': 'measurement',
                'unit_of_measurement': 'rpm',
                'icon': 'mdi:fan'
            },
            'ashp_flow_temp': {
                'name': 'ASHP Flow Temperature',
                'device_class': 'temperature',
                'state_class': 'measurement',
                'unit_of_measurement': '°C',
                'icon': 'mdi:thermometer-chevron-up'
            },
            'ashp_outlet_water_pressure': {
                'name': 'ASHP Outlet Water Pressure',
                'device_class': 'pressure',
                'state_class': 'measurement',
                'unit_of_measurement': 'bar',
                'icon': 'mdi:gauge'
            },
            'ashp_pump_active': {
                'name': 'ASHP Pump',
                'device_class': 'running',
                'state_class': 'measurement',
                'icon': 'mdi:pump',
                'payload_on': '1',
                'payload_off': '0'
            },
            'ashp_return_temp': {
                'name': 'ASHP Return Temperature',
                'device_class': 'temperature',
                'state_class': 'measurement',
                'unit_of_measurement': '°C',
                'icon': 'mdi:thermometer-chevron-down'
            },
            'ashp_target_temp': {
                'name': 'ASHP Target Temperature',
                'device_class': 'temperature',
                'state_class': 'measurement',
                'unit_of_measurement': '°C',
                'icon': 'mdi:thermometer'
            },
            'ashp_work_state': {
                'name': 'ASHP Work State',
                'device_class': 'running',
                'state_class': 'measurement',
                'icon': 'mdi:state-machine',
                'payload_on': '1',
                'payload_off': '0'
            },
            'circuit1_thermostat': {
                'name': 'Circuit 1 Thermostat Temperature',
                'device_class': 'temperature',
                'state_class': 'measurement',
                'unit_of_measurement': '°C',
                'icon': 'mdi:thermostat'
            },
            'dhw_temp': {
                'name': 'Cylinder Temperature',
                'device_class': 'temperature',
                'state_class': 'measurement',
                'unit_of_measurement': '°C',
                'icon': 'mdi:water-thermometer'
            },
            'outdoor_temp': {
                'name': 'Outdoor Sensor Temperature',
                'device_class': 'temperature',
                'state_class': 'measurement',
                'unit_of_measurement': '°C',
                'icon': 'mdi:thermometer'
            },
            'three_way_valve_state': {
                'name': 'Three Way Valve State',
                'device_class': 'enum',
                'icon': 'mdi:valve',
                'options': ['CH', 'DHW']
            }
        }

        self.running = True

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        logger.info(f"Initialized EconetMQTTPublisher with:")
        logger.info(f"  MQTT Broker: {self.mqtt_host}:{self.mqtt_port}")
        logger.info(f"  Topic Prefix: {self.mqtt_topic_prefix}")
        logger.info(f"  Econet Endpoint: {self.econet_endpoint}")
        logger.info(f"  Polling Interval: {self.polling_interval}s")
        logger.info(f"  Home Assistant Discovery: {self.ha_discovery}")
        if self.ha_discovery:
            logger.info(f"  HA Device Name: {self.ha_discovery_name}")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            # Mark this integration as available
            try:
                self.mqtt_client.publish(self.availability_topic, "online", retain=True)
            except Exception as e:
                logger.error(f"Failed to publish availability online status: {e}")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")

    def _on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        logger.info("Disconnected from MQTT broker")

    def _get_nested_value(self, data: Dict[str, Any], path: list) -> Optional[Any]:
        """Extract value from nested dictionary/list using path"""
        try:
            current = data
            for key in path:
                if isinstance(current, dict):
                    current = current[key]
                elif isinstance(current, list):
                    current = current[int(key)]
                else:
                    return None

            # If the final value is a list, take the first element
            # This handles cases like tilesParams[29][0][0] returning ['24.0', 1, 0]
            if isinstance(current, list) and len(current) > 0:
                return current[0]

            return current
        except (KeyError, IndexError, TypeError, ValueError):
            return None

    def _fetch_econet_data(self) -> Optional[Dict[str, Any]]:
        """Fetch data from Econet endpoint"""
        try:
            url = f"http://{self.econet_endpoint}/econet/regParams"
            response = requests.get(url, auth=self.econet_auth, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch data from Econet: {e}", file=sys.stderr)
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response from Econet: {e}", file=sys.stderr)
            return None

    def _publish_ha_discovery(self):
        """Publish Home Assistant MQTT discovery messages"""
        if not self.ha_discovery:
            return

        logger.info("Publishing Home Assistant discovery messages...")
        device_info = {
            "identifiers": ["econet_mqtt_publisher"],
            "name": self.ha_discovery_name,
            "model": "Heat Pump Controller",
            "manufacturer": "Econet",
            "via_device": "econet_mqtt_publisher"
        }

        for topic_name, config in self.ha_discovery_configs.items():
            # Determine component type based on device class or sensor type
            if config.get('device_class') == 'running' or 'payload_on' in config:
                component = 'binary_sensor'
            else:
                component = 'sensor'

            # Create unique ID for the entity
            unique_id = f"econet_{topic_name}"

            # Create discovery topic
            discovery_topic = f"homeassistant/{component}/{unique_id}/config"

            # Create state topic
            state_topic = f"{self.mqtt_topic_prefix}{topic_name}"

            # Build discovery payload
            discovery_payload = {
                "name": config['name'],
                "unique_id": unique_id,
                "state_topic": state_topic,
                "device": device_info,
                "icon": config.get('icon', 'mdi:gauge'),
                # MQTT availability
                "availability_topic": self.availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline"
            }

            # Only sensors (not binary_sensors) support expire_after
            if component == 'sensor':
                # Mark sensor unavailable if no update received within 4x polling interval
                discovery_payload['expire_after'] = self.polling_interval * 4

            # Add device class if specified
            if 'device_class' in config:
                discovery_payload['device_class'] = config['device_class']

            # Add unit of measurement if specified
            if 'unit_of_measurement' in config:
                discovery_payload['unit_of_measurement'] = config['unit_of_measurement']

            # Add state class if specified (enables long-term statistics in HA)
            if 'state_class' in config:
                discovery_payload['state_class'] = config['state_class']

            # Add binary sensor specific payloads
            if component == 'binary_sensor':
                if 'payload_on' in config:
                    discovery_payload['payload_on'] = config['payload_on']
                if 'payload_off' in config:
                    discovery_payload['payload_off'] = config['payload_off']

            # Add enum sensor specific options
            if config.get('device_class') == 'enum' and 'options' in config:
                discovery_payload['options'] = config['options']

            # Publish discovery message
            try:
                result = self.mqtt_client.publish(
                    discovery_topic,
                    json.dumps(discovery_payload),
                    retain=True
                )
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    logger.error(f"Failed to publish discovery for {topic_name}: {result.rc}")
            except Exception as e:
                logger.error(f"Error publishing discovery for {topic_name}: {e}")

        logger.info("Home Assistant discovery messages published")

    def _convert_valve_state(self, value: Any) -> str:
        """Convert three way valve numeric state to text"""
        if value == 0:
            return 'CH'
        elif value == 3:
            return 'DHW'
        else:
            return str(value)  # Return as string if unknown value

    def _publish_metrics(self, data: Dict[str, Any]):
        """Extract and publish all metrics to MQTT"""
        published_values = {}

        for topic_name, json_path in self.topic_mappings.items():
            value = self._get_nested_value(data, json_path)
            if value is not None:
                full_topic = f"{self.mqtt_topic_prefix}{topic_name}"
                try:
                    # Special handling for three way valve state
                    if topic_name == 'three_way_valve_state':
                        payload = self._convert_valve_state(value)
                    else:
                        # Convert value to string for MQTT publishing
                        payload = str(value)

                    result = self.mqtt_client.publish(full_topic, payload)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        published_values[topic_name] = payload  # Log the converted value
                    else:
                        logger.error(f"Failed to publish {topic_name}: {result.rc}")
                except Exception as e:
                    logger.error(f"Error publishing {topic_name}: {e}")
            else:
                logger.warning(f"Could not find value for {topic_name} at path {json_path}")

        # Log all published values
        if published_values:
            logger.info(f"Published values: {published_values}")
        else:
            logger.warning("No values were published")

    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def disconnect_mqtt(self):
        """Disconnect from MQTT broker"""
        # On clean shutdown, mark availability as offline
        try:
            self.mqtt_client.publish(self.availability_topic, "offline", retain=True)
        except Exception as e:
            logger.error(f"Failed to publish availability offline status: {e}")
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()

    def run(self):
        """Main execution loop"""
        logger.info("Starting Econet MQTT Publisher...")

        if not self.connect_mqtt():
            logger.error("Failed to connect to MQTT broker, exiting")
            sys.exit(1)

        # Publish Home Assistant discovery messages once on startup
        self._publish_ha_discovery()

        try:
            while self.running:
                logger.info("Polling Econet endpoint...")
                data = self._fetch_econet_data()

                if data:
                    self._publish_metrics(data)
                else:
                    logger.error("Failed to fetch data from Econet endpoint")

                # Wait for next polling interval
                for _ in range(self.polling_interval):
                    if not self.running:
                        break
                    time.sleep(1)

        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")

        finally:
            logger.info("Shutting down...")
            self.disconnect_mqtt()
            logger.info("Shutdown complete")

def main():
    publisher = EconetMQTTPublisher()
    publisher.run()

if __name__ == "__main__":
    main()
