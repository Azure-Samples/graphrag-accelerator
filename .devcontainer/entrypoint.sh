#!/bin/bash

################################
### Docker configuration ###
################################
sudo chmod 666 /var/run/docker.sock

################################
### Dependency configuration ###
################################

# Install graphrag dependencies
# NOTE: temporarily copy the pyproject.toml and poetry.lock files to the root directory to install dependencies.
# This avoids having a .venv folder in the backend directory, which causes PATH issues when building the
# backend docker image during deployment
ROOT_DIR=/graphrag-accelerator
cd ${ROOT_DIR}
cp ${ROOT_DIR}/backend/pyproject.toml ${ROOT_DIR}
cp ${ROOT_DIR}/backend/poetry.lock ${ROOT_DIR}
poetry install --no-interaction -v
rm ${ROOT_DIR}/pyproject.toml
rm ${ROOT_DIR}/poetry.lock

#########################
### Git configuration ###
#########################
git config --global --add safe.directory ${ROOT_DIR}
pre-commit install
