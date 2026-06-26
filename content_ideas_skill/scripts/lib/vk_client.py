"""
lib/vk_client.py — обёртка VK API (заглушка для v0.1).

В v0.2 — реальная обёртка с методами:
  - get_posts(group_id, count)
  - get_comments(post_id, count)
  - get_group_info(group_id)

Требования:
  - VK API token в .env: VK_TOKEN=...
  - pip install requests python-dotenv
"""

import os
from typing import List, Dict, Any, Optional


class VKClient:
    """Обёртка VK API."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("VK_TOKEN", "")
        self.api_version = "5.131"
        self.base_url = "https://api.vk.com/method"

    def _call(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """v0.1 — заглушка. v0.2 — реальный HTTP-вызов."""
        # TODO v0.2: requests.post(self.base_url + "/" + method, params={**params, "access_token": self.token, "v": self.api_version})
        return {"response": None, "stub": True}

    def get_posts(self, group_id: str, count: int = 200) -> List[Dict[str, Any]]:
        """Получить последние N постов со стены сообщества."""
        # group_id должен быть отрицательным для сообществ
        owner_id = -int(group_id) if str(group_id).lstrip("-").isdigit() else group_id
        result = self._call("wall.get", {"owner_id": owner_id, "count": count})
        return result.get("response", {}).get("items", [])

    def get_comments(self, post_id: str, count: int = 100) -> List[Dict[str, Any]]:
        """Получить комменты к посту."""
        result = self._call("wall.getComments", {"post_id": post_id, "count": count})
        return result.get("response", {}).get("items", [])

    def get_group_info(self, group_id: str) -> Dict[str, Any]:
        """Получить инфо о сообществе."""
        result = self._call("groups.getById", {"group_id": group_id})
        return result.get("response", [{}])[0] if result.get("response") else {}
