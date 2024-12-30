# (c) 2024 Yonz
# License: Nonlicense
#
# "render-yaml.py" renders a YAML file containing JINJA2 templates into a plain YAML file.
#
# use to generate the currect syntax for Homeassistant MQTT Client / Sesnor configuration
# <input_file> is the YAML file containing JINJA2 templates
# <output_file> is the resulting YAML file

# Usage: render-yaml.py <input_file> <output_file>
#
import sys
import os   
import yaml
from jinja2 import Environment, FileSystemLoader

def render_yaml_template(template_file, **kwargs):
    """Renders a YAML template and returns the data as a string."""
    try:
        env = Environment(loader=FileSystemLoader(searchpath='.'))
        template = env.get_template(template_file)
        rendered_yaml = template.render(**kwargs)
        return rendered_yaml
    except Exception as e:
        print(f"Error rendering YAML template: {e}")
        return {}   
    
def main():
    if len(sys.argv) != 3:
        print("Usage: render-yaml.py <input_file> <output_file>")
        sys.exit(1)
        
    input_file = sys.argv[1] # Template file to use (YAML with JINJA2 templates)
    output_file = sys.argv[2] # resulting ymal file
    
# define the parameters for the rendering
    params = {
        "device_name": "my-meter",
        "main_topic": 'homeassistant/sensor',
        "device_class": "energy",
        "state_class": "total_increasing",
        "mes_unit": "kWh",
        "main_device": True,
    }

    try:
        rendered_template = render_yaml_template(input_file, **params)
        output_yaml = yaml.safe_load(rendered_template)
    except yaml.YAMLError as e:
        print(f"Error rendering / parsing YAML file {input_file}: {e}. Exiting...")
        sys.exit(1)

    try:
        with open(output_file, "w") as f:
            f.write(rendered_template)
    except yaml.YAMLError as e:
        print(f"Error writing YAML file {output_file}: {e}. Exiting...")
        sys.exit(1)
    
    print(f"Rendered YAML template to {output_file}")

if __name__ == "__main__":
    main()

