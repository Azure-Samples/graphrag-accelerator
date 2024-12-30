# Development Guide

This document is for developers interested in contributing to GraphRAG.

## Quickstart
Development is best done in a unix environment (Linux, Mac, or [Windows WSL](https://learn.microsoft.com/en-us/windows/wsl/install)).

1. Clone the GraphRAG repository.
1. Follow all directions in the [deployment guide](DEPLOYMENT-GUIDE.md) to install required tools and deploy an instance of the GraphRAG service in Azure. Alternatively, this repo provides a devcontainer with all tools preinstalled.
1. New unit tests and integration tests are currently being added to improve the developer experience when testing code changes locally.

### Testing

A small collection of unit tests and integrations tests have been written to test functionality of the API. To get started, first ensure that all test dependencies have been installed.

```shell
cd <graphrag-accelerator-repo>/backend
poetry install --with test
```

Some tests require the [azurite emulator](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite?toc=%2Fazure%2Fstorage%2Fblobs%2Ftoc.json&bc=%2Fazure%2Fstorage%2Fblobs%2Fbreadcrumb%2Ftoc.json&tabs=docker-hub%2Cblob-storage) and [cosmosdb emulator](https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-develop-emulator?tabs=docker-linux%2Ccsharp&pivots=api-nosql) to be running locally (these are setup in the ci/cd automatically). You may start these emulators by running them in the background as docker containers.

```shell
docker run -d -p 10000:10000 -p 10001:10001 -p 10002:10002 mcr.microsoft.com/azure-storage/azurite:latest
docker run -d -p 8081:8081 -p 1234:1234 mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-preview
```

To run the tests:

```shell
cd <graphrag-accelerator-repo>/backend
pytest -s --cov=src tests
```

### Deployment (CI/CD)
This repository uses Github Actions for continuous integration and continious deployment (CI/CD).

### Style Guide:
* We follow [PEP 8](https://peps.python.org/pep-0008) standards and naming conventions as close as possible.

* [ruff](https://docs.astral.sh/ruff) is used for linting and code formatting. A pre-commit hook has been setup to automatically apply settings to this repo. To make use of this tool without explicitly calling it, install the pre-commit hook.
    ```
    > pre-commit install
    ```

### Versioning
We use [SemVer](https://aka.ms/StartRight/README-Template/semver) for semantic versioning.
