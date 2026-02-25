"""Network skills for MARS — IP info, speed tests, WiFi and Bluetooth control."""

import subprocess


def _run(cmd: list[str], timeout: int = 15) -> tuple[str, str, int]:
    """Run a subprocess and return (stdout, stderr, returncode)."""
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def get_ip_address() -> str:
    """Get both the local and public IP addresses.

    Returns:
        Local and public IP addresses as a string.
    """
    local_ip = "unknown"
    public_ip = "unknown"

    # Local IP
    try:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
    except Exception:
        pass

    # Public IP
    try:
        import urllib.request

        with urllib.request.urlopen("https://api.ipify.org", timeout=5) as resp:
            public_ip = resp.read().decode("utf-8").strip()
    except Exception:
        pass

    return f"Local IP: {local_ip}\nPublic IP: {public_ip}"


def check_internet_connection() -> str:
    """Check whether an internet connection is available.

    Returns:
        Connection status as a string.
    """
    try:
        import urllib.request

        urllib.request.urlopen("https://www.google.com", timeout=5)
        return "Internet connection is active."
    except Exception:
        pass

    # Fallback: ping
    try:
        stdout, _, code = _run(["ping", "-c", "1", "-W", "3", "8.8.8.8"], timeout=10)
        if code == 0:
            return "Internet connection is active."
        return "No internet connection detected."
    except Exception:
        return "Could not determine internet connection status."


def run_speed_test() -> str:
    """Run an internet speed test using speedtest-cli.

    Returns:
        Download/upload speeds and ping as a string.
    """
    try:
        stdout, stderr, code = _run(
            ["speedtest-cli", "--simple"], timeout=60
        )
        if code != 0:
            return f"Speed test failed: {stderr or stdout}"
        return stdout or "Speed test completed but returned no output."
    except FileNotFoundError:
        # Try speedtest (newer binary)
        try:
            stdout, stderr, code = _run(["speedtest", "--format=human-readable"], timeout=60)
            if code == 0:
                return stdout
        except FileNotFoundError:
            pass
        return "speedtest-cli is not installed. Run: pip install speedtest-cli"
    except subprocess.TimeoutExpired:
        return "Speed test timed out."
    except Exception as e:
        return f"Speed test error: {e}"


def wifi_on() -> str:
    """Enable WiFi using networksetup (macOS).

    Returns:
        Confirmation or error message.
    """
    try:
        stdout, stderr, code = _run(["networksetup", "-setairportpower", "en0", "on"])
        if code != 0:
            return f"Failed to enable WiFi: {stderr}"
        return "WiFi enabled."
    except FileNotFoundError:
        try:
            stdout, stderr, code = _run(["nmcli", "radio", "wifi", "on"])
            if code == 0:
                return "WiFi enabled."
            return f"Failed to enable WiFi: {stderr}"
        except FileNotFoundError:
            return "networksetup (macOS) or nmcli (Linux) not found."
    except Exception as e:
        return f"Failed to enable WiFi: {e}"


def wifi_off() -> str:
    """Disable WiFi using networksetup (macOS).

    Returns:
        Confirmation or error message.
    """
    try:
        stdout, stderr, code = _run(["networksetup", "-setairportpower", "en0", "off"])
        if code != 0:
            return f"Failed to disable WiFi: {stderr}"
        return "WiFi disabled."
    except FileNotFoundError:
        try:
            stdout, stderr, code = _run(["nmcli", "radio", "wifi", "off"])
            if code == 0:
                return "WiFi disabled."
            return f"Failed to disable WiFi: {stderr}"
        except FileNotFoundError:
            return "networksetup (macOS) or nmcli (Linux) not found."
    except Exception as e:
        return f"Failed to disable WiFi: {e}"


def get_wifi_info() -> str:
    """Get current WiFi SSID and signal strength.

    Returns:
        WiFi SSID and signal info as a string.
    """
    # macOS: airport utility
    try:
        stdout, _, code = _run(
            ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"]
        )
        if code == 0 and stdout:
            lines = {}
            for line in stdout.splitlines():
                parts = line.split(":", 1)
                if len(parts) == 2:
                    lines[parts[0].strip()] = parts[1].strip()
            ssid = lines.get("SSID", "unknown")
            rssi = lines.get("agrCtlRSSI", "unknown")
            noise = lines.get("agrCtlNoise", "unknown")
            channel = lines.get("channel", "unknown")
            return (
                f"SSID: {ssid}\n"
                f"Signal (RSSI): {rssi} dBm\n"
                f"Noise: {noise} dBm\n"
                f"Channel: {channel}"
            )
    except Exception:
        pass

    # macOS: networksetup
    try:
        stdout, _, code = _run(["networksetup", "-getairportnetwork", "en0"])
        if code == 0 and stdout:
            return stdout
    except Exception:
        pass

    # Linux: iwconfig
    try:
        stdout, _, code = _run(["iwconfig"])
        if code == 0 and stdout:
            lines = [l for l in stdout.splitlines() if "ESSID" in l or "Signal" in l]
            return "\n".join(lines) if lines else "Connected but could not parse WiFi info."
    except Exception:
        pass

    return "Could not retrieve WiFi information."


def bluetooth_on() -> str:
    """Enable Bluetooth (macOS via blueutil or system command).

    Returns:
        Confirmation or error message.
    """
    try:
        stdout, stderr, code = _run(["blueutil", "--power", "1"])
        if code == 0:
            return "Bluetooth enabled."
        return f"blueutil failed: {stderr}"
    except FileNotFoundError:
        try:
            # Linux with rfkill
            stdout, stderr, code = _run(["rfkill", "unblock", "bluetooth"])
            if code == 0:
                return "Bluetooth enabled."
            return f"rfkill failed: {stderr}"
        except FileNotFoundError:
            return "blueutil (macOS: brew install blueutil) or rfkill (Linux) not found."
    except Exception as e:
        return f"Failed to enable Bluetooth: {e}"


def bluetooth_off() -> str:
    """Disable Bluetooth (macOS via blueutil or system command).

    Returns:
        Confirmation or error message.
    """
    try:
        stdout, stderr, code = _run(["blueutil", "--power", "0"])
        if code == 0:
            return "Bluetooth disabled."
        return f"blueutil failed: {stderr}"
    except FileNotFoundError:
        try:
            stdout, stderr, code = _run(["rfkill", "block", "bluetooth"])
            if code == 0:
                return "Bluetooth disabled."
            return f"rfkill failed: {stderr}"
        except FileNotFoundError:
            return "blueutil (macOS: brew install blueutil) or rfkill (Linux) not found."
    except Exception as e:
        return f"Failed to disable Bluetooth: {e}"


def ping_host(host: str) -> str:
    """Ping a host and return the result.

    Args:
        host: Hostname or IP address.

    Returns:
        Ping summary as a string.
    """
    try:
        stdout, stderr, code = _run(["ping", "-c", "4", host], timeout=15)
        if code != 0:
            return f"Ping to '{host}' failed — host may be unreachable.\n{stderr}"
        lines = stdout.splitlines()
        summary = [l for l in lines if "packet" in l or "min/avg" in l or "rtt" in l]
        return "\n".join(summary) if summary else stdout
    except subprocess.TimeoutExpired:
        return f"Ping to '{host}' timed out."
    except Exception as e:
        return f"Ping error: {e}"
