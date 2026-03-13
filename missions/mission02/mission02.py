import csv
import json
import logging
import math
from missions.base_mission import BaseMission
from pathlib import Path
from pydantic import BaseModel

from services.OpenRouter import OpenRouterClient

log = logging.getLogger(__name__)
MISSION_DIR = Path(__file__).parent


class CityCoordinates(BaseModel):
    lat: float
    lon: float


class Mission02(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._openrouter = OpenRouterClient(api_key=self.config.openrouter_api_key)

    def get_task_name(self) -> str:
        return "findhim"

    async def run(self) -> None:
        # await self._download_and_enrich_power_plant_locations()
        # await self._query_and_save_suspect_locations()
        self._calculate_and_save_distances()
        answer = await self._fetch_access_level_for_closest_suspect()
        await self.report_to_headquarter(answer)

    async def _download_and_enrich_power_plant_locations(self) -> None:
        url = "***REMOVED***/data/{}/findhim_locations.json".format(self.config.aidevs4_headquarters_api_key)
        dest = MISSION_DIR / "findhim_locations.json"
        await self.download_file(url, dest)

        data = json.loads(dest.read_text(encoding="utf-8"))
        for city, info in data["power_plants"].items():
            await self._enrich_city_coordinates(city, info)

        dest.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
        log.info("findhim_locations.json enriched with coordinates")

    async def _enrich_city_coordinates(self, city: str, info: dict) -> None:
        if "lat" in info and "lon" in info:
            log.debug("Coordinates for %s already present, skipping", city)
            return
        coords = await self._openrouter.chat_structured(
            messages=[
                {
                    "role": "system",
                    "content": "You are a geography expert. Return precise GPS coordinates for the given city in Poland.",
                },
                {
                    "role": "user",
                    "content": "What are the latitude and longitude of {} in Poland?".format(city),
                },
            ],
            response_model=CityCoordinates,
        )
        info["lat"] = coords.lat
        info["lon"] = coords.lon
        log.info("Enriched %s -> lat=%s, lon=%s", city, coords.lat, coords.lon)

    async def _query_and_save_suspect_locations(self) -> None:
        suspects_people_path = MISSION_DIR / "../mission01/suspects_people.csv"
        with suspects_people_path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        log.info("Querying locations for %d suspects", len(rows))

        locations: dict = {}
        for row in rows:
            result = await self.headquarter.api_location(row["name"], row["surname"])
            locations["{} {}".format(row["name"], row["surname"])] = result

        locations_file = MISSION_DIR / "suspects_locations.json"
        locations_file.write_text(json.dumps(locations, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("Locations saved to %s (%d entries)", locations_file, len(locations))

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Return distance in km between two GPS points using the Haversine formula."""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
        return R * 2 * math.asin(math.sqrt(a))

    def _calculate_and_save_distances(self) -> None:
        suspects_locations: dict = json.loads(
            (MISSION_DIR / "suspects_locations.json").read_text(encoding="utf-8")
        )
        power_plants: dict = json.loads(
            (MISSION_DIR / "findhim_locations.json").read_text(encoding="utf-8")
        )["power_plants"]

        suspects_people_path = MISSION_DIR / "../mission01/suspects_people.csv"
        with suspects_people_path.open(newline="", encoding="utf-8") as f:
            birth_years: dict[str, int] = {
                "{} {}".format(row["name"], row["surname"]): int(row["birthDate"].split("-")[0])
                for row in csv.DictReader(f)
            }

        rows = []
        for full_name, person_locations in suspects_locations.items():
            name, *surname_parts = full_name.split(" ")
            surname = " ".join(surname_parts)
            for location in person_locations:
                for plant_info in power_plants.values():
                    distance = self._haversine(
                        location["latitude"], location["longitude"],
                        plant_info["lat"], plant_info["lon"],
                    )
                    rows.append({
                        "name": name,
                        "surname": surname,
                        "birth_year": birth_years.get(full_name),
                        "power_plant_code": plant_info["code"],
                        "distance_km": round(distance, 2),
                    })

        rows.sort(key=lambda r: r["distance_km"])

        distances_file = MISSION_DIR / "distances.csv"
        self.save_csv(distances_file, rows)
        log.info("Distances saved to %s (%d rows)", distances_file, len(rows))

    async def _fetch_access_level_for_closest_suspect(self) -> dict:
        distances_file = MISSION_DIR / "distances.csv"
        with distances_file.open(newline="", encoding="utf-8") as f:
            first_row = next(csv.DictReader(f))

        name = first_row["name"]
        surname = first_row["surname"]
        birth_year = int(first_row["birth_year"])
        power_plant_code = first_row["power_plant_code"]

        log.info("Fetching access level for %s %s (born %d)", name, surname, birth_year)
        result = await self.headquarter.api_accesslevel(name, surname, birth_year)
        log.info("Access level result: %s", result)

        return {
            "name": name,
            "surname": surname,
            "accessLevel": result["accessLevel"],
            "powerPlant": power_plant_code,
        }
