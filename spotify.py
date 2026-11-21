from variables import *
import re
import json
import requests
from db_functions import (
    get_telegram_audio_id,
    get_cached_collection_track_ids,
    save_cached_collection_track_ids,
    normalize_search_query,
    get_cached_search_results,
    save_cached_search_results,
)
from log import *

# Spotify API kalitisiz ishlaydigan versiya (Spotify Embed/oEmbed + iTunes Search API)
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def get_redirect_link(shortened_link):
    response = requests.head(shortened_link, allow_redirects=True, headers=_HEADERS, timeout=15)
    return response.url


def get_link_type(text):
    if re.match(spotify_track_link_pattern, text):
        return "track"
    elif re.match(spotify_album_link_pattern, text):
        return "album"
    elif re.match(spotify_playlist_link_pattern, text):
        return "playlist"
    elif re.match(spotify_shortened_link_pattern, text):
        return "shortened"
    else:
        return False


def get_valid_spotify_links(text):
    regexes = [
        spotify_shortened_link_pattern,
        spotify_track_link_pattern,
        spotify_album_link_pattern,
        spotify_playlist_link_pattern,
    ]
    regex_combined = re.compile("|".join(regexes))
    return [match.group() for match in regex_combined.finditer(text)]


def _extract_embed_track_ids(link_type, link_id):
    """Spotify embed sahifasidan (API kalitisiz) track ID larni oladi."""
    embed_url = f"https://open.spotify.com/embed/{link_type}/{link_id}"
    resp = requests.get(embed_url, headers=_HEADERS, timeout=25)
    resp.raise_for_status()
    html = resp.text

    # 1-usul: __NEXT_DATA__ JSON ichidan olish
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    track_ids = []
    if m:
        try:
            raw = m.group(1)
            for tid in re.findall(r'"uri"\s*:\s*"spotify:track:([A-Za-z0-9]{22})"', raw):
                if tid not in track_ids:
                    track_ids.append(tid)
        except Exception:
            pass

    # 2-usul: HTML ichidagi barcha spotify:track: yoki /track/ ID larni yig'ish
    if not track_ids:
        for tid in re.findall(r'(?:spotify:track:|/track/)([A-Za-z0-9]{22})', html):
            if tid not in track_ids:
                track_ids.append(tid)

    return track_ids


def get_track_ids(link):
    link_id = link.split("/")[-1].split("?")[0]
    link_type = get_link_type(link)
    if link_type == "track":
        return [link_id]
    if link_type not in ("album", "playlist"):
        return []

    ttl = album_cache_ttl_seconds if link_type == "album" else playlist_cache_ttl_seconds
    cached = get_cached_collection_track_ids(link_type, link_id)
    if cached:
        track_ids, age = cached
        if age <= ttl and track_ids:
            return track_ids

    try:
        track_ids = _extract_embed_track_ids(link_type, link_id)
    except Exception as e:
        log(f"embed collection fetch failed for {link_type} {link_id}: {e}")
        if cached and cached[0]:
            return cached[0]
        raise

    if track_ids:
        save_cached_collection_track_ids(link_type, link_id, track_ids)
    return track_ids


def get_track_image(track_id):
    oembed_url = f"https://open.spotify.com/oembed?url=https://open.spotify.com/track/{track_id}"
    r = requests.get(oembed_url, headers=_HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()["thumbnail_url"]


def _resolve_spotify_track_id(artist, title):
    """Qo'shiq nomi va ijrochi bo'yicha ochiq qidiruvdan haqiqiy Spotify track ID topadi."""
    q = f"{artist} {title}".strip()
    try:
        r = requests.get(
            "https://open.spotify.com/search/" + requests.utils.quote(q),
            headers=_HEADERS,
            timeout=12,
        )
        m = re.search(r'/track/([A-Za-z0-9]{22})', r.text)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def _search_itunes_tracks(query, limit=15):
    """Kalitsiz iTunes API orqali qo'shiq qidiradi va Spotify track ID ga bog'laydi."""
    resp = requests.get(
        "https://itunes.apple.com/search",
        params={"term": query, "media": "music", "entity": "song", "limit": limit},
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json().get("results") or []
    parsed = []
    seen = set()
    for item in results:
        name = (item.get("trackName") or "").strip()
        artist = (item.get("artistName") or "").strip()
        if not name or not artist:
            continue
        key = f"{artist.lower()} - {name.lower()}"
        if key in seen:
            continue
        seen.add(key)

        sp_id = _resolve_spotify_track_id(artist, name)
        if not sp_id:
            continue

        parsed.append({
            "id": sp_id,
            "name": name,
            "artist": artist,
            "uri": f"spotify:track:{sp_id}",
            "url": f"https://open.spotify.com/track/{sp_id}",
            "album": (item.get("collectionName") or "").strip(),
        })
        if len(parsed) >= 10:
            break
    return parsed


def _search_itunes_albums(query, limit=15):
    resp = requests.get(
        "https://itunes.apple.com/search",
        params={"term": query, "media": "music", "entity": "album", "limit": limit},
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json().get("results") or []
    parsed = []
    seen = set()
    for item in results:
        name = (item.get("collectionName") or "").strip()
        artist = (item.get("artistName") or "").strip()
        if not name or not artist:
            continue
        key = f"{artist.lower()} - {name.lower()}"
        if key in seen:
            continue
        seen.add(key)
        try:
            r = requests.get(
                "https://open.spotify.com/search/" + requests.utils.quote(f"{artist} {name}"),
                headers=_HEADERS,
                timeout=12,
            )
            m = re.search(r'/album/([A-Za-z0-9]{22})', r.text)
            if not m:
                continue
            alb_id = m.group(1)
        except Exception:
            continue

        parsed.append({
            "id": alb_id,
            "name": name,
            "artist": artist,
            "url": f"https://open.spotify.com/album/{alb_id}",
            "total_tracks": item.get("trackCount") or 0,
        })
        if len(parsed) >= 10:
            break
    return parsed


def _query_matches(query, name, artist):
    tokens = [tok for tok in query.lower().split() if len(tok) > 1]
    if not tokens:
        return True
    hay = f"{name} {artist}".lower()
    return all(tok in hay for tok in tokens)


def search_spotify_items(query, kind="track", require_in_db=False):
    kind = "album" if kind == "album" else "track"
    query_key = normalize_search_query(query)
    cache_key = f"{kind}:{query_key}" if query_key else None
    cached = get_cached_search_results(cache_key) if cache_key else None
    if cached is None and kind == "track" and query_key:
        cached = get_cached_search_results(query_key)
    parsed = None

    if cached:
        hits, age = cached
        if age <= search_cache_ttl_seconds and hits:
            parsed = [dict(t) for t in hits]

    if parsed is None:
        try:
            if kind == "album":
                parsed = _search_itunes_albums(query, 15)
            else:
                parsed = _search_itunes_tracks(query, 15)
            if parsed and cache_key:
                save_cached_search_results(cache_key, parsed)
        except Exception as e:
            if cached and cached[0]:
                parsed = [dict(t) for t in cached[0]]
            else:
                raise

    if kind == "track":
        for track in parsed:
            track["telegram_audio_id"] = get_telegram_audio_id(track["id"])

    relevant = [t for t in parsed if _query_matches(query, t["name"], t["artist"])]
    pool = relevant if relevant else parsed
    if require_in_db:
        pool = [t for t in pool if t.get("telegram_audio_id")]
    return pool[:10]


def search_track_ids(query, require_in_db=False):
    return search_spotify_items(query, kind="track", require_in_db=require_in_db)


def get_track_info_from_track_id(track_id):
    """Spotify oEmbed va sahifa sarlavhasidan '{artist} - {name}' oladi (kalitsiz)."""
    oembed_url = f"https://open.spotify.com/oembed?url=https://open.spotify.com/track/{track_id}"
    try:
        r = requests.get(oembed_url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        title = (r.json().get("title") or "").strip()
        if title:
            # oEmbed title odatda "Song Name" yoki "Artist - Song Name" bo'ladi
            page = requests.get(f"https://open.spotify.com/track/{track_id}", headers=_HEADERS, timeout=15)
            m = re.search(r'<title>(.*?)\s*-\s*song and lyrics by\s*(.*?)\s*\|\s*Spotify</title>', page.text, re.I)
            if m:
                song_name = m.group(1).strip()
                artist_name = m.group(2).strip()
                return f"{artist_name} - {song_name}"
            return title
    except Exception:
        pass

    page = requests.get(f"https://open.spotify.com/track/{track_id}", headers=_HEADERS, timeout=15)
    page.raise_for_status()
    m = re.search(r'<title>(.*?)\s*-\s*song and lyrics by\s*(.*?)\s*\|\s*Spotify</title>', page.text, re.I)
    if m:
        return f"{m.group(2).strip()} - {m.group(1).strip()}"
    m2 = re.search(r'<title>(.*?)</title>', page.text, re.I)
    if m2:
        return m2.group(1).replace("| Spotify", "").strip()
    raise RuntimeError(f"Track info topilmadi: {track_id}")
