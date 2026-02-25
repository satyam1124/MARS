"""
weather.py — Weather information skills for MARS.

All functions return a ``str`` response that MARS speaks aloud.
Requires the ``OPENWEATHERMAP_API_KEY`` environment variable.

Functions
---------
get_current_weather   : Current conditions for a city (or auto-detected).
get_weather_forecast  : Multi-day forecast for a city.
"""

from __future__ import annotations

import os
import urllib.parse

import requests

from utils.logger import get_logger

log = get_logger(__name__)

_OWM_BASE = "https://api.openweathermap.org/data/2.5"
_TIMEOUT = 10


def _get_api_key() -> str | None:
    """Return the OpenWeatherMap API key from the environment."""
    return os.environ.get("OPENWEATHERMAP_API_KEY")


def _resolve_city(city: str) -> str:
    """Return the actual city name, auto-detecting via ip-api.com if needed."""
    if city.lower() == "auto":
        try:
            resp = requests.get("http://ip-api.com/json/", timeout=5)
            data = resp.json()
            return data.get("city", "London")
        except Exception:
            return "London"
    return city


def _wind_direction(degrees: float) -> str:
    """Convert wind bearing in degrees to a compass direction string."""
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    index = round(degrees / 45) % 8
    return directions[index]


# ---------------------------------------------------------------------------
# get_current_weather
# ---------------------------------------------------------------------------


def get_current_weather(city: str = "auto") -> str:
    """Return a spoken summary of current weather conditions.

    Parameters
    ----------
    city:
        City name, e.g. ``"London"``.  Pass ``"auto"`` to detect the city
        from the machine's public IP address.

    Returns
    -------
    str
        Human-readable current weather description, or an error message.
    """
    api_key = _get_api_key()
    if not api_key:
        return (
            "Weather is unavailable. Please set the OPENWEATHERMAP_API_KEY "
            "environment variable."
        )

    resolved_city = _resolve_city(city)
    encoded_city = urllib.parse.quote(resolved_city)
    url = (
        f"{_OWM_BASE}/weather"
        f"?q={encoded_city}&appid={api_key}&units=metric"
    )
    try:
        response = requests.get(url, timeout=_TIMEOUT)
        if response.status_code == 404:
            return f"I couldn't find weather data for '{resolved_city}'."
        if response.status_code == 401:
            return "Weather API key is invalid. Please check your OPENWEATHERMAP_API_KEY."
        response.raise_for_status()
        data = response.json()

        description: str = data["weather"][0]["description"].capitalize()
        temp: float = data["main"]["temp"]
        feels_like: float = data["main"]["feels_like"]
        humidity: int = data["main"]["humidity"]
        wind_speed: float = data["wind"]["speed"]
        wind_deg: float = data["wind"].get("deg", 0)
        city_name: str = data["name"]
        country: str = data["sys"]["country"]

        result = (
            f"Current weather in {city_name}, {country}: {description}. "
            f"Temperature is {temp:.1f}°C, feels like {feels_like:.1f}°C. "
            f"Humidity is {humidity}%. "
            f"Wind is {wind_speed:.1f} metres per second from the {_wind_direction(wind_deg)}."
        )
        log.info("get_current_weather(%r): success", resolved_city)
        return result
    except requests.RequestException as exc:
        log.error("get_current_weather failed: %s", exc)
        return f"I was unable to fetch weather data: {exc}"


# ---------------------------------------------------------------------------
# get_weather_forecast
# ---------------------------------------------------------------------------


def get_weather_forecast(city: str, days: int = 3) -> str:
    """Return a spoken multi-day weather forecast.

    Uses the OpenWeatherMap 5-day / 3-hour forecast endpoint, grouped by day.

    Parameters
    ----------
    city:
        City name (``"auto"`` for IP-based detection).
    days:
        Number of forecast days to return (1–5).

    Returns
    -------
    str
        Spoken forecast summary, or an error message.
    """
    api_key = _get_api_key()
    if not api_key:
        return (
            "Weather forecast is unavailable. Please set the "
            "OPENWEATHERMAP_API_KEY environment variable."
        )

    days = max(1, min(5, days))
    resolved_city = _resolve_city(city)
    encoded_city = urllib.parse.quote(resolved_city)
    url = (
        f"{_OWM_BASE}/forecast"
        f"?q={encoded_city}&appid={api_key}&units=metric"
    )
    try:
        response = requests.get(url, timeout=_TIMEOUT)
        if response.status_code == 404:
            return f"I couldn't find forecast data for '{resolved_city}'."
        if response.status_code == 401:
            return "Weather API key is invalid. Please check your OPENWEATHERMAP_API_KEY."
        response.raise_for_status()
        data = response.json()

        city_name: str = data["city"]["name"]
        country: str = data["city"]["country"]

        # Group 3-hour slots by date
        from collections import defaultdict
        import datetime

        daily: dict[str, list[dict]] = defaultdict(list)
        for entry in data["list"]:
            date_str = entry["dt_txt"].split(" ")[0]
            daily[date_str].append(entry)

        spoken_days: list[str] = []
        for date_str in sorted(daily.keys())[:days]:
            slots = daily[date_str]
            temps = [s["main"]["temp"] for s in slots]
            descriptions = [s["weather"][0]["description"] for s in slots]
            min_t = min(temps)
            max_t = max(temps)
            # Most common description
            desc = max(set(descriptions), key=descriptions.count).capitalize()
            dt = datetime.date.fromisoformat(date_str)
            day_name = dt.strftime("%A")  # e.g. "Monday"
            spoken_days.append(
                f"{day_name}: {desc}, high of {max_t:.0f}°C, low of {min_t:.0f}°C"
            )

        if not spoken_days:
            return f"No forecast data available for {resolved_city}."

        intro = f"Here is the {days}-day forecast for {city_name}, {country}. "
        result = intro + ". ".join(spoken_days) + "."
        log.info("get_weather_forecast(%r, days=%d): success", resolved_city, days)
        return result
    except requests.RequestException as exc:
        log.error("get_weather_forecast failed: %s", exc)
        return f"I was unable to fetch the weather forecast: {exc}"
