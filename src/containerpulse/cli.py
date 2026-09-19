
import argparse
import logging
import threading

from .runtime_collector import RuntimeCollector
from .notifier.notifier import Notifier
from .webhook.webhook_config_manager import WebhookConfigManager
from .webhook.webhook_manager import WebhookManager
from .config import webhook_manager

def build_parser():
    """
    Build and return the ContainerPulse command-line interface parser.
    """
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
    """
    Dispatch webhook configuration subcommands such as add, list,
    remove, and update.
    """
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
    """
    Parse CLI arguments and dispatch the selected ContainerPulse command.
    """
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
    """
    Start the ContainerPulse monitoring agent.

    Initializes logging, webhook delivery, the notification worker,
    and the runtime collector, then keeps the monitoring process active
    until interrupted.
    """
    configure_logging(args.verbose)

    global webhook_manager
    webhook_manager = WebhookManager()
    notification_manager = Notifier()
    stop_event = threading.Event()
    events_thread = threading.Thread(target=notification_manager.listen,kwargs={"webhook_manager": webhook_manager, "stop_event": stop_event},daemon=True)
    events_thread.start()
    try:
        RuntimeCollector(vars(args))
    except KeyboardInterrupt:
        stop_event.set()
        return

def configure_logging(verbose=False):
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format=(
                "%(asctime)s | %(levelname)s | "
                "%(name)s | %(message)s"
            ),
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s | %(message)s",
        )

if __name__ == "__main__":
    main()