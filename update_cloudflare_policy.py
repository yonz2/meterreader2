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

# --------------------------------------

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
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }

    # Get the existing Access policy
    policy_url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/access/policies/{POLICY_ID}"
    try:
        response = requests.get(policy_url, headers=headers)
        response.raise_for_status()
        policy = response.json().get("result", {})
    except requests.exceptions.RequestException as e:
        print(f"Error fetching policy: {e}")
        return

    # Update the IP range in the policy
    for rule in policy.get('include', []):
        if 'ip' in rule:
            rule['ip'] = [f"{ip_address}/32"]

    # Send the updated policy back to Cloudflare
    try:
        response = requests.put(policy_url, headers=headers, json=policy)
        response.raise_for_status()
        print("Cloudflare Access policy updated successfully!")
    except requests.exceptions.RequestException as e:
        print(f"Error updating policy: {e}")


if __name__ == "__main__":
    current_ip = get_public_ip()
    if current_ip:
        update_cloudflare_access_policy(current_ip)
