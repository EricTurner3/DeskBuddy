import threading
import urllib.request
import json

OPEN_METEO_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}"
    "&current=temperature_2m,weather_code"
    "&temperature_unit=fahrenheit"
)

# Open-Meteo WMO weather codes collapsed into our 5 icon buckets
CODE_TO_CONDITION = {
    **{c: "clear" for c in (0, 1)},
    **{c: "cloudy" for c in (2, 3, 45, 48)},
    **{c: "rain" for c in (51, 53, 55, 61, 63, 65, 80, 81, 82)},
    **{c: "snow" for c in (71, 73, 75, 77, 85, 86)},
    **{c: "storm" for c in (95, 96, 99)},
}


def fetch_weather(lat, lon):
    url = OPEN_METEO_URL.format(lat=lat, lon=lon)
    with urllib.request.urlopen(url, timeout=10) as response:
        data = json.loads(response.read())
    current = data["current"]
    condition = CODE_TO_CONDITION.get(current["weather_code"], "cloudy")
    return condition, round(current["temperature_2m"])


def run_weather_poller(weather_state, lat, lon, stop_event, interval_seconds=600):
    while True:
        try:
            condition, temp_f = fetch_weather(lat, lon)
            weather_state.set(condition, temp_f)
            print(f"* Weather updated: {condition}, {temp_f}F")
        except Exception as error:
            print(f"! Weather fetch failed: {error}")
        if stop_event.wait(interval_seconds):
            return