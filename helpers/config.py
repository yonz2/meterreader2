# (c) 2024 Yonz
# License: Non License
# 
# Read a YAML File containing configuration parameters into a dictionary.
#
# Methods: "get(variable)" : returns the value of the given variable 
#
import yaml
import os

class ConfigLoader:
    def __init__(self, config_file="config.yaml"):
        """
        Initialize the ConfigLoader with the path to the configuration file.
        :param config_file: Path to the YAML configuration file.
        """
        # if defined use the value defined in ENV, else default to config.yaml in current directory 
        self.config_path = os.environ.get('CONFIG_FILE')
        if not self.config_path:
            self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),config_file)
        self.config_data = self.load_config()

    def load_config(self):
        """
        Load configuration data from a YAML file into a dictionary.
        """
        
        try:
            with open(self.config_path, "r") as f:
                config_data = yaml.safe_load(f)  # Use safe_load for security.
                print(f"Loaded configuration from {self.config_path}")
                return config_data
        except FileNotFoundError:
            print(f"Configuration file {self.config_path} not found. Exiting...")
            exit()
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file {self.config_path}: {e}. Exiting...")
            exit()

    def get(self, topic, key, default=None):
        """
        Get a configuration value by topic and key, with an optional default.

        :param topic: The topic (section) in the configuration.
        :param key: The key to retrieve from the configuration.
        :param default: The default value if the key is not found.
        :return: The value associated with the key, or the default value.
        """
        topic_data = self.config_data.get(topic)
        if topic_data:
            return topic_data.get(key, default)
        return default
        
    def print_config(self):
        """
        Prints the loaded configuration data in YAML format.
        """
        try:
            print(yaml.dump(self.config_data, indent=2))  # Use dump to output YAML
        except yaml.YAMLError as e:
            print(f"Error dumping YAML: {e}")


if __name__ == "__main__":
    # Example usage
    config = ConfigLoader()
    print("The loaded configuration:")
    config.print_config()

