import subprocess
import threading
import urllib.request
import json
from alert import speak

API_KEY = "f6bf7c9bed794f06acf51954262903"
CITY    = "Tampa"  # change to your city

def get_weather():
    url = f"http://api.weatherapi.com/v1/current.json?key={API_KEY}&q={CITY}"
    with urllib.request.urlopen(url) as r:
        data = json.loads(r.read())
    desc = data["current"]["condition"]["text"]
    temp = round(data["current"]["temp_f"])  # change to temp_c for Celsius
    return desc, temp

def greet():
    desc, temp = get_weather()
    message = f"Welcome. The weather is {desc}, {temp} degrees. Have a safe drive."
    print(message)
    speak(message)

_weather_cache = None

def get_weather_overlay():
    global _weather_cache
    if _weather_cache is None:
        _weather_cache = get_weather()  # reuses your existing function
    return _weather_cache