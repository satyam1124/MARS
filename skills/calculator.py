"""
calculator.py — Math, unit conversion, and currency conversion skills for MARS.

All functions return a ``str`` response that MARS speaks aloud.

Functions
---------
calculate        : Safely evaluate a mathematical expression.
convert_units    : Convert between common units of measurement.
convert_currency : Convert amounts between currencies via exchangerate-api.
"""

from __future__ import annotations

import ast
import math
import operator
import os
import urllib.parse

import requests

from utils.logger import get_logger

log = get_logger(__name__)

_TIMEOUT = 10

# ---------------------------------------------------------------------------
# Safe expression evaluator
# ---------------------------------------------------------------------------

# Operators permitted in calculate()
_OPERATORS: dict[type, object] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Safe math functions exposed to expressions (e.g. "sqrt(16)")
_SAFE_FUNCTIONS: dict[str, object] = {
    "abs": abs,
    "round": round,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
    "ceil": math.ceil,
    "floor": math.floor,
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "inf": math.inf,
    "factorial": math.factorial,
}


def _safe_eval(node: ast.AST) -> float:
    """Recursively evaluate a parsed AST node using only safe operations."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Unsupported constant: {node.value!r}")
    if isinstance(node, ast.BinOp):
        op_func = _OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return op_func(left, right)  # type: ignore[operator]
    if isinstance(node, ast.UnaryOp):
        op_func = _OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_func(_safe_eval(node.operand))  # type: ignore[operator]
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are allowed.")
        func = _SAFE_FUNCTIONS.get(node.func.id)
        if func is None:
            raise ValueError(f"Function '{node.func.id}' is not allowed.")
        args = [_safe_eval(a) for a in node.args]
        return func(*args)  # type: ignore[operator]
    if isinstance(node, ast.Name):
        val = _SAFE_FUNCTIONS.get(node.id)
        if val is None or not isinstance(val, (int, float)):
            raise ValueError(f"Unknown name: {node.id!r}")
        return float(val)  # type: ignore[arg-type]
    raise ValueError(f"Unsupported node type: {type(node).__name__}")


# ---------------------------------------------------------------------------
# calculate
# ---------------------------------------------------------------------------


def calculate(expression: str) -> str:
    """Safely evaluate a mathematical expression and return a spoken result.

    Supports the four arithmetic operations, exponentiation, and common
    math functions: ``sqrt``, ``sin``, ``cos``, ``tan``, ``log``, ``log10``,
    ``log2``, ``exp``, ``ceil``, ``floor``, ``abs``, ``round``, ``factorial``.
    Constants ``pi``, ``e``, and ``tau`` are also available.

    Parameters
    ----------
    expression:
        Mathematical expression string, e.g. ``"2 ** 10"`` or ``"sqrt(144)"``.

    Returns
    -------
    str
        Spoken result, e.g. ``"The result of 2 ** 10 is 1024."``.
    """
    if not expression.strip():
        return "Please provide a mathematical expression to evaluate."

    # Normalise common spoken forms
    cleaned = (
        expression
        .replace("^", "**")
        .replace("×", "*")
        .replace("÷", "/")
        .replace("x", "*")  # ambiguous but common
    )

    try:
        tree = ast.parse(cleaned, mode="eval")
        result = _safe_eval(tree)
        # Format result neatly
        if isinstance(result, float) and result.is_integer():
            formatted = str(int(result))
        else:
            formatted = f"{result:.6g}"
        spoken = f"The result of {expression} is {formatted}."
        log.info("calculate(%r) = %s", expression, formatted)
        return spoken
    except ZeroDivisionError:
        return "That expression results in a division by zero."
    except (ValueError, TypeError, SyntaxError) as exc:
        log.warning("calculate(%r) error: %s", expression, exc)
        return f"I couldn't evaluate that expression: {exc}"
    except Exception as exc:
        log.error("calculate unexpected error: %s", exc)
        return f"An error occurred while calculating: {exc}"


# ---------------------------------------------------------------------------
# Unit conversion tables
# ---------------------------------------------------------------------------

# Each entry: (unit_aliases, conversion_factor_to_base, base_unit_name)
# Base units: metres (length), kilograms (weight), litres (volume),
#             celsius (temperature), square metres (area), seconds (time)

_LENGTH_TO_METRES: dict[str, float] = {
    "mm": 0.001, "millimetre": 0.001, "millimeter": 0.001,
    "cm": 0.01, "centimetre": 0.01, "centimeter": 0.01,
    "m": 1.0, "metre": 1.0, "meter": 1.0,
    "km": 1000.0, "kilometre": 1000.0, "kilometer": 1000.0,
    "in": 0.0254, "inch": 0.0254, "inches": 0.0254,
    "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
    "yd": 0.9144, "yard": 0.9144, "yards": 0.9144,
    "mi": 1609.344, "mile": 1609.344, "miles": 1609.344,
    "nmi": 1852.0, "nautical mile": 1852.0,
}

_WEIGHT_TO_KG: dict[str, float] = {
    "mg": 1e-6, "milligram": 1e-6, "milligrams": 1e-6,
    "g": 0.001, "gram": 0.001, "grams": 0.001,
    "kg": 1.0, "kilogram": 1.0, "kilograms": 1.0,
    "tonne": 1000.0, "metric ton": 1000.0,
    "oz": 0.0283495, "ounce": 0.0283495, "ounces": 0.0283495,
    "lb": 0.453592, "pound": 0.453592, "pounds": 0.453592,
    "st": 6.35029, "stone": 6.35029,
    "ton": 907.185, "short ton": 907.185,
}

_VOLUME_TO_LITRES: dict[str, float] = {
    "ml": 0.001, "millilitre": 0.001, "milliliter": 0.001,
    "l": 1.0, "litre": 1.0, "liter": 1.0,
    "fl oz": 0.0295735, "fluid ounce": 0.0295735,
    "cup": 0.236588,
    "pint": 0.473176, "pt": 0.473176,
    "quart": 0.946353, "qt": 0.946353,
    "gallon": 3.78541, "gal": 3.78541,
    "tsp": 0.00492892, "teaspoon": 0.00492892,
    "tbsp": 0.0147868, "tablespoon": 0.0147868,
}

_TIME_TO_SECONDS: dict[str, float] = {
    "s": 1.0, "sec": 1.0, "second": 1.0, "seconds": 1.0,
    "min": 60.0, "minute": 60.0, "minutes": 60.0,
    "h": 3600.0, "hr": 3600.0, "hour": 3600.0, "hours": 3600.0,
    "day": 86400.0, "days": 86400.0,
    "week": 604800.0, "weeks": 604800.0,
    "month": 2629800.0, "months": 2629800.0,   # average
    "year": 31557600.0, "years": 31557600.0,   # Julian
}

_SPEED_TO_MPS: dict[str, float] = {
    "m/s": 1.0, "mps": 1.0,
    "km/h": 1 / 3.6, "kph": 1 / 3.6, "kmh": 1 / 3.6,
    "mph": 0.44704,
    "knot": 0.514444, "kn": 0.514444,
}

_AREA_TO_SQM: dict[str, float] = {
    "m2": 1.0, "sqm": 1.0, "square metre": 1.0, "square meter": 1.0,
    "km2": 1e6, "square kilometre": 1e6, "square kilometer": 1e6,
    "cm2": 1e-4, "square centimetre": 1e-4,
    "ft2": 0.092903, "sqft": 0.092903, "square foot": 0.092903, "square feet": 0.092903,
    "in2": 0.00064516, "square inch": 0.00064516,
    "acre": 4046.86,
    "hectare": 10000.0, "ha": 10000.0,
    "mi2": 2.59e6, "square mile": 2.59e6,
}

_DIGITAL_TO_BYTES: dict[str, float] = {
    "b": 1.0, "byte": 1.0, "bytes": 1.0,
    "kb": 1e3, "kilobyte": 1e3,
    "mb": 1e6, "megabyte": 1e6,
    "gb": 1e9, "gigabyte": 1e9,
    "tb": 1e12, "terabyte": 1e12,
    "kib": 1024.0, "kibibyte": 1024.0,
    "mib": 1024.0 ** 2, "mebibyte": 1024.0 ** 2,
    "gib": 1024.0 ** 3, "gibibyte": 1024.0 ** 3,
}

_CONVERSION_GROUPS: list[dict[str, float]] = [
    _LENGTH_TO_METRES,
    _WEIGHT_TO_KG,
    _VOLUME_TO_LITRES,
    _TIME_TO_SECONDS,
    _SPEED_TO_MPS,
    _AREA_TO_SQM,
    _DIGITAL_TO_BYTES,
]

_TEMPERATURE_UNITS = {"c", "celsius", "f", "fahrenheit", "k", "kelvin"}


def _convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
    """Convert between Celsius, Fahrenheit, and Kelvin."""
    from_unit = from_unit.lower().strip()
    to_unit = to_unit.lower().strip()

    # Normalise to Celsius first
    if from_unit in ("f", "fahrenheit"):
        celsius = (value - 32) * 5 / 9
    elif from_unit in ("k", "kelvin"):
        celsius = value - 273.15
    else:
        celsius = value

    # Convert from Celsius to target
    if to_unit in ("f", "fahrenheit"):
        return celsius * 9 / 5 + 32
    if to_unit in ("k", "kelvin"):
        return celsius + 273.15
    return celsius


def _find_group(unit: str) -> dict[str, float] | None:
    """Return the conversion group dict that contains *unit*, or ``None``."""
    unit_lower = unit.lower().strip()
    for group in _CONVERSION_GROUPS:
        if unit_lower in group:
            return group
    return None


# ---------------------------------------------------------------------------
# convert_units
# ---------------------------------------------------------------------------


def convert_units(value: float, from_unit: str, to_unit: str) -> str:
    """Convert *value* from *from_unit* to *to_unit*.

    Supports length, weight/mass, volume, time, speed, area, and digital
    storage.  Also handles temperature (Celsius, Fahrenheit, Kelvin).

    Parameters
    ----------
    value:
        Numeric quantity to convert.
    from_unit:
        Source unit string (e.g. ``"km"``, ``"kg"``, ``"Celsius"``).
    to_unit:
        Target unit string.

    Returns
    -------
    str
        Spoken conversion result or error message.
    """
    from_u = from_unit.lower().strip()
    to_u = to_unit.lower().strip()

    # Temperature is a special case
    if from_u in _TEMPERATURE_UNITS or to_u in _TEMPERATURE_UNITS:
        try:
            result = _convert_temperature(value, from_u, to_u)
            if isinstance(result, float) and result == int(result):
                formatted = str(int(result))
            else:
                formatted = f"{result:.4g}"
            spoken = f"{value} {from_unit} is {formatted} {to_unit}."
            log.info("convert_units: %s %s → %s %s", value, from_unit, formatted, to_unit)
            return spoken
        except Exception as exc:
            return f"I couldn't convert that temperature: {exc}"

    from_group = _find_group(from_u)
    to_group = _find_group(to_u)

    if from_group is None:
        return f"I don't recognise the unit '{from_unit}'."
    if to_group is None:
        return f"I don't recognise the unit '{to_unit}'."
    if from_group is not to_group:
        return f"I can't convert '{from_unit}' to '{to_unit}' — they measure different things."

    base_value = value * from_group[from_u]
    result = base_value / to_group[to_u]

    if isinstance(result, float) and result == int(result):
        formatted = str(int(result))
    else:
        formatted = f"{result:.6g}"

    spoken = f"{value} {from_unit} is {formatted} {to_unit}."
    log.info("convert_units: %s %s → %s %s", value, from_unit, formatted, to_unit)
    return spoken


# ---------------------------------------------------------------------------
# convert_currency
# ---------------------------------------------------------------------------


def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert *amount* from one currency to another using exchangerate-api.

    Uses the free tier of ``https://open.er-api.com`` (no API key required
    for basic conversions).

    Parameters
    ----------
    amount:
        Amount to convert.
    from_currency:
        Three-letter ISO 4217 code, e.g. ``"USD"``.
    to_currency:
        Three-letter ISO 4217 code, e.g. ``"EUR"``.

    Returns
    -------
    str
        Spoken conversion result or error message.
    """
    if amount <= 0:
        return "Please provide a positive amount for currency conversion."

    from_c = from_currency.upper().strip()
    to_c = to_currency.upper().strip()

    if from_c == to_c:
        return f"{amount} {from_c} is the same as {amount} {to_c}."

    url = f"https://open.er-api.com/v6/latest/{from_c}"
    try:
        response = requests.get(url, timeout=_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        if data.get("result") == "error":
            return f"I couldn't find exchange rates for '{from_c}'."

        rates: dict[str, float] = data.get("rates", {})
        if to_c not in rates:
            return f"Exchange rate for '{to_c}' is not available."

        rate = rates[to_c]
        converted = amount * rate

        spoken = (
            f"{amount:.2f} {from_c} is approximately {converted:.2f} {to_c} "
            f"at a rate of {rate:.4f}."
        )
        log.info("convert_currency: %s %s → %s %s", amount, from_c, converted, to_c)
        return spoken
    except requests.RequestException as exc:
        log.error("convert_currency failed: %s", exc)
        return f"I was unable to fetch exchange rates right now: {exc}"
