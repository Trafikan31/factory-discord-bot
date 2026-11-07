#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Discord Forex Factory.
- Résumé quotidien à 07:00 (Europe/Paris)
- Alertes pour les annonces High (rouges), au plus tard dans la fenêtre des 15 min précédant l'événement
- Télécharge le calendrier Forex Factory au maximum environ une fois par heure
Aucune dépendance Python externe : bibliothèque standard uniquement.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
CACHE_FILE = ROOT / "calendar_cache.json"
STATE_FILE = ROOT / "bot_state.json"

FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FF_CALENDAR_URL = "https://www.forexfactory.com/calendar"
PARIS = ZoneInfo("Europe/Paris")
SOURCE_FALLBACK_TZ = ZoneInfo("America/New_York")
FETCH_INTERVAL = timedelta(minutes=55)
ALERT_WINDOW = timedelta(minutes=15)
DISCORD_LIMIT = 1850


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_event_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            # Le flux Forex Factory fournit normalement un décalage UTC.
            # Si celui-ci manque, on interprète l'heure comme heure de New York.
            dt = dt.replace(tzinfo=SOURCE_FALLBACK_TZ)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def fetch_calendar():
    request = urllib.request.Request(
        FEED_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; ForexFactoryDiscordCalendar/1.0)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        raw = response.read()
    data = json.loads(raw.decode("utf-8-sig"))
    if isinstance(data, dict):
        data = data.get("events", [])
    if not isinstance(data, list):
        raise ValueError("Le flux Forex Factory n'a pas renvoyé une liste d'annonces.")
    return data


def get_calendar(now: datetime):
    cache = read_json(CACHE_FILE, {})
    fetched_at = None
    try:
        fetched_at = datetime.fromisoformat(cache["fetched_at"])
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError):
        pass

    fresh = fetched_at is not None and (now - fetched_at) < FETCH_INTERVAL
    if fresh and isinstance(cache.get("events"), list):
        return cache["events"]

    try:
        events = fetch_calendar()
        write_json(CACHE_FILE, {
            "fetched_at": now.isoformat(),
            "source": FEED_URL,
            "events": events,
        })
        print(f"Calendrier actualisé : {len(events)} annonces.")
        return events
    except Exception as exc:
        if isinstance(cache.get("events"), list) and cache["events"]:
            print(f"AVERTISSEMENT : impossible d'actualiser Forex Factory ({exc}). Utilisation du cache existant.")
            return cache["events"]
        raise RuntimeError(f"Impossible de récupérer le calendrier Forex Factory et aucun cache n'est disponible : {exc}") from exc


def normalize_events(raw_events):
    normalized = []
    for item in raw_events:
        if not isinstance(item, dict):
            continue
        dt = parse_event_datetime(item.get("date") or item.get("datetime") or "")
        if dt is None:
            continue
        normalized.append({
            "dt": dt,
            "title": str(item.get("title") or item.get("event") or "Annonce économique"),
            "currency": str(item.get("country") or item.get("currency") or "N/A").upper(),
            "impact": str(item.get("impact") or "Unknown"),
            "forecast": str(item.get("forecast") or "").strip(),
            "previous": str(item.get("previous") or "").strip(),
            "actual": str(item.get("actual") or "").strip(),
        })
    normalized.sort(key=lambda event: event["dt"])
    return normalized


def impact_icon(impact: str) -> str:
    value = impact.lower()
    if value in {"high", "red", "3"}:
        return "🔴"
    if value in {"medium", "orange", "2"}:
        return "🟠"
    if value in {"low", "yellow", "1"}:
        return "🟡"
    if value in {"holiday", "non-economic"}:
        return "⚪"
    return "▫️"


def event_key(event) -> str:
    return "|".join([
        event["dt"].isoformat(),
        event["currency"],
        event["title"],
    ])


def event_line(event, include_impact=True) -> str:
    local_dt = event["dt"].astimezone(PARIS)
    time_label = local_dt.strftime("%H:%M")
    icon = impact_icon(event["impact"]) if include_impact else ""
    line = f"{icon} **{time_label} — {event['currency']} — {event['title']}**"
    extras = []
    if event["forecast"]:
        extras.append(f"Prévision : {event['forecast']}")
    if event["previous"]:
        extras.append(f"Précédent : {event['previous']}")
    if event["actual"]:
        extras.append(f"Réel : {event['actual']}")
    if extras:
        line += "\n   " + " · ".join(extras)
    return line


def split_discord_messages(text: str, limit: int = DISCORD_LIMIT):
    chunks = []
    current = ""
    for paragraph in text.split("\n"):
        candidate = paragraph if not current else current + "\n" + paragraph
        if len(candidate) > limit and current:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
        # Garde-fou pour une ligne anormalement longue.
        while len(current) > limit:
            chunks.append(current[:limit])
            current = current[limit:]
    if current:
        chunks.append(current)
    return chunks


def send_discord(webhook_url: str, message: str):
    if not webhook_url:
        raise RuntimeError("Le secret DISCORD_WEBHOOK_URL est absent.")
    for chunk in split_discord_messages(message):
        payload = json.dumps({
            "content": chunk,
            "allowed_mentions": {"parse": []},
        }).encode("utf-8")
        request = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "ForexFactoryDiscordCalendar/1.0"},
            method="POST",
        )
        last_error = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    if response.status not in (200, 204):
                        raise RuntimeError(f"Discord a répondu avec le code HTTP {response.status}.")
                last_error = None
                break
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 429:
                    try:
                        retry_after = float(json.loads(exc.read().decode("utf-8")).get("retry_after", 2))
                    except Exception:
                        retry_after = 2
                    time.sleep(min(retry_after, 10))
                elif 500 <= exc.code < 600:
                    time.sleep(2 ** attempt)
                else:
                    raise RuntimeError(f"Erreur Discord HTTP {exc.code}: {exc.read().decode('utf-8', 'ignore')[:300]}") from exc
            except Exception as exc:
                last_error = exc
                time.sleep(2 ** attempt)
        if last_error is not None:
            raise RuntimeError(f"Échec d'envoi vers Discord : {last_error}") from last_error


def build_daily_digest(events, today: date) -> str:
    todays_events = [e for e in events if e["dt"].astimezone(PARIS).date() == today]
    header = (
        f"📅 **CALENDRIER ÉCONOMIQUE — {today.strftime('%d/%m/%Y')}**\n"
        f"Source : [Forex Factory]({FF_CALENDAR_URL}) · Fuseau : Europe/Paris\n"
        f"Annonces du jour : **{len(todays_events)}**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    if not todays_events:
        return header + "\nAucune annonce publiée dans le calendrier pour aujourd'hui."

    sections = [header]
    for event in todays_events:
        sections.append(event_line(event))
    sections.append("━━━━━━━━━━━━━━━━━━━━━━━━\n🔴 Fort impact · 🟠 Impact moyen · 🟡 Faible impact · ⚪ Jour férié")
    return "\n".join(sections)


def main():
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if os.environ.get("TEST_DISCORD", "").lower() == "true" or "--test" in sys.argv:
        send_discord(webhook, "✅ **Test réussi !** Le webhook du bot Forex Factory fonctionne.")
        print("Message de test envoyé à Discord.")
        return

    now = utc_now()
    local_now = now.astimezone(PARIS)
    state = read_json(STATE_FILE, {})
    if not isinstance(state, dict):
        state = {}

    raw_events = get_calendar(now)
    events = normalize_events(raw_events)

    # Résumé quotidien : la tâche GitHub tourne toutes les 5 minutes.
    # La fenêtre de 07:00 à 07:14 permet d'absorber un léger retard de planification.
    today_key = local_now.date().isoformat()
    if local_now.hour == 7 and local_now.minute < 15 and state.get("last_digest_date") != today_key:
        digest = build_daily_digest(events, local_now.date())
        send_discord(webhook, digest)
        state["last_digest_date"] = today_key
        print(f"Résumé quotidien envoyé pour le {today_key}.")

    # Alertes rouges : déclenchement au premier passage du workflow dans les 15 min
    # précédant l'annonce. Une alerte déjà envoyée n'est jamais répétée.
    alerted = state.get("alerted", {})
    if not isinstance(alerted, dict):
        alerted = {}

    sent_count = 0
    for event in events:
        if event["impact"].lower() not in {"high", "red", "3"}:
            continue
        seconds_left = (event["dt"] - now).total_seconds()
        key = event_key(event)
        if 0 < seconds_left <= ALERT_WINDOW.total_seconds() and key not in alerted:
            local_event_time = event["dt"].astimezone(PARIS).strftime("%d/%m/%Y à %H:%M")
            message = (
                "🚨 **ALERTE ÉCONOMIQUE — FORT IMPACT** 🚨\n"
                f"🔴 **{event['currency']} — {event['title']}**\n"
                f"🕒 Publication prévue : **{local_event_time}** (heure de Paris)\n"
                "⏳ Publication prévue dans environ 15 minutes.\n"
                f"Source : [Forex Factory]({FF_CALENDAR_URL})"
            )
            send_discord(webhook, message)
            alerted[key] = now.isoformat()
            sent_count += 1
            print(f"Alerte envoyée : {event['currency']} / {event['title']}.")

    # Conserve 14 jours d'historique d'alertes pour limiter la taille du fichier.
    cutoff = now - timedelta(days=14)
    cleaned = {}
    for key, value in alerted.items():
        try:
            sent_at = datetime.fromisoformat(value)
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)
            if sent_at >= cutoff:
                cleaned[key] = value
        except (TypeError, ValueError):
            continue
    state["alerted"] = cleaned
    write_json(STATE_FILE, state)
    print(f"Terminé. Annonces chargées : {len(events)}. Nouvelles alertes : {sent_count}.")


if __name__ == "__main__":
    main()
