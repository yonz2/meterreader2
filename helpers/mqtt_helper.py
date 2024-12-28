# (c) 2024 Yonz
# License: Nonlicense
#
# Helper functions to manage the MQTT connection to Home Assistant
#
# When called for the first time, a Homeassitant MQQT Sensor configuration topic is sent to HA. 
# The Sensor is configred based on a template stored in the config_template.json file
#
# All parameters are stored in the config.json file
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
import yaml
import time
import paho.mqtt.client as mqtt

# Import your custom modules
import helpers.config as config 

# Make sure to use the same logger as therest of hte application
import logging
logger_name = os.environ.get("LOGGER_NAME") or os.path.splitext(os.path.basename(__file__))[0]
logger = logging.getLogger(logger_name)



class HomeAssistant_MQTT:
    def __init__(self, config, template_file="mqtt_config_template.json"):
        """
        Initializes the HomeAssistant_MQTT class.

        Args:
            config_file (str): Path to the configuration file. Defaults to "config.json".
            template_file (str): Path to the configuration template file. Defaults to "config_template.json".
        """
        self.config = config
        self.template_file = template_file


        self.mqtt_broker = self.config.get('MQTT', 'broker')
        self.mqtt_port = self.config.get('MQTT', 'port')
        self.mqtt_username = self.config.get('MQTT', 'username')
        self.mqtt_topic = self.config.get('MQTT', 'topic')
        self.mqtt_password = self.config.get('MQTT', 'password')
        self.tracked_devices = set(self.config.get('MQTT', 'tracked_devices'))
        # Connect to the MQTT Broker
        self.connect_mqtt()

    def connect_mqtt(self):
        """Sets up the MQTT client and connects to the broker."""
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.enable_logger()
        self.client.username_pw_set(self.mqtt_username, self.mqtt_password)
        self.client.connect(self.mqtt_broker, self.mqtt_port, 60)

    def new_device_config(self, new_device):
        """
        Creates a new device configuration in Home Assistant.

        Args:
            new_device (str): The ID of the new device.
        """
        new_device_id = f"{new_device}"

        with open(self.template_file, 'r') as f:
            templates = json.load(f)

        # Clear any old definition 
        for key, payload in reversed(templates.items()):
            config_topic = f"{self.mqtt_topic}/{new_device_id}/{key}/config"
            self.client.publish(config_topic, payload=None, retain=True)
            logger.info(f"Published: '<<None>>' to topic: {config_topic}")
            time.sleep(3)

        for key, payload in templates.items():
            payload_str = json.dumps(payload)
            payload = json.loads(payload_str)

            config_topic = f"{self.mqtt_topic}/{new_device_id}/{key}/config"
            payload_str = json.dumps(payload)
            self.client.publish(config_topic, payload=payload_str, retain=True)
            logger.info(f"Published: {json.dumps(payload)} to topic: {config_topic}")
            time.sleep(5)

    def send_value(self, device_id, value):
        """
        Sends a new value to Home Assistant.

        Args:
            device_id (str): The ID of the device.
            value (float): The value to send.
        """
        epoch_timestamp = int(time.time())

        data = {
            "timestamp": epoch_timestamp,
            "timestamp_str": str(time.ctime()),
            "value": float(value),
        }
        json_payload_str = json.dumps(data)

        topic = f"{self.mqtt_topic}/{device_id}/state"
        self.client.publish(topic, payload=json_payload_str)

        logger.info(f"Published: {json_payload_str} to topic: {topic}")


def main():
    # used to test the MQTT Integration

    # Create a Config object
    config_instance = config.ConfigLoader("config.yaml")

    # Create an instance of the class
    ha_mqtt = HomeAssistant_MQTT(config_instance, logger) 

    # # Create a new device configuration
    ha_mqtt.new_device_config("my_meter")  
    sensor_state_topic = "homeassistant/sensor/electricity_meter/state"
    xx = 'homeassistant/sensor/my_meter/Stromzaehler/config'
    # # Send a value to Home Assistant
    ha_mqtt.send_value("electricity_meter", 25000.0)



if __name__ == "__main__":
    main()
