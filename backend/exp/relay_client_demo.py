#!/usr/bin/env python3
import argparse
import sys
import threading
import time
from datetime import datetime

import roslibpy


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9090
DEFAULT_STATE_TOPIC = "/usv_std/relay/enabled"
DEFAULT_COMMAND_TOPIC = "/usv_std/relay/set_enabled"

TRUE_TOKENS = {"1", "true", "on", "enable", "enabled", "yes", "y"}
FALSE_TOKENS = {"0", "false", "off", "disable", "disabled", "no", "n"}
QUIT_TOKENS = {"q", "quit", "exit"}


def parse_enabled_token(value):
    normalized = value.strip().lower()
    if normalized in TRUE_TOKENS:
        return True
    if normalized in FALSE_TOKENS:
        return False
    raise ValueError("expected one of: on/off, enable/disable, true/false, 1/0")


def describe_enabled(enabled):
    if enabled:
        return "ENABLED -> GPIO 0 -> relay closed"
    return "DISABLED -> GPIO 1 -> relay open"


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect_ros(args):
    ros = roslibpy.Ros(host=args.host, port=args.port)
    try:
        ros.run(timeout=args.timeout)
    except Exception as exc:
        raise RuntimeError(
            "failed to connect to rosbridge at ws://{}:{} ({})".format(
                args.host,
                args.port,
                exc,
            )
        ) from exc

    if not ros.is_connected:
        raise RuntimeError(
            "failed to connect to rosbridge at ws://{}:{} within {:.1f}s".format(
                args.host,
                args.port,
                args.timeout,
            )
        )

    print("connected: ws://{}:{}".format(args.host, args.port))
    return ros


def make_state_topic(ros, args):
    return roslibpy.Topic(
        ros,
        args.state_topic,
        "std_msgs/Bool",
    )


def make_command_topic(ros, args):
    return roslibpy.Topic(
        ros,
        args.command_topic,
        "std_msgs/Bool",
    )


def print_state_message(message):
    enabled = bool(message.get("data", False))
    print(
        "[{}] raw={} | {}".format(
            now_text(),
            message,
            describe_enabled(enabled),
        ),
        flush=True,
    )


def publish_command(topic, enabled):
    topic.publish(roslibpy.Message({"data": bool(enabled)}))
    print(
        "sent: data={} | {}".format(
            str(bool(enabled)).lower(),
            describe_enabled(bool(enabled)),
        ),
        flush=True,
    )


def run_watch(args):
    ros = connect_ros(args)
    state_topic = make_state_topic(ros, args)
    stop_event = threading.Event()

    def on_state(message):
        print_state_message(message)

    state_topic.subscribe(on_state)
    print("watching {}. Press Ctrl-C to stop.".format(args.state_topic))

    try:
        while not stop_event.wait(0.5):
            pass
    except KeyboardInterrupt:
        print("\nstopping watch")
    finally:
        state_topic.unsubscribe()
        ros.terminate()

    return 0


def run_set(args):
    enabled = parse_enabled_token(args.value)
    ros = connect_ros(args)
    command_topic = make_command_topic(ros, args)
    try:
        publish_command(command_topic, enabled)
        time.sleep(args.post_publish_delay)
    finally:
        command_topic.unadvertise()
        ros.terminate()
    return 0


def run_interactive(args):
    ros = connect_ros(args)
    state_topic = make_state_topic(ros, args)
    command_topic = make_command_topic(ros, args)

    def on_state(message):
        print_state_message(message)

    state_topic.subscribe(on_state)
    print("interactive mode")
    print("commands: on, off, q")

    try:
        while True:
            try:
                value = input("> ").strip()
            except EOFError:
                print()
                break

            if not value:
                continue

            normalized = value.lower()
            if normalized in QUIT_TOKENS:
                break

            try:
                enabled = parse_enabled_token(value)
            except ValueError as exc:
                print("invalid command: {}".format(exc), file=sys.stderr)
                continue

            publish_command(command_topic, enabled)
    except KeyboardInterrupt:
        print("\nstopping interactive mode")
    finally:
        state_topic.unsubscribe()
        command_topic.unadvertise()
        ros.terminate()

    return 0


def add_common_args(parser):
    parser.add_argument("--host", default=DEFAULT_HOST, help="rosbridge host")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int, help="rosbridge port")
    parser.add_argument(
        "--state-topic",
        default=DEFAULT_STATE_TOPIC,
        help="std_msgs/Bool state topic",
    )
    parser.add_argument(
        "--command-topic",
        default=DEFAULT_COMMAND_TOPIC,
        help="std_msgs/Bool command topic",
    )
    parser.add_argument(
        "--timeout",
        default=10.0,
        type=float,
        help="rosbridge connection timeout in seconds",
    )


def build_parser():
    parser = argparse.ArgumentParser(
        description="Local roslibpy relay control demo for usv_std.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    watch_parser = subparsers.add_parser("watch", help="print relay state messages")
    add_common_args(watch_parser)
    watch_parser.set_defaults(handler=run_watch)

    set_parser = subparsers.add_parser("set", help="send one relay command")
    add_common_args(set_parser)
    set_parser.add_argument("value", help="on/off, enable/disable, true/false, 1/0")
    set_parser.add_argument(
        "--post-publish-delay",
        default=0.25,
        type=float,
        help="delay before disconnecting after publish",
    )
    set_parser.set_defaults(handler=run_set)

    interactive_parser = subparsers.add_parser(
        "interactive",
        help="print relay state and accept on/off commands",
    )
    add_common_args(interactive_parser)
    interactive_parser.set_defaults(handler=run_interactive)

    return parser


def main():
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except ValueError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
