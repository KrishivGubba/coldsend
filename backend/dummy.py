import os
from dotenv import load_dotenv
import requests

load_dotenv()

mic_client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
mic_tenant_id = os.getenv("MICROSOFT_TENANT_ID")
mic_client_id = os.getenv("MICROSOFT_CLIENT_ID")

endpoint = f"https://login.microsoftonline.com/{mic_tenant_id}/oauth2/v2.0/token"

payload = {
    "grant_type": "client_credentials",
    "client_id": mic_client_id,
    "client_secret": mic_client_secret,
    "scope": "https://graph.microsoft.com/.default"
}

response = requests.post(endpoint, data=payload)
print(response.json())