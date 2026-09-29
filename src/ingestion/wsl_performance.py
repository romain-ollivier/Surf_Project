"""Ingestion des performances WSL."""

import re

import requests
from bs4 import BeautifulSoup


EVENTS = [
    {
        "event_id": "324",
        "event_name": "Rip Curl Pro Bells Beach",
        "event_year": 2025,
        "spot_name": "Bells Beach",
        "tour": "MCT",
        "url": (
            "https://www.worldsurfleague.com/"
            "events/2025/ct/324/"
            "rip-curl-pro-bells-beach/results"
        ),
    },
]


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/153.0 Safari/537.36"
    )
}


def get_wsl_data(event):
    """Download the WSL event results page."""

    response = requests.get(
        event["url"],
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    return {
        "event": event,
        "soup": soup,
    }


def transform_wsl_data(data, connection):
    """Transform WSL HTML data into RAW records."""

    event = data["event"]
    soup = data["soup"]

    from .database import get_surf_spots

    spots = get_surf_spots(connection)

    spot_id = next(
        (
            spot[0]
            for spot in spots
            if spot[1] == event["spot_name"]
        ),
        None,
    )

    if spot_id is None:
        raise ValueError(
            f"Surf spot not found: "
            f"{event['spot_name']}"
        )

    # ---------------------------------------------------------
    # Build round mapping
    # ---------------------------------------------------------

    round_mapping = {}

    for element in soup.select(
        "a[data-gtm-event]"
    ):

        gtm_event = element.get(
            "data-gtm-event",
            "",
        )

        round_id_match = re.search(
            r'"round_ids":"([^"]+)"',
            gtm_event,
        )

        round_name_match = re.search(
            r'"round_names":"([^"]+)"',
            gtm_event,
        )

        round_number_match = re.search(
            r'"round_numbers":"([^"]+)"',
            gtm_event,
        )

        if (
            round_id_match
            and round_name_match
            and round_number_match
        ):

            round_mapping[
                round_id_match.group(1)
            ] = {
                "name": round_name_match.group(1),
                "number": int(
                    round_number_match.group(1)
                ),
            }

    # ---------------------------------------------------------
    # Extract heats
    # ---------------------------------------------------------

    records = []

    heats = soup.select(
        ".post-event-watch-heat-grid__heat"
    )

    for heat in heats:

        heat_number = heat.get(
            "data-heat-number"
        )

        round_number = heat.get(
            "data-round-number"
        )

        round_container = heat.find_parent(
            class_="post-event-watch-heat-grid__round"
        )

        round_id = (
            round_container.get(
                "data-round-id"
            )
            if round_container
            else None
        )

        round_info = round_mapping.get(
            round_id
        )

        round_name = (
            round_info["name"]
            if round_info
            else None
        )

        if round_info:
            round_number = round_info["number"]

        athletes = heat.select(
            ".hot-heat-athlete"
        )

        for athlete in athletes:

            athlete_id = athlete.get(
                "data-athlete-id"
            )

            name_element = athlete.select_one(
                ".hot-heat-athlete__name--full"
            )

            country_element = athlete.select_one(
                ".athlete-country-flag"
            )

            score_element = athlete.select_one(
                ".hot-heat-athlete__score"
            )

            waves_element = athlete.select_one(
                ".hot-heat-athlete__num-waves"
            )

            counted_waves_element = athlete.select_one(
                ".hot-heat-athlete__counted-waves"
            )

            if not name_element:
                continue

            surfer_name = (
                name_element.get_text(
                    strip=True
                )
            )

            surfer_country = (
                country_element.get("title")
                if country_element
                else None
            )

            heat_score = (
                float(
                    score_element.get_text(
                        strip=True
                    )
                )
                if score_element
                else None
            )

            waves_text = (
                waves_element.get_text(
                    strip=True
                )
                if waves_element
                else None
            )

            waves_match = re.search(
                r"(\d+)",
                waves_text or "",
            )

            waves_count = (
                int(
                    waves_match.group(1)
                )
                if waves_match
                else None
            )

            counted_waves = (
                counted_waves_element.get_text(
                    strip=True
                )
                if counted_waves_element
                else None
            )

            best_wave_1 = None
            best_wave_2 = None

            if counted_waves:

                scores = [
                    float(score.strip())
                    for score in counted_waves.split("+")
                ]

                if len(scores) >= 2:
                    best_wave_1 = scores[0]
                    best_wave_2 = scores[1]

            records.append(
                {
                    "event_id": event["event_id"],
                    "event_name": event["event_name"],
                    "event_date": None,
                    "spot_id": spot_id,
                    "tour": event["tour"],
                    "round": round_name,
                    "heat_number": int(
                        heat_number
                    ),
                    "surfer_id": athlete_id,
                    "surfer_name": surfer_name,
                    "surfer_country": surfer_country,
                    "heat_score": heat_score,
                    "waves_count": waves_count,
                    "best_wave_1": best_wave_1,
                    "best_wave_2": best_wave_2,
                }
            )

    return records


def insert_wsl_data(connection, records):
    """Insert WSL performance records into RAW."""

    if not records:
        return

    query = """
        INSERT INTO raw.wsl_performance (
            event_id,
            event_name,
            event_date,
            spot_id,
            tour,
            round,
            heat_number,
            surfer_id,
            surfer_name,
            surfer_country,
            heat_score,
            waves_count,
            best_wave_1,
            best_wave_2
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (
            event_id,
            heat_number,
            surfer_id
        )
        DO UPDATE SET
            event_name = EXCLUDED.event_name,
            event_date = EXCLUDED.event_date,
            spot_id = EXCLUDED.spot_id,
            tour = EXCLUDED.tour,
            round = EXCLUDED.round,
            heat_score = EXCLUDED.heat_score,
            waves_count = EXCLUDED.waves_count,
            best_wave_1 = EXCLUDED.best_wave_1,
            best_wave_2 = EXCLUDED.best_wave_2,
            ingested_at = NOW()
    """

    rows = [
        (
            record["event_id"],
            record["event_name"],
            record["event_date"],
            record["spot_id"],
            record["tour"],
            record["round"],
            record["heat_number"],
            record["surfer_id"],
            record["surfer_name"],
            record["surfer_country"],
            record["heat_score"],
            record["waves_count"],
            record["best_wave_1"],
            record["best_wave_2"],
        )
        for record in records
    ]

    with connection.cursor() as cursor:
        cursor.executemany(
            query,
            rows,
        )

    connection.commit()