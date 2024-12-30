# test_mqtt_client.py

import logging
import time
import os
from dotenv import load_dotenv
from helpers.custom_logger import setup_logging
from helpers import config
from helpers.mqtt_client import HomeAssistant_MQTT

def main():
    """
    Test function for the HomeAssistant_MQTT client.

    This function creates an instance of the HomeAssistant_MQTT client
    and keeps it running to test its functionality.
    """
    # Load environment variables
    load_dotenv()

    # Create a logger object
    logger_name = os.environ.get("LOGGER_NAME") or os.path.splitext(os.path.basename(__file__))[0]
    logger = setup_logging(logger_name=logger_name, log_level=logging.DEBUG)

    # Create a Config object
    config_instance = config.ConfigLoader("config.yaml")

    # Create an instance of the MQTT client
    logger.debug("Creating an instance of the HomeAssistant_MQTT class")
    ha_mqtt = HomeAssistant_MQTT(config_instance)

    # Send a test value (optional)
    ha_mqtt.send_value("my_meter", 27000.0)

    # Keep the client running to receive messages
    logger.debug("Waiting for messages... Hit Ctrl-C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Exiting...")

    # Disconnect the client
    ha_mqtt.disconnect_mqtt()

if __name__ == "__main__":
    main()