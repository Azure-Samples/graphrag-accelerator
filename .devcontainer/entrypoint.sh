#!/bin/bash

################################
### Docker configuration ###
################################
sudo chmod 666 /var/run/docker.sock

################################
### Dependency configuration ###
################################

# Install graphrag dependencies
ROOT_DIR=/graphrag-accelerator
cd ${ROOT_DIR}
poetry install --no-interaction -v --directory ${ROOT_DIR}/backend

#########################
### Git configuration ###
#########################
git config --global --add safe.directory ${ROOT_DIR}
pre-commit install
