import requests

# 🔧 Use your actual API key here
API_KEY = "a3dede8bbc12f4bd0afd61cf1ac691f3545d5faf"  # Replace with real API key
BASE_URL = "https://linkcents.com/api"  # LinkCents API endpoint

def create_short_link(code: str) -> str:
    try:
        # This dummy URL embeds the code so user sees it on destination page
        target_url = f"https://t.me/Anime_fetch_robot?code={code}"
        params = {
            "api": API_KEY,
            "url": target_url,
            "format": "json"
        }
        response = requests.get(BASE_URL, params=params)
        result = response.json()
        return result.get("shortenedUrl") or result.get("short", "⚠️ Failed to shorten")
    except Exception as e:
        print("Shortener error:", e)
        return "⚠️ Shortener failed"
