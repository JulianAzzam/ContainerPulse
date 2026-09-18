

import json

from src.config import SETTINGS_PATH, settings
WEBHOOKS = "webhooks"

class WebhookConfigManager:
    def add(self, name, url):
        if WEBHOOKS not in settings:
            settings[WEBHOOKS] = []
        if name in ["discord", "slack"]:
            settings[WEBHOOKS].append({"name": name, "url": url})
        self.update_settings()

    def delete(self, name):
        if WEBHOOKS in settings:
            for ind, obj in enumerate(settings[WEBHOOKS]):
                if "name" in obj and obj["name"] == name:
                    settings[WEBHOOKS].pop(ind)
        self.update_settings()

    def update(self, name, url):
        for webhook in settings.get(WEBHOOKS, []):
            if webhook["name"] == name:
                webhook["url"] = url
                self.update_settings()
                return

        raise ValueError(f"Webhook '{name}' not found")

    def list(self):
        if WEBHOOKS in settings:
            print(settings[WEBHOOKS])
        else:
            print("No webhooks setup")


    def update_settings(self):
        with open(SETTINGS_PATH, "w") as file:
            json.dump(settings, file)
    