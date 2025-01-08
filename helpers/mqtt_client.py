# (c) 2024 Yonz
# License: Nonlicense
#
#  MQTT Client to handle connection to Home Assistant
#
# When called for the first time, a Homeassitant MQQT Sensor configuration topic is sent to HA. 
# The Sensor is configred based on a template stored in the config.yaml file
#
# All parameters are stored in the config.yaml file
#
# This script uses the Eclipse paho mqtt client library to communicate with the MQTT Broker, as well as the watchdog library to monitor file system changes.
# Both need to be installed using pip:
#    >pip install watchdog paho-mqtt
#
# For more detals see.
#   https://www.home-assistant.io/integrations/sensor.mqtt/
#   https://www.home-assistant.io/integrations/mqtt/#sensors
#
import os
import json
import time
import logging
import threading

from typing import Dict

import paho.mqtt.client as mqtt

# Import your custom modules
import helpers.config as config


# Set up logging
logger_name = os.environ.get("LOGGER_NAME") or os.path.splitext(os.path.basename(__file__))[0]
logger = logging.getLogger(logger_name)

# pylint: disable=w1203
# pylint: disable=C0103
class HomeAssistant_MQTT_Client:
    """
    MQTT client for interacting with Home Assistant.

    
    This client handles:
      - Connecting to the MQTT broker.
      - Subscribing to the Home Assistant birth topic.
      - Sending discovery messages for configured devices.
      - Publishing availability messages for devices.
      - Sending data values to Home Assistant.

    Attributes:
        config: Configuration object containing MQTT settings.
        devices: Dictionary of device configurations.
        HAisOnline: Boolean indicating if Home Assistant is online.
        client: Paho MQTT client object.
        connected_event: Threading event to signal connection status.
    """

    def __init__(self, config):
        """
        Initializes the HomeAssistant_MQTT client.

        Args:
            config: Configuration object.
        """
        self.config = config
        self.mqtt_broker = self.config.get('MQTT', 'broker')
        self.mqtt_port = int(self.config.get('MQTT', 'port'))
        self.mqtt_username = self.config.get('MQTT', 'username')
        self.mqtt_topic = self.config.get('MQTT', 'topic')
        self.mqtt_password = self.config.get('MQTT', 'password')
        self.qos = int(self.config.get('MQTT', 'qos', default=1))
        self.birth_topic = self.config.get('MQTT', 'birth_topic', default="homeassistant/status")

        self.devices: Dict[str, Dict] = self.config.get('MQTT', 'devices') or {}

        self.HAisOnline = False

        # Connect to the MQTT broker
        self.connect_mqtt()

        # Wait for connection to be established (with timeout)
        self.connected_event = threading.Event()
        self.connected_event.wait(timeout=5)

        # Send discovery messages for devices (if any)
        if self.devices and self.HAisOnline:
            self.send_discovery()
        else:
            logger.error("No devices defined in config.yaml - not sending discovery messages")

    def connect_mqtt(self):
        """Sets up the MQTT client and connects to the broker."""

        logger.debug("Connecting to MQTT Broker...")
        self.client = mqtt.Client(client_id="MQTT_Client.py", clean_session=True, userdata=None, protocol=mqtt.MQTTv311, transport="tcp")
        self.client.enable_logger()
        self.client.username_pw_set(self.mqtt_username, self.mqtt_password)

        # Assign callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish

        self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
        self.client.loop_start()
        self.HAisOnline = True

    def on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker."""

        logger.debug(f"Connected to MQTT broker, with result code {rc}")
        if rc == 0:
            logger.info("Connected to MQTT Broker!")
            self.client.subscribe(self.birth_topic)
            self.HAisOnline = True
            self.connected_event.set()  # Signal successful connection
        else:
            logger.error(f"Failed to connect, return code {rc}")
            self.HAisOnline = False

    def on_message(self, client, userdata, msg):
        """Callback for when a message is received."""
        try:
            logger.info(f"Received message: {msg.payload.decode()} on topic: {msg.topic}")

            if msg.topic == self.birth_topic:
                if msg.payload.decode() == "online":
                    if self.devices:
                        self.send_discovery()
                    self.HAisOnline = True
                elif msg.payload.decode() == "offline":
                    for device_id in self.devices:
                        self.publish_availability(device_id, "offline")
                    self.HAisOnline = False
            else:
                logger.info(f"No handler for messages on topic: {msg.topic}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def on_publish(self, client, userdata, mid):
        """Callback for when a message is published."""
        logger.debug(f"Message {mid} has been published.")

    def publish_availability(self, device_id: str, payload: str):
        """Publishes availability message for a device."""
        if device_id in self.devices:
            availability_topic = f"{self.mqtt_topic}/{device_id}/status"
            self.client.publish(availability_topic, payload=payload, qos=self.qos, retain=False)
            logger.debug(f"Published availability: {payload} to {availability_topic}")
        else:
            logger.warning(f"Device {device_id} not found in devices list.")

    def send_discovery(self):
        """Sends discovery messages for all configured devices."""
        for device_id, device_info in self.devices.items():
            config_topic = f"{self.mqtt_topic}/{device_id}/config"
            payload_str = json.dumps(device_info)
            self.client.publish(config_topic, payload=payload_str, qos=self.qos, retain=False)
            logger.debug(f"Published discovery message for {device_id} to {config_topic}")
            self.publish_availability(device_id, "online")

    def send_value(self, state_topic, value):
        """Sends a new value to Home Assistant."""

        # Check if state_topic is a full topic path or just an object_id
        if not state_topic.startswith(self.mqtt_topic):  # Not a full path
            state_topic = f"{self.mqtt_topic}/{state_topic}/state"  # Assemble full path

        epoch_timestamp = int(time.time())
        data = {
            "timestamp": epoch_timestamp,
            "timestamp_str": str(time.ctime()),
            "value": float(value),
        }
        json_payload_str = json.dumps(data)

        
        self.client.publish(state_topic, payload=json_payload_str, qos=self.qos, retain=False)
        logger.info(f"Published value: {json_payload_str} to topic: {state_topic}")

    def disconnect_mqtt(self):
        """Disconnects the MQTT client from the broker."""
        if self.devices:
            for device_id in self.devices:
                self.publish_availability(device_id, "offline")
        self.client.disconnect(reasoncode=0, properties=None)
        self.client.loop_stop()
        logger.info("Disconnected from MQTT Broker!")

def main():
    """
        This is just for testing the basic functionality of the MQTT client.
        to make sure it is created and can connect to the broker defined in config.yaml
        
        Complete test is in 'mqtt_client_test.py'
        Create a Config object
    """
    config_instance = config.ConfigLoader("config.yaml")

    ha_mqtt = HomeAssistant_MQTT_Client(config_instance)

    time.sleep(5)

    # Disconnect from the MQTT broker
    ha_mqtt.disconnect_mqtt()

if __name__ == "__main__":
    main()
