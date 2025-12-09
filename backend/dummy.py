import requests
import os
from dotenv import load_dotenv

load_dotenv()

def get_email_from_linkedin(linkedin_url: str, api_key: str) -> dict:
    """
    Get email and contact info from a LinkedIn URL using Apollo's People Enrichment API.
    """
    url = "https://api.apollo.io/api/v1/people/match"
    
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "x-api-key": api_key
    }
    
    data = {
        "linkedin_url": linkedin_url,
        "reveal_personal_emails": True  # Set to True if you want personal emails
    }
    
    response = requests.post(url, headers=headers, json=data)
    print(response.json())
    return response.json()


if __name__ == "__main__": 
    API_KEY = os.getenv("APOLLO_API_KEY")
    LINKEDIN_URL = "https://www.linkedin.com/in/nikhil-gorrepati/"
    
    result = get_email_from_linkedin(LINKEDIN_URL, API_KEY)
    
    if result.get("person"):
        person = result["person"]
        print(f"Name: {person.get('name')}")
        print(f"Email: {person.get('email')}")
        print(f"Title: {person.get('title')}")
        print(f"Company: {person.get('organization', {}).get('name')}")
    else:
        print("No match found")
        print(result)