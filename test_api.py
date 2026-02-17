"""Quick diagnostic to test API connection."""
import os
from dotenv import load_dotenv
from anthropic import Anthropic

# Load env
load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")

if not api_key:
    print("❌ No API key found in environment")
else:
    print(f"✓ API key loaded: {api_key[:20]}...")
    
    try:
        client = Anthropic(api_key=api_key)
        
        # Test simple call
        message = client.messages.create(
            model="claude-opus-4-5-20251101",
            max_tokens=100,
            messages=[
                {"role": "user", "content": "Return just the word 'test' as JSON: {\"result\": \"test\"}"}
            ]
        )
        
        print(f"✓ API connection successful!")
        print(f"Response: {message.content[0].text}")
        
    except Exception as e:
        print(f"❌ API call failed: {e}")
