"""Command line entrypoint for workshop-checker"""
import argparse
import sys
from typing import Optional


def parse_arguments(arguments: list[str]) -> argparse.Namespace:
    """Parse generic arguments, given as parameters"""
    parser = argparse.ArgumentParser(
        "workshop-checker",
        description="Arma Workshop mod update checker for Zeusops",
    )
    parser.add_argument("foo", help="Some parameter")
    return parser.parse_args(arguments)


def cli(arguments: Optional[list[str]] = None):
    """Run the workshop_checker cli"""
    if arguments is None:
        arguments = sys.argv[1:]
    args = parse_arguments(arguments)
    main(args.foo)


def main(foo):
    """Run the program's main command"""
    print(f"Foo is: {foo}")
