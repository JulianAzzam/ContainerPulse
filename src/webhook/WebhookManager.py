from typing import List

from src.config import settings
from src.webhook.WebhookObject import WebhookObject


class WebhookManager:

    _instance = None
    _initialized = False
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            # Create the instance if it doesn't exist
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return  # Prevent re-initialization
        self.webhooks = []
        for webhook in settings["webhooks"]:
            name = webhook["name"]
            url = webhook["url"]
            self.webhooks.append(WebhookObject(name,url))
        self._initialized = True

    def get_webhooks(self) -> List[WebhookObject]:
        return self.webhooks

