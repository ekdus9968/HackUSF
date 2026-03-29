import subprocess
import threading
import urllib.request
import json
import os
import ssl

from dotenv import load_dotenv
from alert import speak

ssl._create_default_https_context = ssl._create_unverified_context

load_dotenv()
API_KEY = os.getenv("WEATHERAPI_KEY")
TOMTOM_KEY = os.getenv("TOMTOM_KEY")
CITY = "Tampa"  # change to your city

def get_weather():
    url = f"http://api.weatherapi.com/v1/current.json?key={API_KEY}&q={CITY}"
    with urllib.request.urlopen(url) as r:
        data = json.loads(r.read())

    desc = data["current"]["condition"]["text"]
    temp = round(data["current"]["temp_f"])  # change to temp_c for Celsius
    return desc, temp

def get_traffic():
    # TomTom flow API for Tampa area (lat/lng)
    lat, lng = 27.9506, -82.4572
    url = (
        "https://api.tomtom.com/traffic/services/4/flowSegmentData/"
        f"absolute/10/json?point={lat},{lng}&key={TOMTOM_KEY}"
    )
    with urllib.request.urlopen(url) as r:
        data = json.loads(r.read())

    flow = data["flowSegmentData"]
    current_speed = flow["currentSpeed"]
    free_flow_speed = flow["freeFlowSpeed"]
    ratio = current_speed / free_flow_speed

    if ratio > 0.8:
        return "light"
    elif ratio > 0.5:
        return "moderate"
    else:
        return "heavy"

def greet():
    def _greet():
        desc, temp = get_weather()
        traffic = get_traffic()
        message = (
            f"Hey! The weather today in Tampa is {desc}, {temp} degrees. "
            f"Traffic is currently {traffic}. Have a safe drive!"
        )
        print(message)
        speak(message)

    threading.Thread(target=_greet, daemon=True).start()

_weather_cache = None

def get_weather_overlay():
    global _weather_cache
    if _weather_cache is None:
        _weather_cache = get_weather()  # reuses your existing function
    return _weather_cache