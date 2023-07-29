#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, fields
from functools import cache
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

from slim_compose.args import Args, Command
from slim_compose.utils import (create_labels, eprint, execute_command,
                                is_volume, list_entity, load_from_config, nvl)


@dataclass
class Container:
    """
    container
    """
    name: str  # container name
    image: str  # image name
    pod: str  # pod name
    location: Path # config file location
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
        r.extend(create_labels(self))
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
        self.infra_name = nvl(self.infra_name, f'{self.name}-infra')
        r.extend(['--infra-name', self.infra_name])

        self.network_alias = nvl(self.network_alias, self.name)
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


class SlimCompose:
    def __init__(self, config_file: Path, dry: bool):
        self.config_file = config_file
        self.dry = dry
        self.location=config_file.resolve().parent()

    def start(self):
        self.__opration('start')

    def stop(self):
        self.__opration('stop')

    def restart(self):
        self.__opration('restart')

    def up(self, disable_network: bool):
        pod = self.__create_pod_from_config()
        labels = create_labels()
        # default network
        if not pod.networks and not disable_network:
            pod.networks = [f'{pod.name}-default']
        # create network
        for net in nvl(pod.networks, []):
            if not self.exists('network', net):
                cmd = ['podman', 'network', 'create']
                cmd.extend(labels)
                cmd.append(net)
                self.__execute(cmd=cmd)
        # create pod
        cmd = ['podman', 'pod', 'create']
        cmd.extend(pod.make_command())
        self.__execute(cmd=cmd)
        # create volume
        for ctr in pod.containers:
            for vol in nvl(ctr.volumes, []):
                vol_name = vol.split(':', 2)[0]
                if is_volume(vol_name) and not self.exists('volume', vol_name):
                    cmd = ['podman', 'volume', 'create']
                    cmd.extend(labels)
                    cmd.append(vol_name)
                    self.__execute(cmd=cmd)
        # create container
        for container in pod.containers:
            cmd = ['podman', 'run', '-d']
            cmd.extend(container.make_command())
            self.__execute(cmd=cmd)
        print('Created.')

    def down(self, all: bool):
        """
        destroy pod
        :param dry: dry run
        :return: None
        """
        entity_types: list
        if all:
            entity_types = ['pod', 'container', 'network', 'volume']
        else:
            entity_types = ['pod', 'container']
        for entity_type in entity_types:
            entities = list_entity(entity_type=entity_type,location=self.location)
            for e in entities:
                # stop pod and container
                if entity_type in ('pod', 'container'):
                    cmd = ['podman', entity_type, 'stop', e]
                    self.__execute(cmd=cmd, ignore_error=True)
                cmd = ['podman', entity_type, 'rm', e]
                self.__execute(cmd=cmd, ignore_error=True)
        print('Finished.')

    def template(sefl, template_file: Path):
        """
        create template file
        :param file_name:  file_name
        :param dry: dry run
        :return: None
        """
        template = {
            "pod": {
                "name": "pod-name",
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
                        "name": "container-name",
                        "image": "image-name",
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
        josn_str = json.dumps(template, indent=2)
        if sefl.dry:
            print(josn_str)
            return
        with open(template_file, "w") as f:
            f.write(josn_str)
#########################

    def __execute(self, cmd: Sequence[str], ignore_error: bool = False) -> int:
        r, _, _ = execute_command(cmd=cmd, dry=self.dry)
        if not ignore_error and r != 0:
            eprint(f'error: code={r}')
            exit(r)
        return r

    def exists(self, entity_type: str, name: str) -> bool:
        """
        check entity exists
        :param dry: dry run
        :param entity_type: entity type
        :param name:    entity name
        :return:
        """
        cmd = ['podman', entity_type, 'exists', name]
        r, _, _ = execute_command(cmd=cmd, dry=self.dry)
        if self.dry:
            return False
        else:
            return True if r == 0 else False

    def __opration(self, op: str):
        pod = self.__create_pod_from_config()
        cmd = ['podman', 'pod', op, pod.name]
        code = self.__execute(cmd=cmd, )
        sys.exit(code)

    @cache
    def __create_pod_from_config(self) -> Pod:
        """
        create pod from config
        :return:    pod
        """
        config = json.loads(self.config_file.read_text())
        # create pod
        pod_config = config['pod']
        pod = Pod(name=pod_config['name'])
        load_from_config(config=pod_config, entity=pod)
        # load Containers
        containers_config = config['pod']['containers']
        for ctr_config in containers_config:
            container = Container(
                name=f"{pod.name}-{ctr_config['name']}",
                image=ctr_config['image'],
                pod=pod.name)
            load_from_config(config=ctr_config, entity=container)
            # rename requires
            container.requires = [
                f'{pod.name}-{req}' for req in nvl(container.requires, [])]
            # add container
            pod.containers.append(container)
        return pod


def main():
    args = Args()
    compose = SlimCompose(config_file=args.config_file, dry=args.dry)
    if args.command == Command.Start.value:
        compose.start()
    if args.command == Command.Stop.value:
        compose.stop()
    if args.command == Command.Restart.value:
        compose.restart()
    if args.command == Command.Up.value:
        compose.up(disable_network=args.disable_network)
    if args.command == Command.Down.value:
        compose.down(all=args.all)
    if args.command == Command.Template.value:
        compose.template(args.template_file)


if __name__ == '__main__':
    main()
