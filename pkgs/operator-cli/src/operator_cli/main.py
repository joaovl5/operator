"""Argument parser entrypoints for the Operator CLI."""

import argparse
from collections.abc import Callable, Sequence

from operator_cli.auth.main import run_openai_login, run_openai_logout, run_openai_status

type Handler = Callable[[argparse.Namespace], int]


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level Operator argument parser."""
    parser = argparse.ArgumentParser(
        prog="operator",
        description="Operator command-line interface.",
        epilog=(
            "Auth commands:\n"
            "  operator auth openai login\n"
            "  operator auth openai logout\n"
            "  operator auth openai status"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command_group", required=True)

    auth_parser = subparsers.add_parser("auth", help="Authentication commands")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_provider_group", required=True)

    openai_parser = auth_subparsers.add_parser("openai", help="OpenAI authentication commands")
    openai_subparsers = openai_parser.add_subparsers(dest="auth_action", required=True)

    login_parser = openai_subparsers.add_parser("login", help="Log in with OpenAI OAuth")
    login_parser.set_defaults(command_id="auth.openai.login", handler=_handle_openai_login)

    logout_parser = openai_subparsers.add_parser("logout", help="Log out of OpenAI OAuth")
    logout_parser.set_defaults(command_id="auth.openai.logout", handler=_handle_openai_logout)

    status_parser = openai_subparsers.add_parser("status", help="Show OpenAI OAuth status")
    status_parser.set_defaults(command_id="auth.openai.status", handler=_handle_openai_status)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and dispatch to the selected command handler."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv   else None)
    command_id = getattr(args, "command_id", None)
    match command_id:
        case "auth.openai.login":
            return _handle_openai_login(args)
        case "auth.openai.logout":
            return _handle_openai_logout(args)
        case "auth.openai.status":
            return _handle_openai_status(args)
        case _:
            parser.print_help()
            return 1


def _handle_openai_login(_args: argparse.Namespace) -> int:
    return run_openai_login()


def _handle_openai_logout(_args: argparse.Namespace) -> int:
    return run_openai_logout()


def _handle_openai_status(_args: argparse.Namespace) -> int:
    return run_openai_status()
