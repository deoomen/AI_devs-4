from collections import defaultdict
from typing import Callable

from .types import Event, EventName


class EventEmitter:
    def __init__(self):
        self._listeners: dict[str, list[Callable[[Event], None]]] = defaultdict(list)

    def on(self, event_name: EventName, handler: Callable[[Event], None]) -> None:
        self._listeners[str(event_name)].append(handler)

    def emit(self, event: Event) -> None:
        for handler in self._listeners.get(str(event.name), []):
            handler(event)
        # Wildcard listeners
        for handler in self._listeners.get("*", []):
            handler(event)
