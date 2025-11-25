import json
from pathlib import Path
from typing import List, Dict, Any
import asyncio


class BaseAdapter:
    name: str = "Base"

    def fetch(self, rego: str, state: str) -> List[Dict[str, Any]]:
        """Synchronous fetch method."""
        raise NotImplementedError

    async def fetch_async(self, rego: str, state: str) -> List[Dict[str, Any]]:
        """Async version - demonstrates async pattern."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.fetch, rego, state)


class AutoPartsDirectAdapter(BaseAdapter):
    name = "AutoParts Direct"

    def fetch(self, rego: str, state: str) -> List[Dict[str, Any]]:
        demo_file = Path(__file__).parent / "data" / "supplier_a_demo.json"
        return json.loads(demo_file.read_text())


class PartsHubProAdapter(BaseAdapter):
    name = "PartsHub Pro"

    def fetch(self, rego: str, state: str) -> List[Dict[str, Any]]:
        demo_file = Path(__file__).parent / "data" / "supplier_b_demo.json"
        return json.loads(demo_file.read_text())


def get_enabled_adapters():
    return [
        AutoPartsDirectAdapter(),
        PartsHubProAdapter()
    ]
