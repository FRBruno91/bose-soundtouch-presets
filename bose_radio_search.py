# -*- coding: utf-8 -*-
"""Search Radio Browser and print a short JSON list for the Bose presets."""
import json
import sys
import urllib.parse
import urllib.request

UA = "HomeAssistant-Bose/1.0"
FALLBACK = [
    "de1.api.radio-browser.info",
    "de2.api.radio-browser.info",
    "nl1.api.radio-browser.info",
    "at1.api.radio-browser.info",
    "fi1.api.radio-browser.info",
]
SAFE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789%._~+-")


def emit(payload):
    print(json.dumps(payload, ensure_ascii=True))


def fetch(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def servers():
    found = []
    try:
        data = json.loads(fetch("https://all.api.radio-browser.info/json/servers", 6))
        for item in data if isinstance(data, list) else []:
            name = (item.get("name") or "").strip()
            if name and name not in found:
                found.append(name)
    except Exception:
        found = []
    for name in FALLBACK:
        if name not in found:
            found.append(name)
    return found[:8]


def usable(url):
    if not isinstance(url, str):
        return False
    url = url.strip()
    low = url.lower()
    return low.startswith("http://") and ".m3u8" not in low and " " not in url and len(url) <= 255


def pick_url(station):
    for key in ("url_resolved", "url"):
        if usable(station.get(key)):
            return station.get(key).strip()
    return ""


def reason(station):
    raw = (station.get("url_resolved") or station.get("url") or "")
    low = raw.lower() if isinstance(raw, str) else ""
    if ".m3u8" in low:
        return "m3u8"
    if low.startswith("https://"):
        return "https"
    return "incompatible"


def meta(station, extra=""):
    country = (station.get("country") or station.get("countrycode") or "").strip()
    codec = (station.get("codec") or "").strip()
    if codec.upper() == "UNKNOWN":
        codec = ""
    bitrate = station.get("bitrate") or 0
    tech = codec
    try:
        if int(bitrate) > 0 and codec:
            tech = codec + " " + str(int(bitrate))
        elif int(bitrate) > 0:
            tech = str(int(bitrate))
    except (TypeError, ValueError):
        pass
    parts = [part for part in (country, tech, extra) if part]
    return " · ".join(parts)[:100]


def search(query):
    encoded = urllib.parse.urlencode(
        {
            "name": query,
            "hidebroken": "true",
            "order": "clickcount",
            "reverse": "true",
            "limit": "40",
        }
    )
    for host in servers():
        url = "https://%s/json/stations/search?%s" % (host, encoded)
        try:
            payload = json.loads(fetch(url, 8))
        except Exception:
            continue
        if isinstance(payload, list):
            return payload
    return None


def rows_from(stations):
    good = []
    bad = []
    seen = set()
    for station in stations:
        name = (station.get("name") or "").strip()
        if not name:
            continue
        url = pick_url(station)
        if url:
            if url in seen:
                continue
            seen.add(url)
            good.append({"name": name[:120], "meta": meta(station), "url": url, "ok": "1"})
        else:
            bad.append(
                {
                    "name": name[:120],
                    "meta": meta(station, reason(station)),
                    "url": "",
                    "ok": "0",
                }
            )
    return (good if good else bad)[:8]


def main():
    if len(sys.argv) != 2 or not sys.argv[1] or any(ch not in SAFE for ch in sys.argv[1]):
        emit({"ok": False, "error": "query", "rows": []})
        return 0
    query = urllib.parse.unquote(sys.argv[1]).strip()
    if not query:
        emit({"ok": False, "error": "query", "rows": []})
        return 0
    found = search(query)
    if found is None:
        emit({"ok": False, "error": "unavailable", "rows": []})
        return 0
    emit({"ok": True, "error": "", "rows": rows_from(found)})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        emit({"ok": False, "error": "unavailable", "rows": []})
        sys.exit(0)
