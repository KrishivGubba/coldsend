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

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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
RESUME_PATH = os.getenv("RESUME_PATH", "resume.pdf")


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
    You are writing a cold outreach email as **Krishiv Gubba**, a junior at UW–Madison studying Computer Science and Data Science.

    You MUST follow this exact structure:

    1. **Opening line:**  
    Hi <FIRSTNAME>!

    2. **1 sentence:**  
    A short intro about me: "I'm a CS/DS junior at UW–Madison."

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
    - MUST sound like a normal college student writing a human email.
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


    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=450,
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    raw_response = response.content[0].text
    parsed = parse_email_response(raw_response)

    output = jsonify({
        "email": parsed["body"],
        "subject": parsed["subject"]
    })
    print(output)
    return output


@app.route("/generate-connection-message", methods=["POST"])
def generate_connection_message():
    profile = request.json
    
    custom_instructions = profile.get('customInstructions', '').strip()
    
    custom_section = ""
    if custom_instructions:
        custom_section = f"""
    CUSTOM INSTRUCTIONS (incorporate these):
    {custom_instructions}
    """
    
    prompt = f"""
    You are writing a LinkedIn connection request note as **Krishiv Gubba**, a junior at UW–Madison studying Computer Science and Data Science.

    STRICT RULES:
    - MUST be under 300 characters (LinkedIn's limit)
    - 2-3 sentences MAX
    - Start with "Hi <FIRSTNAME>!" 
    - Reference ONE specific thing from their profile (role, company, project, etc.)
    - End with a simple ask or expression of interest
    - NO generic phrases like "I'd love to connect" or "expanding my network"
    - Sound like a real college student, not a salesperson
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

    response = client.messages.create(
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


def format_email_as_html(body_text):
    """
    Convert plain text email body to HTML and add signature.
    """
    # Convert plain text to HTML (escape special chars and convert newlines)
    html_body = body_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    html_body = html_body.replace('\n', '<br>\n')
    
    # Add the signature
    signature = """
<br><br>
Best,<br>
<br>
<b>Krishiv Gubba</b><br>
B.S. in Computer Science and Data Science<br>
University of Wisconsin-Madison<br>
<a href="mailto:kgubba@wisc.edu">kgubba@wisc.edu</a><br>
<a href="https://www.linkedin.com/in/krishiv-gubba/">LinkedIn</a> | <a href="https://github.com/KrishivGubba">GitHub</a>
"""
    
    return f"<html><body>{html_body}{signature}</body></html>"


@app.route('/send-email', methods=['POST'])
def send_email():
    try:
        data = request.get_json()

        if not data or 'emailBody' not in data or 'emailId' not in data:
            return jsonify({"error": "Missing required parameters: emailBody and emailId"}), 400

        email_body = data['emailBody']
        email_id = data['emailId']
        email_subject = data.get('subject', '')
        include_resume = data.get('includeResume', False)
        schedule_send = data.get('scheduleSend', False)

        access_token = get_access_token()
        
        if not access_token:
            return jsonify({"error": "No access token found. Please authenticate first."}), 401

        # Convert email body to HTML with signature
        html_body = format_email_as_html(email_body)

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
