import httpx
import logging
from config import Config, load_config

class WrongAnswerError(Exception):
    def __init__(self, code: int, msg: str) -> None:
        self.code = code
        self.msg = msg
        super().__init__(self.msg)

class AIdevs4:
    def __init__(self, config: Config | None = None) -> None:
        self.config = config or load_config()

    def parse_response(self, response: httpx.Response) -> dict:
        if response.status_code == 406:
            json = response.json()
            raise WrongAnswerError(json['code'], json['message'])
        elif response.status_code != 200:
            raise RuntimeError('Unexpected HTTP status code: {}; Content: {}'.format(response.status_code, response.text))
        logging.debug(response.text)
        json = response.json()

        if json['code'] != 0:
            raise RuntimeError('Something went wrong :( Content: %s', json)

        return json

    async def answer(self, api_url: str, mission_name: str, answer) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url,
                headers={'Content-Type': 'application/json'},
                json={
                    'apikey': self.config.headquarters_api_key,
                    'task': mission_name,
                    'answer': answer,
                }
            )
        logging.info('Answer sent: {}'.format(answer))
        json = self.parse_response(response)

        logging.info(json['message'])

        return json['message']

    async def verify(self, mission_name: str, report) -> str:
        return await self.answer(
            self.config.headquarters_system_url + "/verify",
            mission_name,
            report,
        )
