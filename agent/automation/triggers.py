import logging
from typing import List, Dict, Callable

class TriggerManager:
    """
    Manages event triggers.
    Simple Rule: IF event_type == X THEN execute Action.
    """
    def __init__(self):
        self.logger = logging.getLogger("TriggerManager")
        self.triggers: Dict[str, List[Callable]] = {}

    def register_trigger(self, event_type: str, action: Callable):
        """
        Registers an action to be called when an event occurs.
        """
        if event_type not in self.triggers:
            self.triggers[event_type] = []
        self.triggers[event_type].append(action)
        self.logger.info(f"Registered trigger for event: {event_type}")

    def fire_event(self, event_type: str, payload: dict = None):
        """
        Fires an event, executing all registered actions.
        """
        if event_type in self.triggers:
            self.logger.info(f"Event fired: {event_type}")
            for action in self.triggers[event_type]:
                try:
                    action(payload)
                except Exception as e:
                    self.logger.error(f"Error in trigger action: {e}")
