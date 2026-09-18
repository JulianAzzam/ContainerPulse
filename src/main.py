
import argparse
import threading

from src.RuntimeCollector import RuntimeCollector
from src.notifier.Notifier import Notifier
from src.webhook.WebhookConfigManager import WebhookConfigManager
from src.webhook.WebhookManager import WebhookManager
from src.config import webhook_manager

def build_parser():
    parser = argparse.ArgumentParser(
        prog="containerpulse",
        description="Container workload anomaly detection agent",
    )

    subparsers = parser.add_subparsers(dest="command")

    start_parser = subparsers.add_parser(
        "start",
        help="Start the ContainerPulse monitoring agent",
    )

    start_parser.add_argument(
        "--verbose",
        action="store_true",
    )

    # -------------------------
    # webhooks
    # -------------------------
    webhooks_parser = subparsers.add_parser(
        "webhooks",
        help="Manage webhook configuration",
    )

    webhook_subparsers = webhooks_parser.add_subparsers(
        dest="webhook_command"
    )

    # containerpulse webhooks add NAME URL
    add_parser = webhook_subparsers.add_parser(
        "add",
        help="Add a webhook",
    )
    add_parser.add_argument("name")
    add_parser.add_argument("url")

    # containerpulse webhooks list
    webhook_subparsers.add_parser(
        "list",
        help="List configured webhooks",
    )

    # containerpulse webhooks remove NAME
    remove_parser = webhook_subparsers.add_parser(
        "remove",
        help="Remove a webhook",
    )
    remove_parser.add_argument("name")

    # containerpulse webhooks update NAME URL
    update_parser = webhook_subparsers.add_parser(
        "update",
        help="Update a webhook",
    )
    update_parser.add_argument("name")
    update_parser.add_argument("url")

    return parser

def handle_webhook_command(args):
    manager = WebhookConfigManager()

    if args.webhook_command == "add":
        manager.add(args.name, args.url)

    elif args.webhook_command == "list":
        manager.list()

    elif args.webhook_command == "remove":
        manager.delete(args.name)

    elif args.webhook_command == "update":
        manager.update(args.name, args.url)

    else:
        print("Missing webhook command")


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "start":
        start_containerpulse(args)
        return

    if args.command == "webhooks":
        handle_webhook_command(args)
        return

    parser.print_help()


def start_containerpulse(args):
    
    global webhook_manager
    webhook_manager = WebhookManager()
    notification_manager = Notifier()
    stop_event = threading.Event()
    events_thread = threading.Thread(target=notification_manager.listen,kwargs={"webhook_manager": webhook_manager, "stop_event": stop_event},daemon=True)
    events_thread.start()
    try:
        collector = RuntimeCollector(vars(args))
        collector.run()
    except KeyboardInterrupt:
        stop_event.set()
        return

if __name__ == "__main__":
    main()