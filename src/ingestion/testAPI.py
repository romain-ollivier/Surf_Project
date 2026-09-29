from datetime import datetime, timezone, timedelta

from .tides_open_water import (
    get_tide_data,
    get_or_create_tide_station,
)
from .database import (
    get_db_connection,
    get_surf_spots,
)


now_utc = datetime.now(timezone.utc)

start_date = now_utc.date()
end_date = start_date + timedelta(days=7)

print("Dates demandées par main.py:")
print(f"start = {start_date}")
print(f"end   = {end_date}")

connection = get_db_connection()

try:
    spots = get_surf_spots(connection)

    for spot_id, spot_name, latitude, longitude in spots:

        print(f"\n--- {spot_name} ---")

        tide_station = get_or_create_tide_station(
            connection,
            spot_id,
            latitude,
            longitude,
        )

        tide_station_id = tide_station[0]

        tide_data = get_tide_data(
            tide_station_id,
            start_date,
            end_date,
        )

        timeline = tide_data["timeline"]

        print(f"Station : {tide_station_id}")
        print(f"Nombre de points : {len(timeline)}")
        print(f"Premier point    : {timeline[0]['time']}")
        print(f"Dernier point    : {timeline[-1]['time']}")

finally:
    connection.close()