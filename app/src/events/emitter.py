from collections import defaultdict
from typing import Callable

from .types import Event


class EventEmitter:
    def __init__(self):
        self._listeners: dict[str, list[Callable[[Event], None]]] = defaultdict(list)

    def on(self, event_name: str, handler: Callable[[Event], None]) -> None:
        self._listeners[event_name].append(handler)

    def emit(self, event: Event) -> None:
        for handler in self._listeners.get(event.name, []):
            handler(event)
        # Wildcard listeners
        for handler in self._listeners.get("*", []):
            handler(event)
