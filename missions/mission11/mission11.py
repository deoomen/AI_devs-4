import json
from loguru import logger
from pathlib import Path
from pydantic import BaseModel
from missions.base_mission import BaseMission
from services.AIdevs4 import AIdevs4
from services.OpenRouter import OpenRouterClient


MISSION_WORKSPACE_DIR = Path(__file__).parent / ".workspace"

class Measurement(BaseModel):
    sensor_type: str
    timestamp: int
    temperature_K: int
    pressure_bar: float
    water_level_meters: float
    voltage_supply_v: float
    humidity_percent: float
    operator_notes: str

    def is_valid_measurement(self) -> bool:
        sensor_types = self.sensor_type.split("/")

        if (0 != self.temperature_K and "temperature" not in sensor_types) or ("temperature" in sensor_types and not (553 <= self.temperature_K <= 873)):
            print(f"Invalid temperature: {self.temperature_K}")
            return False
        if (0.0 != self.pressure_bar and "pressure" not in sensor_types) or ("pressure" in sensor_types and not (60.0 <= self.pressure_bar <= 160.0)):
            print(f"Invalid pressure: {self.pressure_bar}")
            return False
        if (0.0 != self.water_level_meters and "water" not in sensor_types) or ("water" in sensor_types and not (5.0 <= self.water_level_meters <= 15.0)):
            print(f"Invalid water level: {self.water_level_meters}")
            return False
        if (0.0 != self.voltage_supply_v and "voltage" not in sensor_types) or ("voltage" in sensor_types and not (229.0 <= self.voltage_supply_v <= 231.0)):
            print(f"Invalid voltage supply: {self.voltage_supply_v}")
            return False
        if (0.0 != self.humidity_percent and "humidity" not in sensor_types) or ("humidity" in sensor_types and not (40.0 <= self.humidity_percent <= 80.0)):
            print(f"Invalid humidity: {self.humidity_percent}")
            return False

        return True


class Mission11(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "evaluation"

    async def run(self) -> None:
        sensors_dir = await self._download_sensors_data()

        measurements = self._split_by_measurement_validity(sensors_dir)
        logger.info("Valid measurements: {}", len(measurements["valid"]))
        logger.info("Invalid measurements: {}", len(measurements["invalid"]))

        unique_note_fragments = self._fetch_unique_note_fragments(sensors_dir / "valid")
        logger.info("Unique note fragments: {}", len(unique_note_fragments))

        anomalous_indices = await self._classify_notes(unique_note_fragments)
        logger.info("Anomalous note fragments: {}", anomalous_indices)

        unique_note_fragments_list = list(unique_note_fragments)
        anomalous_notes = [unique_note_fragments_list[i] for i in anomalous_indices]
        logger.info("Anomalous notes: {}", anomalous_notes)

        invalid_valid_files = self._get_invalid_valid_files(sensors_dir / "valid", anomalous_notes)
        logger.info("Invalid valid files: {}", invalid_valid_files)

        invalid_files_path = sensors_dir / "invalid"
        valid_files_path = sensors_dir / "valid"
        combined_invalid_files_list = self._combine_invalid_files_list_with_anomalous_notes(invalid_files_path, valid_files_path, anomalous_notes)
        logger.info("Combined invalid files list: {}", combined_invalid_files_list)

        aidevs4 = AIdevs4()
        result = await aidevs4.verify(self.get_task_name(), {"recheck": combined_invalid_files_list})
        print(result)

    async def _download_sensors_data(self) -> Path:
        import zipfile

        zip_url = "{}/dane/sensors.zip".format(self.config.aidevs4_headquarters_system_url)
        zip_path = MISSION_WORKSPACE_DIR / "sensors.zip"
        await self.download_file(zip_url, zip_path)

        sensors_dir = MISSION_WORKSPACE_DIR / "sensors"
        sensors_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(sensors_dir)
        logger.info("Extracted sensors.zip to {}", sensors_dir)

        return sensors_dir

    def _split_by_measurement_validity(self, sensors_dir: Path) -> dict[str, list[str]]:
        measurements = {"valid": [], "invalid": []}
        (sensors_dir / "valid").mkdir(parents=True, exist_ok=True)
        (sensors_dir / "invalid").mkdir(parents=True, exist_ok=True)

        for file in sensors_dir.glob("*.json"):
            measurement = Measurement.model_validate_json(file.read_text())
            if measurement.is_valid_measurement():
                measurements["valid"].append(file.name)
                file.rename(sensors_dir / "valid" / file.name)
            else:
                measurements["invalid"].append(file.name)
                file.rename(sensors_dir / "invalid" / file.name)

        return measurements

    def _fetch_unique_note_fragments(self, sensors_dir: Path) -> list[str]:
        if (MISSION_WORKSPACE_DIR / "unique_note_fragments.json").exists():
            with open(MISSION_WORKSPACE_DIR / "unique_note_fragments.json", encoding="utf-8") as f:
                return json.loads(f.read())

        note_fragments = set()
        for file in sensors_dir.glob("*.json"):
            measurement = Measurement.model_validate_json(file.read_text())
            fragments = measurement.operator_notes.split(",")
            fragments = [f.strip() for f in fragments if f.strip()]
            note_fragments.update(fragments)

        note_fragments = list(note_fragments)
        with open(MISSION_WORKSPACE_DIR / "unique_note_fragments.json", "w", encoding="utf-8") as f:
            json.dump(note_fragments, f, indent=2)

        return note_fragments

    async def _classify_notes(self, notes: list[str]) -> list[int]:
        """Use OpenRouter LLM to find anomalous note fragments, return their indices."""
        cache_path = MISSION_WORKSPACE_DIR / "batch_classifications.json"

        if cache_path.exists():
            logger.info("Loading cached classifications from {}", cache_path)
            return list(json.loads(cache_path.read_text()))

        llm = OpenRouterClient(api_key=self.config.openrouter_api_key)

        numbered_notes = "\n".join(f"{i}: {note}" for i, note in enumerate(notes))
        response = await llm.chat(
            messages =[
                {"role": "system", "content": (
                    "You are a sensor operator note classifier. "
                    "You will receive a numbered list of operator note fragments. "
                    "Most notes describe routine, healthy, stable operation — these are NORMAL. "
                    "Some notes describe irregularities, faults, instability, or anything unexpected — these are ANOMALOUS. "
                    "Return ONLY a JSON array of integer indices of the ANOMALOUS notes. "
                    "Example: [3, 17, 42]"
                )},
                {"role": "user", "content": numbered_notes},
            ],
            model = "openai/gpt-5-mini",
        )

        import re
        logger.info("LLM raw response: {}", response)
        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if not json_match:
            raise ValueError(f"No JSON array found in LLM response: {response}")
        anomalous_indices = sorted(json.loads(json_match.group()))

        cache_path.write_text(json.dumps(anomalous_indices))
        logger.info("Saved classification results to {}", cache_path)

        return anomalous_indices

    def _get_invalid_valid_files(self, sensors_dir: Path, anomalous_notes: list[str]) -> list[str]:
        invalid_files = []
        for file in sensors_dir.glob("*.json"):
            measurement = Measurement.model_validate_json(file.read_text())
            fragments = measurement.operator_notes.split(",")
            fragments = [f.strip() for f in fragments if f.strip()]
            if any(f in anomalous_notes for f in fragments):
                invalid_files.append(file.name)

        return invalid_files

    def _combine_invalid_files_list_with_anomalous_notes(self, invalid_files_path: Path, valid_files_path: Path, anomalous_notes: list[str]) -> list[str]:
        invalid_files = []

        for file in invalid_files_path.glob("*.json"):
            invalid_files.append(file.name)

        for file in valid_files_path.glob("*.json"):
            measurement = Measurement.model_validate_json(file.read_text())
            fragments = measurement.operator_notes.split(",")
            fragments = [f.strip() for f in fragments if f.strip()]
            if any(f in anomalous_notes for f in fragments):
                invalid_files.append(file.name)

        return invalid_files
