#!/usr/bin/env python3

from dataclasses import dataclass, field, fields
from typing import Dict, Optional, Sequence, Mapping, Callable, Any
import subprocess
import sys
from pathlib import Path
import os
import subprocess
import json
import argparse

APP_VERSION = '1.0.2'

ENCODING = 'utf-8'


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


def eprint(*args, **kwargs):
    """
    print to stderr
    :param args:
    :param kwargs:
    :return: None
    """
    print(*args, **kwargs, file=sys.stderr)


def exec_cmd(cmd: Sequence[str], ignore_error: bool = True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
             stdin=sys.stdin, dry: bool = False) -> tuple:
    """
    execute command
    :param cmd: command
    :param ignore_error:    if True, ignore error
    :param stdout:  stdout
    :param stderr:  stderr
    :param stdin:   stdin
    :param dry:    if True, do not execute command
    :return:    return code, stdout, stderr
    """
    for c in cmd:
        if not isinstance(c, str):
            RuntimeError(f'not str: {c} cmd: {cmd}')
    command = [f"'{c}'" for c in cmd]
    print(f"command:{' '.join(command)}")
    if dry:
        return 0, b'', b''
    completed: subprocess.CompletedProcess = subprocess.run(
        cmd, stdout=stdout, stderr=stderr, stdin=stdin)
    r = completed.returncode
    if r == 0:
        print(completed.stdout.decode('utf-8'))
    else:
        eprint(completed.stderr.decode('utf-8'))
    if not ignore_error and r != 0:
        raise RuntimeError(f'error: exit_code={r}')
    return completed.returncode, completed.stdout, completed.stderr


def create_labels() -> list[str]:
    """
    create labels
    :return: list of labels
    """
    cwd = os.getcwd()
    labels = [f'location={cwd}', 'creator=slim-compose',
              f'version={APP_VERSION}']
    args = []
    for label in labels:
        args.extend(['--label', label])
    return args


def list_relevant_entity(entity_type: str) -> list[str]:
    """
    list relevant entity
    :param entity_type: entity type
    :return:  entity list
    """
    labels = [label for label in create_labels() if label != '--label']
    entity_list = []
    if entity_type == 'container':
        name_column = r'{{.Names}}'
    else:
        name_column = r'{{.Name}}'
    cmd = ['podman', entity_type, 'ls', '--format', name_column]
    for label in labels:
        cmd.extend(['--filter', f'label={label}'])
    _, stdout, _ = exec_cmd(cmd=cmd, ignore_error=False)
    entities = stdout.decode(ENCODING).split()
    entity_list.extend(entities)
    return entity_list


@dataclass
class Container:
    """
    container
    """
    name: str  # container name
    image: str  # image name
    pod: str  # pod name
    environments: list[str] | None = None  # environment variables
    requires: list[str] | None = None  # required containers
    tz: str | None = None  # timezone
    user: str | None = None  # user
    volumes: list[str] | None = None  # volumes
    capabilities: list[str] | None = None  # capabilities
    workdir: str | None = None  # workdir
    custom_args: list[str] | None = None  # custom args
    entrypoint: Sequence | None = None  # entrypoint
    command: list[str] | None = None  # command

    def make_command(self) -> list[str]:
        """
        make command
        """
        r = ['--name', self.name]

        if self.pod:
            r.extend(['--pod', self.pod])

        for e in nvl(self.environments, []):
            r.extend(['--env', e])

        if self.requires:
            r.extend(['--requires', ','.join(self.requires)])

        if self.tz:
            r.extend(['--tz', self.tz])

        if self.user:
            r.extend(['--user', self.user])

        if self.entrypoint:
            json_str = json.dumps(self.entrypoint)
            r.extend(['--entrypoint', json_str])

        for vol in nvl(self.volumes, []):
            r.extend(['--volume', vol])

        for cap in nvl(self.capabilities, []):
            r.extend(['--cap-add', cap])

        if self.workdir:
            r.extend(['--workdir', self.workdir])

        if self.custom_args:
            r.extend(self.custom_args)
        #  add labels
        r.extend(create_labels())
        r.append(self.image)
        if self.command:
            r.extend(self.command)
        return r


@dataclass
class Pod:
    """
    pod
    """
    name: str  # pod name
    infra_name: str | None = None  # infra container name
    network_alias: str | None = None  # network alias
    networks: list[str] | None = None  # networks
    ports: list[str] | None = None  # ports
    sysctls: list[str] | None = None  # sysctls
    cpus: int | None = None  # cpus
    memory: str | None = None  # memory
    userns: str | None = None  # userns
    custom_args: list[str] | None = None  # custom args
    containers: list[Container] = field(
        default_factory=list[Container])  # containers

    def make_command(self) -> list[str]:
        """
        make command
        """
        r = ['--name', self.name]
        if self.infra_name:
            r.extend(['--infra-name', self.infra_name])
        else:
            r.extend(['--infra-name', f'{self.name}-infra'])

        if self.network_alias:
            r.extend(['--network-alias', self.network_alias])
        else:
            r.extend(['--network-alias', self.name])

        for net in nvl(self.networks, []):
            r.extend(['--network', net])

        for port in nvl(self.ports, []):
            r.extend(['--publish', port])

        for ctl in nvl(self.sysctls, []):
            r.extend(['--sysctl', ctl])

        if self.cpus:
            r.extend(['--cpus', str(self.cpus)])

        if self.memory:
            r.extend(['--memory', self.memory])

        if self.userns:
            r.extend(['--userns', self.userns])

        if self.custom_args:
            r.extend(self.custom_args)
        #  add labels
        r.extend(create_labels())
        return r


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


def load_optional_args(config: Dict, entity: Any):
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


def get_config_file():
    """
    get config file
    :return: path of config file
    """
    return Path(os.getcwd()) / 'slim-compose.json'


def load_pod_from_config() -> Pod:
    """
    load pod from config
    :return:    pod
    """
    config_file = get_config_file()
    with open(config_file) as jf:
        config_data = json.load(jf)
    # load Pod
    pod_config = config_data['pod']
    pod = Pod(name=pod_config['name'])
    # set default network
    if not pod.networks:
        pod.networks = [f'{pod.name}-default']
    load_optional_args(config=pod_config, entity=pod)
    # load Containers
    container_config = config_data['pod']['containers']
    for ctr_config in container_config:
        container = Container(
            name=f"{pod.name}-{ctr_config['name']}",
            image=ctr_config['image'],
            pod=pod.name)
        load_optional_args(config=ctr_config, entity=container)
        # rename requires
        container.requires = [
            f'{pod.name}-{req}' for req in nvl(container.requires, [])]
        # add container
        pod.containers.append(container)
    return pod


def exists(entity_type: str, name: str, dry: bool) -> bool:
    """
    check entity exists
    :param dry: dry run
    :param entity_type: entity type
    :param name:    entity name
    :return:
    """
    cmd = ['podman', entity_type, 'exists', name]
    if dry:
        return False
    r, _, _ = exec_cmd(cmd=cmd)
    return True if r == 0 else False


def create(pod: Pod, dry: bool):
    """
    create pod
    :param pod:
    :param dry:
    :return:
    """
    labels = create_labels()
    # create network
    for net in nvl(pod.networks, []):
        if not exists('network', net, dry=dry):
            cmd = ['podman', 'network', 'create']
            cmd.extend(labels)
            cmd.append(net)
            exec_cmd(cmd=cmd, ignore_error=False, dry=dry)
    # create pod
    cmd = ['podman', 'pod', 'create']
    cmd.extend(pod.make_command())
    exec_cmd(cmd=cmd, ignore_error=False, dry=dry)
    # create volume
    for ctr in pod.containers:
        for vol in nvl(ctr.volumes, []):
            vol_name = vol.split(':', 2)[0]
            if is_volume(vol_name) and not exists('volume', vol_name, dry=dry):
                cmd = ['podman', 'volume', 'create']
                cmd.extend(labels)
                cmd.append(vol_name)
                exec_cmd(cmd=cmd, ignore_error=False, dry=dry)
    # create container
    for container in pod.containers:
        cmd = ['podman', 'run', '-d']
        cmd.extend(container.make_command())
        exec_cmd(cmd=cmd, ignore_error=False, dry=dry)
    print('Created.')


def destroy(all: bool, dry: bool):
    """
    destroy pod
    :param dry: dry run
    :return: None
    """
    entity_types = ['pod', 'container', 'network']
    if all:
        entity_types = ['pod', 'container', 'network', 'volume']
    for entity_type in entity_types:
        entities = list_relevant_entity(entity_type=entity_type)
        for e in entities:
            # stop pod and container
            if entity_type in ('pod', 'container'):
                cmd = ['podman', entity_type, 'stop', e]
                exec_cmd(cmd=cmd, ignore_error=False, dry=dry)
            cmd = ['podman', entity_type, 'rm', e]
            exec_cmd(cmd=cmd, ignore_error=False, dry=dry)
    print('Finished.')


def pod_operate(op: str, dry: bool):
    """
    operate pod
    :param op: operation
    :param dry: dry run
    :return: None
    """
    if op not in ['start', 'stop', 'restart']:
        raise RuntimeError(f'Invalid operation: {op}')
    pods = list_relevant_entity(entity_type='pod')
    for pod in pods:
        cmd = ['podman', 'pod', op, pod]
        exec_cmd(cmd=cmd, ignore_error=False, dry=dry)
    print('Finished.')


def create_template_file(file_name: Path, dry: bool):
    """
    create template file
    :param file_name:  file_name
    :param dry: dry run
    :return: None
    """
    template = {
        "pod": {
            "name": "pod_name",
            "infra-name": None,
            "network-alias": None,
            "networks": [],
            "ports": [],
            "sysctls": [],
            "cpus": None,
            "memory": None,
            "userns": None,
            "custom-args": [],
            "containers": [
                {
                    "name": "container_name",
                    "image": "image_name",
                    "environments": [],
                    "requires": [],
                    "tz": "Asia/Shanghai",
                    "user": None,
                    "volumes": [],
                    "capabilities": [],
                    "workdir": None,
                    "custom-args": [],
                    "entrypoint": [],
                    "command": []
                }
            ]
        }
    }
    josn_str = json.dumps(template, indent=4)
    if dry:
        print(josn_str)
        return
    with open(file_name, "w") as f:
        f.write(josn_str)


def init_args():
    """
    init args
    :return:
    """
    parser = argparse.ArgumentParser(
        prog=f'slim-compose',
        description='podman pod manager',
        epilog='cofnig file: slim-compose.json')
    parser.add_argument('action', choices=[
        'start', 'stop',
        'up', 'down', 'down-all',
        'restart', 'template'
    ], help='Action')
    parser.add_argument('--dry', action='store_true',
                        help='dry run', required=False)
    parser.add_argument('--version', action='version',
                        version=f'%(prog)s {APP_VERSION}')
    args = parser.parse_args()
    return args


def main():
    """
    main
    :return:
    """
    args = init_args()
    dry = args.dry
    if args.action == 'up':
        pod = load_pod_from_config()
        create(pod=pod, dry=dry)
    if args.action == 'down':
        destroy(all=False, dry=dry)
    if args.action == 'down-all':
        destroy(all=True, dry=dry)
    if args.action in ['start', 'stop', 'restart']:
        pod_operate(op=args.action, dry=dry)
    if args.action == 'template':
        template_file = Path(os.getcwd()) / 'slim-compose-template.json'
        create_template_file(file_name=template_file, dry=dry)
        print(f'{template_file} has been generated.')


if __name__ == '__main__':
    main()
