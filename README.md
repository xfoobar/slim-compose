# slim-compose
Simple management tool for podman pods, pure Python, no third-party dependencies.

## requirements
- Podman 4.x (network backend: netavark)
- Python 3.11


## install
```
pipx install slim-compose
```

## usage
```sh
# create config file
slim-compose template
# edit config file
vim slim-compose-template.json
# rename config file
mv slim-compose-template.json slim-compose.json
# deploy pod
slim-compose up
# stop pod
slim-compose stop
# destroy pod
slim-compose down
# help
slim-compose -h
```