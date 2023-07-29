import os
import subprocess
import sys
from dataclasses import fields
from typing import Any, Sequence


def eprint(*args, **kwargs):
    """
    print to stderr
    :param args:
    :param kwargs:
    :return: None
    """
    print(*args, **kwargs, file=sys.stderr)


def nvl(*args):
    """
    return first non-null value
    :param args: values
    :return: first non-null value
    """
    for a in args:
        if a:
            return a
    return args[-1]


def execute_command(cmd: Sequence[str], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    stdin=sys.stdin, dry: bool = False) -> tuple[int, bytes, bytes]:
    """
    execute command
    :param cmd: command
    :param stdout:  stdout
    :param stderr:  stderr
    :param stdin:   stdin
    :param dry:    if True, do not execute command
    :return:    return code, stdout, stderr
    """
    ENCODING = 'utf-8'
    for c in cmd:
        if not isinstance(c, str):
            RuntimeError(f'non-str instance exists: {c} in {cmd}')
    command = [f"'{c}'" for c in cmd]
    print(f"command: {' '.join(command)}")
    if dry:
        return 0, b'', b''
    completed: subprocess.CompletedProcess = subprocess.run(
        cmd, stdout=stdout, stderr=stderr, stdin=stdin)
    return completed.returncode, completed.stdout, completed.stderr


def create_labels(location:Path) -> list[str]:
    """
    create labels
    :return: list of labels
    """
    labels = [f'location={cwd}', 'creator=slim-compose']
    args = []
    for label in labels:
        args.extend(['--label', label])
    return args


def is_volume(volume: str) -> bool:
    """
    check volume
    :param volume:  volume
    :return:    True if volume is valid
    """
    if not volume.startswith('.') and not volume.startswith('/'):
        return True
    else:
        return False


def load_from_config(config: dict, entity: Any):
    """
    load optional args
    :param config: config
    :param entity: entity
    :return: None
    """
    cls = type(entity)
    optional_list = [f.name for f in fields(cls) if f.default is None]
    for op in optional_list:
        json_op = op.replace('_', '-')
        value = config.get(json_op)
        if value:
            setattr(entity, op, value)


def list_entity(entity_type: str,location:Path) -> list[str]:
    """
    list entity
    :param entity_type: entity type
    :return:  entity list
    """
    ENCODING = 'utf-8'
    labels = [label for label in create_labels(location) if label != '--label']
    entity_list = []
    if entity_type == 'container':
        name_column = r'{{.Names}}'
    else:
        name_column = r'{{.Name}}'
    cmd = ['podman', entity_type, 'ls', '--format', name_column]
    for label in labels:
        cmd.extend(['--filter', f'label={label}'])
    _, stdout, _ = execute_command(cmd=cmd)
    entities = stdout.decode(ENCODING).split()
    entity_list.extend(entities)
    return entity_list
