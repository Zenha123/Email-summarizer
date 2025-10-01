from django.shortcuts import render


from django.shortcuts import render
from django.http import HttpResponse, FileResponse
from .forms import UploadEmailFileForm
import os
import json
import tempfile
import time
from google import genai
from google.genai import types
from django.conf import settings

MAX_RETRIES = 3

def load_and_split_emails(file_path: str):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
        emails = [e.strip() for e in content.split("\n---\n") if e.strip()]
        return emails

def create_summary_prompt(emails):
    json_schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "sender": {"type": "string"},
                "subject": {"type": "string"},
                "main_action_or_request": {"type": "string"},
                "deadline_or_priority": {"type": "string"},
                "summary": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["sender","subject","main_action_or_request","deadline_or_priority","summary"]
        }
    }
    instruction = (
        "You are an expert email summarization AI. Extract the most important details "
        "into strict JSON format: sender, subject, main_action_or_request, "
        "deadline_or_priority, and summary (3-4 bullet points). Return only JSON."
    )
    emails_text = "\n\n---\n\n".join(emails)
    return instruction, emails_text, json_schema

def call_gemini(client, instruction, emails_text, json_schema):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[emails_text],
                config=types.GenerateContentConfig(
                    system_instruction=instruction,
                    response_mime_type="application/json",
                    response_schema=json_schema,
                )
            )
            return json.loads(response.text)
        except Exception as e:
            if "503" in str(e) and attempt < MAX_RETRIES:
                time.sleep(5)
            else:
                raise



def home(request):
    summary_data = None
    form = UploadEmailFileForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        email_file = form.cleaned_data["email_file"]
        
        # Save uploaded file temporarily
        temp_file_path = os.path.join(tempfile.gettempdir(), email_file.name)
        with open(temp_file_path, 'wb+') as f:
            for chunk in email_file.chunks():
                f.write(chunk)
        
        # Load emails
        emails = load_and_split_emails(temp_file_path)
        
        # --- API Key ---
        api_key = os.getenv("GEMINI_API_KEY", "AIzaSyB8wJzq3W_tMc4yW51BH2HRe0pSdTlegaI")

        if not api_key:
            return HttpResponse(
                "⚠️ GEMINI_API_KEY is not set. Please set the environment variable.",
                status=500
            )
        
        # Call Gemini API
        client = genai.Client(api_key=api_key)
        instruction, emails_text, json_schema = create_summary_prompt(emails)
        summary_data = call_gemini(client, instruction, emails_text, json_schema)
        
        # Save JSON to media folder for download
        output_file_path = os.path.join(settings.MEDIA_ROOT, "summary.json")
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2)
        
        # summary_data = json.dumps(summary_data, indent=2)
    
    return render(request, 'home.html', {'form': form, 'summary_data': summary_data})

def download_file(request):
    file_path = os.path.join(settings.MEDIA_ROOT, "summary.json")
    return FileResponse(open(file_path, 'rb'), as_attachment=True, filename="summary.json")
