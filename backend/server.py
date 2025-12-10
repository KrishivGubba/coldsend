# server.py
from flask import Flask, request, jsonify
import requests
from anthropic import Anthropic
import os
import json
import re
import base64
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # allows Chrome extension to call this backend

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")) #TODO: user input here.

# Dev mode - set to True to load settings from dev_settings.json automatically
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

# In-memory storage for user settings
user_settings = {
    "userName": None,
    "userAbout": None,
    "apiKey": None,
    "signatureHtml": None,
    "resumePath": None,
    "apolloApiKey": None
}


def load_dev_settings():
    """Load settings from dev_settings.json if in dev mode."""
    if not DEV_MODE:
        return
    try:
        with open("backend/dev_settings.json", "r") as f:
            saved = json.load(f)
            user_settings.update(saved)
            print("✅ DEV MODE: Loaded settings from dev_settings.json")
    except FileNotFoundError:
        print("⚠️  DEV MODE: dev_settings.json not found - create it with your settings")
    except json.JSONDecodeError:
        print("⚠️  DEV MODE: dev_settings.json is invalid JSON")


# Load dev settings on startup
load_dev_settings()


@app.route("/save-settings", methods=["POST"])
def save_settings():
    """Save user settings to memory."""
    data = request.get_json()
    
    if data.get("userName"):
        user_settings["userName"] = data["userName"]
    if data.get("userAbout"):
        user_settings["userAbout"] = data["userAbout"]
    if data.get("apiKey"):
        user_settings["apiKey"] = data["apiKey"]
    if data.get("signatureHtml"):
        user_settings["signatureHtml"] = data["signatureHtml"]
    if data.get("resumePath"):
        user_settings["resumePath"] = data["resumePath"]
    if data.get("apolloApiKey"):
        user_settings["apolloApiKey"] = data["apolloApiKey"]
    
    print(f"Settings saved: userName={user_settings['userName']}, userAbout={bool(user_settings['userAbout'])}, apiKey={'*' * 10 if user_settings['apiKey'] else 'None'}, signatureHtml={bool(user_settings['signatureHtml'])}, resumePath={user_settings['resumePath']}, apolloApiKey={'*' * 10 if user_settings['apolloApiKey'] else 'None'}")
    
    return jsonify({"success": True})


@app.route("/query-apollo", methods=["POST"])
def query_apollo():
    """Query Apollo API to get email from LinkedIn URL."""
    # Check if Apollo API key is configured
    if not user_settings["apolloApiKey"]:
        return jsonify({"error": "Apollo API key not configured", "code": "SETTINGS_NOT_CONFIGURED"}), 400
    
    data = request.get_json()
    linkedin_url = data.get("linkedinUrl")
    
    if not linkedin_url:
        return jsonify({"error": "LinkedIn URL is required"}), 400
    
    try:
        url = "https://api.apollo.io/api/v1/people/match"
        
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "x-api-key": user_settings["apolloApiKey"]
        }
        
        payload = {
            "linkedin_url": linkedin_url,
            "reveal_personal_emails": True
        }
        
        response = requests.post(url, headers=headers, json=payload)
        result = response.json()
        
        if result.get("person"):
            person = result["person"]
            return jsonify({
                "success": True,
                "email": person.get("email"),
                "name": person.get("name"),
                "title": person.get("title"),
                "company": person.get("organization", {}).get("name") if person.get("organization") else None
            })
        else:
            return jsonify({
                "success": False,
                "error": "No match found in Apollo"
            })
            
    except Exception as e:
        print(f"Error querying Apollo: {e}")
        return jsonify({"error": str(e)}), 500

mic_client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
mic_tenant_id = os.getenv("MICROSOFT_TENANT_ID")
mic_client_id = os.getenv("MICROSOFT_CLIENT_ID")

endpoint = f"https://login.microsoftonline.com/{mic_tenant_id}/oauth2/v2.0/token"


def get_access_token():
    """Get the current access token from storage."""
    try:
        with open("ms_tokens.json", "r") as f:
            tokens = json.load(f)
        return tokens.get("access_token")
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def refresh_access_token():
    """
    Refresh the access token using the stored refresh token.
    Saves new tokens to ms_tokens.json and returns the new access token.
    """
    try:
        with open("ms_tokens.json", "r") as f:
            tokens = json.load(f)
        
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            print("No refresh token found")
            return None

        refresh_payload = {
            "client_id": mic_client_id,
            "client_secret": mic_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "redirect_uri": "http://localhost:3000/auth/callback",
            "scope": "Mail.Send offline_access openid profile"
        }

        res = requests.post(endpoint, data=refresh_payload)
        new_tokens = res.json()

        if "error" in new_tokens:
            print(f"Token refresh failed: {new_tokens}")
            return None

        # Save updated tokens to file
        with open("ms_tokens.json", "w") as f:
            json.dump(new_tokens, f)

        print("Access token refreshed successfully")
        return new_tokens.get("access_token")

    except Exception as e:
        print(f"Error refreshing token: {e}")
        return None


# Path to your resume file - update this to your actual resume location
RESUME_PATH = os.getenv("RESUME_PATH", "resume.pdf") #TODO: user input here.


def get_next_working_day_9am_cst():
    """
    Calculate the next working day (Mon-Fri) at 9:00 AM CST.
    Returns ISO 8601 formatted datetime string in UTC.
    """
    cst = ZoneInfo("America/Chicago")
    now = datetime.now(cst)
    
    # Start with tomorrow
    next_day = now + timedelta(days=1)
    
    # Skip weekends (Saturday=5, Sunday=6)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    
    # Set to 9:00 AM CST
    scheduled_time = next_day.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # Convert to UTC for Microsoft Graph API
    utc_time = scheduled_time.astimezone(ZoneInfo("UTC"))
    
    # Return in ISO 8601 format
    return utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")


def get_resume_attachment():
    """
    Read and base64 encode the resume file for email attachment.
    Returns attachment dict for Microsoft Graph API, or None if file doesn't exist.
    """
    if not os.path.exists(RESUME_PATH):
        print(f"Resume file not found at: {RESUME_PATH}")
        return None
    
    try:
        with open(RESUME_PATH, "rb") as f:
            file_content = f.read()
        
        # Get filename from path
        filename = os.path.basename(RESUME_PATH)
        
        # Determine content type based on extension
        ext = filename.lower().split('.')[-1]
        content_types = {
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        content_type = content_types.get(ext, 'application/octet-stream')
        
        # Base64 encode the file
        encoded_content = base64.b64encode(file_content).decode('utf-8')
        
        return {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": filename,
            "contentType": content_type,
            "contentBytes": encoded_content
        }
    except Exception as e:
        print(f"Error reading resume file: {e}")
        return None


def parse_email_response(response_text):
    """
    Parse LLM response to extract subject and body.
    Expects JSON format: {"subject": "...", "body": "..."}
    Falls back to treating entire response as body if JSON parsing fails.
    """
    # Try to extract JSON from the response
    try:
        # Look for JSON in the response (might have extra text around it)
        json_match = re.search(r'\{[\s\S]*"subject"[\s\S]*"body"[\s\S]*\}', response_text)
        if json_match:
            json_str = json_match.group()
            parsed = json.loads(json_str)
            return {
                "subject": parsed.get("subject", "").strip(),
                "body": parsed.get("body", "").strip()
            }
    except (json.JSONDecodeError, AttributeError):
        pass
    
    # Fallback: try to find subject and body with different patterns
    try:
        # Try pattern like "Subject: ...\n\nBody: ..."
        subject_match = re.search(r'[Ss]ubject:\s*(.+?)(?:\n|$)', response_text)
        if subject_match:
            subject = subject_match.group(1).strip()
            # Everything after subject line is body
            body_start = subject_match.end()
            body = response_text[body_start:].strip()
            # Remove "Body:" prefix if present
            body = re.sub(r'^[Bb]ody:\s*', '', body).strip()
            return {"subject": subject, "body": body}
    except:
        pass
    
    # Final fallback: no subject, entire response is body
    return {
        "subject": "",
        "body": response_text.strip()
    }

@app.route("/generate-email", methods=["POST"])
def generate_email():
    # Check if required settings are configured
    if not user_settings["apiKey"]:
        return jsonify({"error": "API key not configured", "code": "SETTINGS_NOT_CONFIGURED"}), 400
    if not user_settings["userName"]:
        return jsonify({"error": "User name not configured", "code": "SETTINGS_NOT_CONFIGURED"}), 400
    if not user_settings["userAbout"]:
        return jsonify({"error": "User about info not configured", "code": "SETTINGS_NOT_CONFIGURED"}), 400
    
    profile = request.json  # LinkedIn data
    
    # Get preferences
    include_resume = profile.get('includeResume', False)
    include_coffee_chat = profile.get('includeCoffeeChat', False)
    custom_instructions = profile.get('customInstructions', '').strip()
    
    # Build dynamic instructions based on preferences
    ask_instructions = []
    if include_coffee_chat:
        ask_instructions.append("Request a quick coffee chat or 15-min call")
    if include_resume:
        ask_instructions.append("Mention that you've attached your resume for reference")
    
    if not ask_instructions:
        ask_instructions.append("Has a clear, low-pressure ask (advice or quick question)")
    
    ask_instructions_text = "\n".join(f"- {instruction}" for instruction in ask_instructions)
    
    # Add custom instructions section if provided
    custom_instructions_section = ""
    if custom_instructions:
        custom_instructions_section = f"""
    CUSTOM INSTRUCTIONS (IMPORTANT - incorporate these into the email):
    {custom_instructions}
    """

    prompt = f"""
    You are writing a cold outreach email as **{user_settings["userName"]}**, {user_settings["userAbout"]}.

    You MUST follow this exact structure:

    1. **Opening line:**  
    Hi <FIRSTNAME>!

    2. **1 sentence:**  
    A short intro about me based on this: "{user_settings["userAbout"]}"

    3. **4-5 sentences:**  
    A personal hook based on something specific from their LinkedIn (from their About, Experiences, or Headline).  
    This should feel natural, like "I saw you've been working on X…" or "I noticed you built X at Y…".

    4. **1–2 sentences (the ask):**  
    {ask_instructions_text}

    5. **Ending:**
    Do NOT include any sign-off (no "Best", "Thanks", name, etc.). The signature will be added automatically.
    {custom_instructions_section}
    OTHER RULES:
    - KEEP IT UNDER 100 WORDS.
    - DO NOT use generic openers ("I hope you're doing well", "I came across your profile").
    - DO NOT use cringe phrases ("inspiring", "passionate about", "leverage", "synergy", etc.).
    - DO NOT overpraise or sound like a LinkedIn influencer.
    - MUST sound like a normal person writing a human email.
    - Tone: friendly + casual but respectful. Think "texting a friend's older sibling who works in tech."

    RECIPIENT'S LINKEDIN INFO:
    Name: {profile.get('name')}
    Headline: {profile.get('headline')}
    About: {profile.get('about')}
    Experiences: {profile.get('experiences')}
    
    SUBJECT LINE RULES:
    - 5–7 words max.
    - NOT salesy or corny.
    - Should reference something from their profile OR be direct and simple.

    OUTPUT FORMAT:
    Return ONLY valid JSON in this exact shape:
    {{
        "subject": "your subject line here",
        "body": "your email body here"
    }}
    """

    anthropic_client = Anthropic(api_key=user_settings["apiKey"])
    print("Prompt: ", prompt)
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=450,
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    raw_response = response.content[0].text
    print("Raw response: ", raw_response)
    parsed = parse_email_response(raw_response)
    print("Parsed: ", parsed)

    output = jsonify({
        "email": parsed["body"],
        "subject": parsed["subject"]
    })
    return output


@app.route("/generate-connection-message", methods=["POST"])
def generate_connection_message():
    # Check if required settings are configured
    if not user_settings["apiKey"]:
        return jsonify({"error": "API key not configured", "code": "SETTINGS_NOT_CONFIGURED"}), 400
    if not user_settings["userName"]:
        return jsonify({"error": "User name not configured", "code": "SETTINGS_NOT_CONFIGURED"}), 400
    if not user_settings["userAbout"]:
        return jsonify({"error": "User about info not configured", "code": "SETTINGS_NOT_CONFIGURED"}), 400
    
    profile = request.json
    
    custom_instructions = profile.get('customInstructions', '').strip()
    
    custom_section = ""
    if custom_instructions:
        custom_section = f"""
    CUSTOM INSTRUCTIONS (incorporate these):
    {custom_instructions}
    """
    
    prompt = f"""
    You are writing a LinkedIn connection request note as **{user_settings["userName"]}**, {user_settings["userAbout"]}.

    STRICT RULES:
    - MUST be under 300 characters (LinkedIn's limit)
    - 2-3 sentences MAX
    - Start with "Hi <FIRSTNAME>!" 
    - Reference ONE specific thing from their profile (role, company, project, etc.)
    - End with a simple ask or expression of interest
    - NO generic phrases like "I'd love to connect" or "expanding my network"
    - Sound like a real person, not a salesperson
    - Be casual but respectful
    {custom_section}
    RECIPIENT'S LINKEDIN INFO:
    Name: {profile.get('name')}
    Headline: {profile.get('headline')}
    About: {profile.get('about')}
    Experiences: {profile.get('experiences')}

    OUTPUT:
    Return ONLY the connection note text. No quotes, no JSON, just the raw message.
    """

    anthropic_client = Anthropic(api_key=user_settings["apiKey"])
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )

    message = response.content[0].text.strip()
    
    # Ensure it's under 300 chars
    if len(message) > 300:
        message = message[:297] + "..."
    
    print(f"Generated connection message ({len(message)} chars): {message}")
    return jsonify({"message": message})


def send_mail_request(access_token, message):
    """Helper to make the actual Graph API request."""
    graph_url = "https://graph.microsoft.com/v1.0/me/sendMail"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    return requests.post(graph_url, headers=headers, json=message)


def format_email_as_html(body_html, signature_html):
    """
    Wrap HTML email body with signature.
    Body is already HTML from the frontend (contenteditable div).
    """
    # Add spacing between body and signature
    return f"<html><body>{body_html}<br><br>{signature_html}</body></html>"


@app.route('/send-email', methods=['POST'])
def send_email():
    try:
        data = request.get_json()

        if not data or 'emailBody' not in data or 'emailId' not in data:
            return jsonify({"error": "Missing required parameters: emailBody and emailId"}), 400

        # Check if signature is configured
        if not user_settings["signatureHtml"]:
            return jsonify({"error": "Email signature not configured", "code": "SETTINGS_NOT_CONFIGURED"}), 400

        email_body = data['emailBody']
        email_id = data['emailId']
        email_subject = data.get('subject', '')
        include_resume = data.get('includeResume', False)
        schedule_send = data.get('scheduleSend', False)
        
        # Check if resume path is configured when trying to attach resume
        if include_resume and not user_settings["resumePath"]:
            return jsonify({"error": "Resume path not configured", "code": "SETTINGS_NOT_CONFIGURED"}), 400

        access_token = get_access_token()
        
        if not access_token:
            return jsonify({"error": "No access token found. Please authenticate first."}), 401

        # Convert email body to HTML with signature
        html_body = format_email_as_html(email_body, user_settings["signatureHtml"])

        message = {
            "message": {
                "subject": email_subject,
                "body": {
                    "contentType": "HTML",
                    "content": html_body
                },
                "toRecipients": [
                    {"emailAddress": {"address": email_id}}
                ]
            },
            "saveToSentItems": "true"
        }

        # Add deferred send time if scheduling (9 AM CST next working day)
        if schedule_send:
            deferred_time = get_next_working_day_9am_cst()
            message["message"]["singleValueExtendedProperties"] = [
                {
                    "id": "SystemTime 0x3FEF",  # PidTagDeferredSendTime
                    "value": deferred_time
                }
            ]
            print(f"Email scheduled for: {deferred_time}")

        # Attach resume if requested
        if include_resume:
            attachment = get_resume_attachment()
            if attachment:
                message["message"]["attachments"] = [attachment]
                print(f"Attaching resume: {attachment['name']}")
            else:
                print("Warning: includeResume was true but no resume file found")

        # First attempt
        res = send_mail_request(access_token, message)

        # Check if token expired (401 Unauthorized)
        if res.status_code == 401:
            res_json = res.json()
            error_code = res_json.get("error", {}).get("code", "")
            
            if error_code == "InvalidAuthenticationToken" or "expired" in str(res_json).lower():
                print("Access token expired, refreshing...")
                
                # Refresh the token
                new_token = refresh_access_token()
                
                if new_token:
                    # Retry with new token
                    res = send_mail_request(new_token, message)
                else:
                    return jsonify({"error": "Failed to refresh token. Please re-authenticate."}), 401

        # Check final result
        if res.status_code == 202:
            return jsonify({"success": True}), 200
        else:
            return jsonify({"error": res.text}), 400
            
    except Exception as e:
        print(f"Error sending email: {e}")
        return jsonify({"error": str(e)}), 500




#MICROSOFT STUFF

from urllib.parse import urlencode

@app.route("/auth/login")
def auth_login():
    params = {
        "client_id": mic_client_id,
        "response_type": "code",
        "redirect_uri": "http://localhost:3000/auth/callback",
        "response_mode": "query",
        "scope": "Mail.Send offline_access openid profile",
        "state": "xyz123"  # can be anything
    }
    auth_url = (
        f"https://login.microsoftonline.com/{mic_tenant_id}/oauth2/v2.0/authorize?"
        + urlencode(params)
    )
    return jsonify({"auth_url": auth_url})


@app.route("/auth/callback")
def auth_callback():
    code = request.args.get("code")
    if not code:
        return "No code provided", 400

    token_payload = {
        "client_id": mic_client_id,
        "client_secret": mic_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": "http://localhost:3000/auth/callback",
        "scope": "Mail.Send offline_access openid profile"
    }

    token_res = requests.post(endpoint, data=token_payload)
    token_json = token_res.json()

    # Save tokens (TEMP: to a file — change to DB later)
    with open("ms_tokens.json", "w") as f:
        json.dump(token_json, f)

    return "Login successful — you can close this window."


if __name__ == "__main__":
    app.run(port=3000, debug=True)
