import requests
import os
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
import uuid
x = str(uuid.uuid4())
print(x)

data = {
    "user_id": x,
    "image_url": "https://test.com/thumbnail.png"
}

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

response = requests.post(
    f"{SUPABASE_URL}/rest/v1/thumbnail_usage",
    headers=headers,
    json=data
)

print(response.status_code, response.text)
