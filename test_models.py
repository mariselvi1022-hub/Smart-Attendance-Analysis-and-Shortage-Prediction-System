import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ GEMINI_API_KEY is missing from your .env file.")
else:
    try:
        client = genai.Client(api_key=api_key)
        print("✅ Successfully connected! Available Gemini models:\n")
        
        for model in client.models.list():
            if "gemini" in model.name.lower():
                print(f" • {model.name}")

    except Exception as e:
        print(f"❌ Error fetching models: {e}")