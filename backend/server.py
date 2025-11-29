# server.py
from flask import Flask, request, jsonify
import requests
from anthropic import Anthropic
import os
import json
import re
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
    # Read stored token file
    with open("ms_tokens.json", "r") as f:
        tokens = json.load(f)

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    # Return token if it exists
    if access_token:
        return access_token

    # Refresh if expired or missing
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

    # Save updated tokens
    with open("ms_tokens.json", "w") as f:
        json.dump(new_tokens, f)

    return new_tokens["access_token"]



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
    
    # Build dynamic instructions based on preferences
    ask_instructions = []
    if include_coffee_chat:
        ask_instructions.append("Request a quick coffee chat or 15-min call")
    if include_resume:
        ask_instructions.append("Mention that you've attached your resume for reference")
    
    if not ask_instructions:
        ask_instructions.append("Has a clear, low-pressure ask (advice or quick question)")
    
    ask_text = "\n".join(f"- {instruction}" for instruction in ask_instructions)
    
    prompt = f"""You are writing a cold outreach email as Krishiv Gubba, a junior at UW-Madison studying Computer Science and Data Science.

RECIPIENT'S LINKEDIN INFO:
Name: {profile.get('name')}
Headline: {profile.get('headline')}
About: {profile.get('about')}
Experiences: {profile.get('experiences')}

WRITE A SHORT EMAIL (4-6 sentences max) that:
- Opens with something SPECIFIC from their profile that genuinely caught your attention (a project, company, role, or something from their about section)
- Briefly mentions you're a CS/DS junior at UW-Madison
{ask_text}
- Ends naturally, not with corporate sign-offs

CRITICAL RULES:
- NO generic openers like "I hope this email finds you well" or "I came across your profile"
- NO phrases like "I was impressed by" or "Your journey is inspiring" 
- NO buzzwords like "leverage", "synergy", "ecosystem", "passionate about"
- NO exclamation points overload
- Write like you're texting a friend's older sibling who works in tech - respectful but not stiff
- Be specific. If they worked at Google on ML, mention that. If their about says they love hiking, don't mention it unless relevant.
- Sound like a real college student, not a LinkedIn influencer
- Keep it under 100 words

ALSO write a subject line that:
- Is short (5-8 words max)
- Is NOT corny or salesy (no "Quick question!" or "Let's connect!")
- References something specific about them or is straightforwardly direct
- Sounds like a real person wrote it

OUTPUT FORMAT: Return ONLY valid JSON in this exact format, no other text:
{{"subject": "your subject line here", "body": "your email body here"}}"""

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
    


@app.route('/send-email', methods=['POST'])
def send_email():
    data = request.get_json()
    if not data or 'emailBody' not in data or 'emailId' not in data:
        return jsonify({"error": "Missing required parameters: emailBody and emailId"}), 400

    email_body = data['emailBody']
    email_id = data['emailId']
    email_subject = data.get('subject', '')  # Subject is optional
    include_resume = data.get('includeResume', False)

    # Stub: logic to actually send the email would go here
    print(f"Sending email to: {email_id}")
    print(f"Subject: {email_subject}")
    print(f"Body:\n{email_body}")
    print(f"Include Resume: {include_resume}")

    # Respond with a success stub
    return jsonify({"success": True, "message": "Email send endpoint stub"}), 200



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
