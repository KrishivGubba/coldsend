# server.py
from flask import Flask, request, jsonify, request
from anthropic import Anthropic
import os
from dotenv import load_dotenv

load_dotenv()

from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # allows Chrome extension to call this backend

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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

Just output the email body. No subject line needed."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=350,
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    email = response.content[0].text

    output =  jsonify({"email": email})
    print(output)
    return output
    


@app.route('/send-email', methods=['POST'])
def send_email():
    data = request.get_json()
    if not data or 'emailBody' not in data or 'emailId' not in data:
        return jsonify({"error": "Missing required parameters: emailBody and emailId"}), 400

    email_body = data['emailBody']
    email_id = data['emailId']

    # Stub: logic to actually send the email would go here
    print(f"Sending email to {email_id} with body:\n{email_body}")

    # Respond with a success stub
    return jsonify({"success": True, "message": "Email send endpoint stub"}), 200



if __name__ == "__main__":
    app.run(port=3000, debug=True)
