# Development Guide

This document is for developers interested in contributing to GraphRAG.

## Quickstart
Development is best done in a unix environment (Linux, Mac, or [Windows WSL](https://learn.microsoft.com/en-us/windows/wsl/install)).

1. Clone the GraphRAG repository.
1. Follow all directions in the [deployment guide](DEPLOYMENT-GUIDE.md) to install required tools and deploy an instance of the GraphRAG service in Azure. Alternatively, this repo provides a devcontainer with all tools preinstalled.
1. Create a `.env` file in the root of the repository (`GraphRAG/.env`). A detailed description of environment variables used to configure graphrag can be found [here](https://microsoft.github.io/graphrag). Add the following environment variables to the `.env` file:

    | Environment Variable | Description |
    | :--- | ---: |
    `COSMOS_URI_ENDPOINT`                | Azure CosmosDB connection string from graphrag deployment
    `STORAGE_ACCOUNT_BLOB_URL`           | Azure Storage blob url from graphrag deployment
    `AI_SEARCH_URL`                      | AI search endpoint from graphrag deployment (will be in the form of https://\<name\>.search.windows.net)
    `GRAPHRAG_API_BASE`                  | The AOAI API Base URL.
    `GRAPHRAG_API_VERSION`               | The AOAI API version (i.e. `2023-03-15-preview`)
    `GRAPHRAG_LLM_MODEL`                 | The AOAI model name (i.e. `gpt-4`)
    `GRAPHRAG_LLM_DEPLOYMENT_NAME`       | The AOAI model deployment name (i.e. `gpt-4-turbo`)
    `GRAPHRAG_EMBEDDING_MODEL`           | The AOAI model name (i.e. `text-embedding-ada-002`)
    `GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME` | The AOAI model deployment name (i.e.`my-text-embedding-ada-002`)
    `REPORTERS`                          | A comma-delimited list of logging that will be enabled. Possible values are `blob,console,file`

1. Developing inside the devcontainer
    1. Requirements
        - [Docker](https://www.docker.com/)
        - [Visual Studio Code](https://code.visualstudio.com/)
        - [Remote - Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.vscode-remote-extensionpack) for VS Code

    1. Open VS Code in the directory containing your project.
        - Use the Command Palette (Ctrl+Shift+P on Windows/Linux, Cmd+Shift+P on macOS) and type "Remote-Containers: Open Folder in Container..."
        - Select your project folder and VS Code will start building the Docker container based on the Dockerfile and devcontainer.json in your project. This process may take a few minutes, especially on the first run.
        - Once your vscode prompt appears, it may not be done. You should wait for the following prompt to appear to ensure full install is complete. `vscode@<hostname>:/graphrag$`

    1. Adding Python packages to the dev container.
        - Poetry is the Python package manager in the dev container. Python packages can be added using `poetry add <package-name>`
        - Everytime a package is added it will update `poetry.lock` and `pyproject.toml`, these are the two files that track all package management. Changes to these file should be checked into the repo. That is how we keep our devcontainer consistent across users.
        - Its possible to get into a situation where a package has been added but your local poetry.lock does not contain the proper hash. This is most common after resolving a merge conflict and the easiest way to resolve this issue is `poetry install`, which will check all package status' and update hash values in `poetry.lock`.

    1. Adding dependencies to the environment
        - Most dependencies (packages or tools) should be added to the environment through the Dockerfile. This allows us to maintain a consistent development enviornment. If you need a tool added, please make the appropriate changes to the Dockerfile and submit a Pull Request.

### Deploying GraphRAG
The GraphRAG service consist of two components - a `backend` application and a `frontend` UI application (coming soon). GraphRAG can be launched in multiple ways depending on where in the application stack you are developing and debugging.

- In Azure Kubernetes Service (AKS):

    Navigate to the root directory of the repository. First build and publish the `backend` docker image to an azure container registry.

    ```
    > az acr build --registry <my_container_registry> -f docker/Dockerfile-backend --image graphrag:backend .
    ```
    Update `infra/deployment.parameters.json` to use your custom graphrag docker images and re-run the deployment script to update AKS.

    After deployment is complete, `kubectl` is used to login and view the GraphRAG AKS resources as well aid in other debugging use-cases. See below for some helpful commands to quickly access AKS
    ```
    > RGNAME=<your_resource_group>
    > AKSNAME=`az aks list --resource-group $RGNAME --query "[].name" --output tsv`
    > az aks get-credentials -g $RGNAME -n $AKSNAME --overwrite-existing
    > kubectl config set-context --current --namespace=graphrag
    ```
    Some example AKS commands below to get started
    ```
    > kubectl get pods                       # view a list of all deployed pods
    > kubectl get nodes                      # view a list of all deployed nodes
    > kubectl get jobs                       # view a list of all AKS jobs
    > kubectl logs <pod_name>                # print out useful logging information (print statements)
    > kubectl exec -it <pod_name> -- bash    # login to a running container
    > kubectl describe pod <pod_name>        # retrieve detailed info about a pod
    > kubectl describe node <node_name>      # retrieve detailed info about a node
    ```

### Testing

A small collection of pytests have been written to test functionality of the API. Ensure that all test dependencies have been install

```python
poetry install --with test
```

Some tests require the azurite emulator and cosmosdb emulator to be running locally (these are setup in the ci/cd automatically). Please start these services by running them in the background as docker containers

```shell
docker run -d -p 10000:10000 -p 10001:10001 -p 10002:10002 mcr.microsoft.com/azure-storage/azurite
docker run -d -p 8081:8081 -p 1234:1234 mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-preview
```

To run the tests,

```shell
cd <graphrag-accelerator-repo>/backend
pytest --cov=src -s tests/
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