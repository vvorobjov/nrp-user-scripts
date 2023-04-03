#!/bin/bash

# NOTE:
# set the tag and repository if needed
export NRP_CORE_TAG="${NRP_CORE_TAG:-:latest}"
export NRP_DOCKER_REGISTRY="${NRP_DOCKER_REGISTRY:-docker-registry.ebrains.eu/}"

if [ -z "$HBP" ]; then
  echo "Your HBP variable is not set!"
  echo "Please, set it up:"
  echo "export HBP=<path with nrp-user-scripts repository folder>"
  exit 1
fi

if [ -z "$STORAGE_PATH" ]; then
    export STORAGE_PATH=$HOME/.opt/nrpStorage
    echo "STORAGE_PATH is set to default $STORAGE_PATH"
fi

#check if the storage exists
if [ ! -d "$STORAGE_PATH/FS_db" ] || [ ! -f "$STORAGE_PATH/FS_db/users" ]; then
    mkdir -p "$STORAGE_PATH" || { echo "ERROR, couldn't create $STORAGE_PATH"; exit 1;}
    docker compose run nrp-proxy-service node_modules/ts-node/dist/bin.js utils/createFSUser.ts --user nrpuser --password password
    docker compose down
fi

docker compose -f docker-compose_no-frontend.yaml up --abort-on-container-exit "$@"
