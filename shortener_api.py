# LinkCents Shortener API integration
import requests

API_KEY = "a3dede8bbc12f4bd0afd61cf1ac691f3545d5faf"  # Replace this with your actual API key

def create_short_link(code):
    url = "https://linkcents.com/api"
    params = {
        "api": API_KEY,
        "url": f"https://t.me/Anime_fetch_robot?start={code}",
        "format": "json"
    }
    try:
        res = requests.get(url, params=params).json()
        return res["shortenedUrl"] if "shortenedUrl" in res else "Shortening failed"
    except:
        return "Shortening error"

