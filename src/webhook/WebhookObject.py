import requests


class WebhookObject:

    def __init__(self, name, url):
        self.url = url
        self.name = name

    def send(self, title, message):
        payload = {
            "content": f"**{title}**\n{message}"
        }

        response = requests.post(
            self.url,
            params={"wait": "true"},
            json=payload,
            timeout=5,
        )

        response.raise_for_status()
        return response.json()
