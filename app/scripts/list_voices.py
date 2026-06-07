# ...existing code...
import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

# ...existing code...
api_key = os.getenv("ELEVEN_API_KEY")
if not api_key:
    print("Error: ELEVEN_API_KEY not set. Add it to your .env or export it in the shell.")
    raise SystemExit(1)

client = ElevenLabs(api_key=api_key)

try:
    voices = client.voices.get_all()
except Exception as e:
    print(f"Error fetching voices from ElevenLabs: {e}")
    raise

for v in getattr(voices, "voices", []):
    vid = getattr(v, "voice_id", getattr(v, "id", "unknown"))
    name = getattr(v, "name", getattr(v, "voice_name", "unknown"))
    category = getattr(v, "category", getattr(v, "voice_type", "unknown"))
    print(f"ID: {vid} | Tên: {name} | Category: {category}")
# ...existing code...