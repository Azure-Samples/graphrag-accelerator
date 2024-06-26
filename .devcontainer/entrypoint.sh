#!/bin/bash

################################
### Docker configuration ###
################################
sudo chmod 666 /var/run/docker.sock

################################
### Dependency configuration ###
################################

# Install graphrag dependencies
cd /graphrag-accelerator
poetry install --no-interaction -v

#########################
### Git configuration ###
#########################

git config --global --add safe.directory /graphrag-accelerator
pre-commit install
