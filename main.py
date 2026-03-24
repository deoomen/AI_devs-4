import asyncio
import logging
import sys
from importlib import import_module

from services.Logging import init_loggers

async def main() -> None:
    init_loggers(logging.INFO)

    try:
        if 1 == len(sys.argv):
            mission_number = input("Which mission do you want to run?")
        else:
            mission_number = sys.argv[1]

        try:
            mission_module = import_module(f"missions.mission{mission_number}.mission{mission_number}")
            mission_class = getattr(mission_module, f"Mission{mission_number}")

            mission = mission_class()
            await mission.run()

        except ModuleNotFoundError as exc:
            raise RuntimeError('Unknown mission "{}"'.format(mission_number)) from exc

    except Exception as exception:  # pylint: disable=broad-exception-caught
        logging.exception(exception)
        exit(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Interrupted by user, shutting down.")
