# slim-compose
Simple management tool for podman pods, written by pure Python, no third-party dependencies.

## requirements
- Podman 4.4.2 ( networkBackend: netavark )
- Python 3.10


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
# destroy pod
slim-compose down
```