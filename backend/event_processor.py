import asyncio
import json
from pathlib import Path
from typing import Optional

import store
from rule_engine import RuleEngine

DATA_DIR = Path(__file__).parent / "data"

SPEED_DELAYS = {
    "slow": 0.8,
    "normal": 0.25,
    "fast": 0.05,
    "instant": 0,
}


class ReplayState:
    def __init__(self):
        self.events: list = []
        self.current_index: int = 0
        self.is_running: bool = False
        self.speed: str = "normal"
        self._task: Optional[asyncio.Task] = None
        self._engine = RuleEngine()

    def load_events(self) -> None:
        path = DATA_DIR / "events.jsonl"
        events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        # Sort by timestamp so out-of-order lines in the file don't break causality
        self.events = sorted(events, key=lambda e: e["ts"])

    @property
    def total_events(self) -> int:
        return len(self.events)

    @property
    def current_ts(self) -> Optional[str]:
        if self.events and self.current_index > 0:
            idx = min(self.current_index - 1, len(self.events) - 1)
            return self.events[idx]["ts"]
        return None

    def to_dict(self) -> dict:
        return {
            "is_running": self.is_running,
            "current_index": self.current_index,
            "total_events": self.total_events,
            "current_ts": self.current_ts,
            "speed": self.speed,
        }

    def reset(self) -> None:
        self.is_running = False
        self.current_index = 0
        self._engine.reset()
        store.reset_notifications()
        if self._task and not self._task.done():
            self._task.cancel()

    async def start(self, speed: str) -> None:
        if self.is_running:
            return
        self.speed = speed
        self.is_running = True
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        delay = SPEED_DELAYS.get(self.speed, 0.25)
        configs = store.get_configs()

        try:
            while self.current_index < len(self.events):
                if not self.is_running:
                    break

                event = self.events[self.current_index]
                self.current_index += 1

                new_notifs, updated_notifs, resolved = self._engine.process_event(event, configs)

                # Apply changes to the store atomically
                active = store.get_notifications()
                active_map = {n["notification_id"]: n for n in active}

                for n in new_notifs:
                    active_map[n["notification_id"]] = n

                for n in updated_notifs:
                    nid = n["notification_id"]
                    if nid in active_map:
                        active_map[nid]["last_seen_at"] = n["last_seen_at"]

                resolved_ids = {r["notification_id"] for r in resolved}
                remaining = [n for nid, n in active_map.items() if nid not in resolved_ids]
                store.save_notifications(remaining)

                if resolved:
                    history = store.get_history()
                    history.extend(resolved)
                    store.save_history(history)

                if delay > 0:
                    await asyncio.sleep(delay)

        finally:
            self.is_running = False


# Module-level singleton shared across FastAPI routes
replay = ReplayState()
