# (c) 2025 Yonz
# License NonLicense
#
# This script updates a Cloudflare Access policy with your current public IP address.
# It assumes that the policy uses a simple IP range rule.
# Modify the script as needed to match your policy configuration.
#
import os
from dotenv import load_dotenv
import requests
from cloudflare import Cloudflare

load_dotenv()

# --- Replace with your actual values or set them as environment variables ---
API_TOKEN = os.getenv('CF_API_TOKEN', 'your-api-token')
ACCOUNT_ID = os.getenv('CLOUDFLARE_ACCOUNT_ID', 'your-account-id')
POLICY_ID = os.getenv('CLOUDFLARE_POLICY_ID', 'your-policy-id')

BASE_URL = "https://api.cloudflare.com/client/v4"



def get_public_ip():
    """Fetches your current public IP address."""
    try:
        response = requests.get('https://api.ipify.org')
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error getting public IP: {e}")
        return None

def update_cloudflare_access_policy(ip_address):
    """Updates the Cloudflare Access policy with the new IP address."""
    try:
        client = Cloudflare(
            # This is the default and can be omitted
            api_email=os.environ.get("CLOUDFLARE_EMAIL"),
            # This is the default and can be omitted
            api_key=os.environ.get("CLOUDFLARE_API_KEY"),
        )
    except Exception as e:
        print(f"Error creating Cloudflare client: {e}")
        return

    try:
        # Get the existing Access policy
        policy = client.accounts.access.policies(ACCOUNT_ID, POLICY_ID).get()

        # Assuming your policy uses a simple IP range rule, modify as needed
        for rule in policy['include']:
            if 'ip_range' in rule:
                rule['ip_range'] = f"{ip_address}/32" 

        # Update the policy
        client.accounts.access.policies(ACCOUNT_ID, POLICY_ID).put(data=policy)
        print("Cloudflare Access policy updated successfully!")

    except Exception as e:
        print(f"Error updating Cloudflare Access policy: {e}")

if __name__ == "__main__":
    current_ip = get_public_ip()
    if current_ip:
        update_cloudflare_access_policy(current_ip)