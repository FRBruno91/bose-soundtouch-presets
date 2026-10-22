# -*- coding: utf-8 -*-
"""Search Radio Browser and print a short JSON list for the Bose presets."""
import json
import os
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


class StayHttp(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not str(newurl).lower().startswith("http://"):
            return None
        return urllib.request.HTTPRedirectHandler.redirect_request(
            self, req, fp, code, msg, headers, newurl
        )


def http_audio(url):
    """True when the same path still answers in http with an audio stream."""
    opener = urllib.request.build_opener(StayHttp)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Icy-MetaData": "1"})
    try:
        with opener.open(req, timeout=3) as resp:
            if resp.status != 200:
                return False
            if str(resp.geturl()).lower().startswith("https://"):
                return False
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "text/html" in ctype or "json" in ctype or "mpegurl" in ctype:
                return False
            if ctype.startswith("audio/") or "mpeg" in ctype or "aac" in ctype or ctype.startswith("application/ogg"):
                return True
            chunk = resp.read(16)
    except Exception:
        return False
    if not chunk:
        return False
    if chunk.startswith(b"ID3") or chunk[:2] == b"\xff\xfb" or chunk[:2] == b"\xff\xf3" or chunk[:2] == b"\xff\xf1":
        return True
    return False


def direct_http(url):
    raw = (url or "").strip()
    low = raw.lower()
    if ".m3u8" in low or " " in raw or not low.startswith("https://"):
        return ""
    alt = "http://" + raw[8:]
    if len(alt) > 255 or not http_audio(alt):
        return ""
    return alt


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


def source_url(station):
    for key in ("url_resolved", "url"):
        raw = station.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def rows_from(stations):
    good = []
    bad = []
    seen = set()
    for station in stations:
        name = (station.get("name") or "").strip()
        if not name:
            continue
        raw = source_url(station)
        low = raw.lower()
        url = pick_url(station)
        mode = "http"
        if not url and low.startswith("https://") and ".m3u8" not in low and " " not in raw:
            alt = direct_http(raw)
            if alt:
                url = alt
                mode = "http"
            elif len(raw) <= 255:
                url = raw
                mode = "https"
        if url:
            if url in seen:
                continue
            seen.add(url)
            good.append(
                {
                    "name": name[:120],
                    "meta": meta(station, mode),
                    "url": url,
                    "ok": "1",
                }
            )
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


def relay_prepare(payload):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import bose_https_relay

    bose_https_relay.register_and_print(payload)


def main():
    if len(sys.argv) == 2 and sys.argv[1].startswith("relay:"):
        relay_prepare(sys.argv[1][6:])
        return 0
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
        if len(sys.argv) == 2 and str(sys.argv[1]).startswith("relay:"):
            sys.exit(1)
        emit({"ok": False, "error": "unavailable", "rows": []})
        sys.exit(0)
