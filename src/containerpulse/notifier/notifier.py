from threading import Event

from ..config import event_queue
from ..events.anomaly_event import AnomalyEvent
from ..webhook.webhook_manager import WebhookManager
from ..webhook.webhook_object import WebhookObject



class Notifier:
    """
    Listens for anomalies pushed to the event_queue on a separate thread
    Calls all available webhooks.
    """
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
        self._initialized = True

    def listen(self, webhook_manager: WebhookManager, stop_event: Event):
        webhooks = webhook_manager.get_webhooks()
        while not stop_event.is_set():
            if event_queue.qsize != 0:
                anomaly :AnomalyEvent = event_queue.get()
                webhook : WebhookObject
                for webhook  in webhooks:
                    webhook.send(anomaly.title, anomaly.message)
                event_queue.task_done()
     
                
