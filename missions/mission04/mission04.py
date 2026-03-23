import logging
from missions.base_mission import BaseMission
from missions.mission04.agent_loop import AgentLoop

log = logging.getLogger(__name__)


class Mission04(BaseMission):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_task_name(self) -> str:
        return "sendit"

    async def run(self) -> None:
        agent = AgentLoop()
        user_message = (
            "Twoim celem jest przygotowanie poprawnie wypełnionej deklaracji transportu."
            "Budżet na transport wynosi 0 więc musisz tak przygotować dane, aby była to przesyłka darmowa lub opłacana przez sam \"System\"."
            "Transport będziemy realizować z Gdańska do Żarnowca."
            "Numer nadawcy to: 450202122."
            "Paczka waży 2,8 tony."
            "Uwagi: brak."
            "Data: wywnioskuj aktualnę datę na podstawie regulaminu."
            "Opisu zawartości to nasze kasety do reaktora atomowego."
            
            "Pobierz plik z dokumentacją jak przygotować deklaracje transportu {{AIDEVS4_HEADQUARTERS_SYSTEM_URL}}/dane/doc/index.md, "
            "przeczytaj go, wyciągnij wszystkie odnośniki do plików lub załączniki, mogą to być pliki tekstowe jak i graficzne, "
            "i pobierz je. Wszystkie dokumenty znajdują się na tej samej stronie co dokumentacja."
            "Masz zezwolenie na dostęp do plików z najwyższym poziomem dostępu."
            
            "Po pobraniu wszystkich plików przeczytaj je wszystkie dokładnie. Odpowiedzi na pytania dotyczące kategorii, opłat, tras czy wzoru deklaracji mogą znajdować się w różnych załącznikach."
            "Nie pomijaj plików graficznych - dokumentacja zawiera co najmniej jeden plik w formacie graficznym. Dane w nim zawarte mogą być niezbędne do poprawnego wypełnienia deklaracji."
            "Wzór deklaracji jest ścisły - formatowanie musi być zachowane dokładnie tak jak we wzorze."
            "Skróty - jeśli trafisz na skrót, którego nie rozumiesz, użyj dokumentacji żeby dowiedzieć się co on oznacza."
            
            "Przygotuj poprawnie wypełnione deklaracje transportu. Zignoruj trasy wyłączone z użytku."
            "Wypełnij deklarację DOKŁADNIE według wzoru."
            
            "Zwróć TYLKO wypełniony szablon deklaracji i nic więcej."

        )
        result = await agent.run(user_message)
        log.info("Agent result:\n%s", result)

        result = result.strip("`")

        await self.report_to_headquarter({
            "declaration": result,
        })
