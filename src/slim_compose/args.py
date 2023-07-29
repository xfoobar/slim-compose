import argparse
import importlib.metadata
import os
# import tomllib
from dataclasses import asdict, dataclass
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Mapping, Optional, Sequence


@cache
def project_root() -> Path:
    """Find the project root directory by locating pyproject.toml."""
    # current_file = Path(__file__)
    # for parent_directory in current_file.parents:
    #     if (parent_directory / "pyproject.toml").is_file():
    #         return parent_directory
    raise FileNotFoundError(
        "Could not find project root containing pyproject.toml")


@cache
def version() -> str:
    pyproject_toml_version = None
    try:
        # Probably this is the pyproject.toml of a development install
        pyproject_toml = project_root() / "pyproject.toml"
    except FileNotFoundError:
        # Probably not a development install
        pyproject_toml = None

    if pyproject_toml is not None:
        return tomllib.loads(pyproject_toml.read_text())["project"]["version"]
    else:
        return importlib.metadata.version(
            __package__ or __name__).removesuffix('+editable')


class Command(Enum):
    Start = 'start'
    Stop = 'stop'
    Restart = 'restart'
    Up = 'up'
    Down = 'down'
    Template = 'template'


def args_init(args: Sequence[str] | None = None):
    parser = argparse.ArgumentParser(prog=f'slim-compose',
                                     description='podman pod manager',
                                     epilog='cofnig file: slim-compose.json')
    parser.add_argument('--dry',
                        action='store_true',
                        help='dry run',
                        required=False)
    parser.add_argument('--config',
                        action='store',
                        help='specify configuration file',
                        required=False)
    # Command
    subparsers = parser.add_subparsers(help='command', required=True)
    # Start
    start_parser = subparsers.add_parser(Command.Start.value, help='start pod')
    start_parser.set_defaults(which=Command.Start.value)
    # Stop
    stop_parser = subparsers.add_parser(Command.Stop.value, help='stop pod')
    stop_parser.set_defaults(which=Command.Stop.value)
    # Rrestart
    restart_parser = subparsers.add_parser(Command.Restart.value,
                                           help='restart pod')
    restart_parser.set_defaults(which=Command.Restart.value)
    # Up
    up_parser = subparsers.add_parser(Command.Up.value, help='up pod')
    up_parser.add_argument('--disable-network',
                           action='store_true',
                           help='do not create default network')
    up_parser.set_defaults(which=Command.Up.value)
    # Down
    down_parser = subparsers.add_parser(Command.Down.value, help='down pod')
    down_parser.add_argument('--all',
                             action='store_true',
                             help='include network,volume')
    down_parser.set_defaults(which=Command.Down.value)
    # Template
    template_parser = subparsers.add_parser(Command.Template.value,
                                            help='output template')
    template_parser.add_argument('template_file',
                                 action='store',
                                 help='template file',
                                 nargs='?')
    template_parser.set_defaults(which=Command.Template.value)
    # Version
    parser.add_argument('--version',
                        action='version',
                        version=f'%(prog)s {version()}')
    return parser.parse_args(args=args)


@dataclass
class Args:
    dry: bool | None = None
    config_file: Path | None = None
    command: str | None = None
    # values
    disable_network: bool | None = None
    template_file: Path | None = None
    all: bool | None = None

    def __init__(self, args=args_init()):
        self.dry = args.dry
        if args.config:
            self.config_file = Path(args.config)
        else:
            self.config_file = (Path(os.getcwd()) /
                                'slim-compose.json').resolve()
        self.command = args.which
        if self.command == Command.Up.value:
            self.disable_network = args.disable_network
        if self.command == Command.Down.value:
            self.all = args.all
        if self.command == Command.Template.value:
            if args.template_file:
                self.template_file = (Path(args.template_file)).resolve()
            else:
                self.template_file = (Path(os.getcwd()) /
                                      'slim-compose-template.json').resolve()


if __name__ == '__main__':
    print(args_init())
    print(Args())
