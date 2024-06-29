# Deployment Guide Quickstart

This guide will walk through the steps required to deploy GraphRAG in Azure.

### Prerequisites
The deployment process requires the following tools to be installed:

* [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) >= v2.55.0
* awk - a standard linux utility
* cut - a standard linux utility
* sed - a standard linux utility
* [curl](https://curl.se) - command line data transfer
* [helm](https://helm.sh/docs/intro/install) - k8s package manager
* [jq](https://jqlang.github.io/jq/download) >= v1.6
* [kubectl](https://kubernetes.io/docs/tasks/tools) - k8s command line tool
* [yq](https://github.com/mikefarah/yq?tab=readme-ov-file#install) >= v4.40.7 - yaml file parser

TIP: If you open this repository inside a devcontainer (i.e. VSCode Dev Containers or Codespaces), all required tools for deployment will already be available. Opening a devcontainer using VS Code requires <a href="https://docs.docker.com/engine/install/" target="_blank" >Docker to be installed</a>.

The setup/deployment process has been mostly automated with a shell script and Bicep files (infrastructure as code). Azure CLI will deploy all necessary Azure resources using these Bicep files. The deployment is configurable using values defined in `infra/deploy.parameters.json`. To the utmost extent, we have provided default values but users are still expected to modify some values.


#### RBAC Permissions
You will need the following <a href="https://learn.microsoft.com/en-us/azure/role-based-access-control/overview">Azure Role Based Access </a>permissions at the Subscription level to deploy the GraphRAG solution accelerator.  By default, Azure resources will be deployed with <a href="https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/overview">Azure Managed Identities </a>in place, keeping with security best practices.  Due to this enhanced security configuration, higher level permissions are required in order to deploy the necessary Azure resources:
| Permission | Scope |
| :--- | ---: |
Contributor            | Subscription
Role Based Access Control (RBAC) Administrator | Subscription

#### Resource Providers
The Azure subscription that you deploy this solution accelerator in will require both the `Microsoft.OperationsManagement` and `Microsoft.AlertsManagement` resource providers to be registered.
This can be accomplished via the [Azure Portal](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-providers-and-types#azure-ortal) or with the following [Azure CLI](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-providers-and-types#azure-cli) commands:

```shell
# register providers
az provider register --namespace Microsoft.OperationsManagement
az provider register --namespace Microsoft.AlertsManagement
# verify providers were registered
az provider show --namespace Microsoft.OperationsManagement -o table
az provider show --namespace Microsoft.AlertsManagement -o table
```

## Installation

### 1. Deploy Azure OpenAI Service
You will need access to a deployed Azure OpenAI resource. Documentation on how to deploy an Azure OpenAI service resource can be found [here](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource?pivots=web-portal). Ensure deployments for the `gpt-4-turbo` model and `text-embedding-ada-002` embedding model are setup. Take note of the model deployment name and model name.

As a starting point, we recommend the following quota thresholds be setup for this solution accelerator to run.
| Model Name | TPM Threshold |
| :--- | ---: |
gpt-4 turbo            | 80K
text-embedding-ada-002 | 300K

### 2. Login to Azure
Login with Azure CLI and set the appropriate Azure subscription.
```shell
# login to Azure - may need to use use the "--use-device-code" flag if using a remote host/virtual machine
az login
# check what subscription you are logged into
az account show
# set appropriate subscription
az account set --subscription "<subscription_name> or <subscription id>"
```

### 3. Create a Resource Group
A resource group can be created via the [Azure Portal](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/manage-resource-groups-portal) or Azure CLI.

```shell
az group create --name <my_resource_group> --location <my_location>
```

### 4. Fill out `infra/deploy.parameters.json`

In the `deploy.parameters.json` file, provide values for the following required variables, if not already filled out.

| Variable | Expected Value | Required | Description
| :--- | :--- | --- | ---: |
`RESOURCE_GROUP`                       | <my_resource_group>                | Yes | The resource group that GraphRAG will be deployed in. Will get created automatically if the resource group does not exist.
`LOCATION`                             | <my_location>                      | Yes | The azure cloud region to deploy GraphRAG resources in.
`CONTAINER_REGISTRY_SERVER`            | <my_container_registry>.azurecr.io | No  | Name of an existing Azure Container Registry where the `graphrag` backend docker image is hosted. Will get created automatically if not provided.
`GRAPHRAG_IMAGE`                       | graphrag:backend                   | No  | The name and tag of the graphrag docker image in the container registry. Will default to `graphrag:backend`.
`GRAPHRAG_API_BASE`                    |                                    | Yes | Azure OpenAI service endpoint.
`GRAPHRAG_API_VERSION`                 | 2023-03-15-preview                 | Yes | Azure OpenAI API version.
`GRAPHRAG_LLM_MODEL`                   | gpt-4                              | Yes | Name of the gpt-4 turbo model.
`GRAPHRAG_LLM_DEPLOYMENT_NAME`         |                                    | Yes | Deployment name of the gpt-4 turbo model.
`GRAPHRAG_EMBEDDING_MODEL`             | text-embedding-ada-002             | Yes | Name of the Azure OpenAI embedding model.
`GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME`   |                                    | Yes | Deployment name of the Azure OpenAI embedding model.
`GRAPHRAG_COGNITIVE_SERVICES_ENDPOINT` |                                    | No  | Endpoint for cognitive services identity authorization. Will default to `https://cognitiveservices.azure.com/.default` for Azure Commercial cloud but should be defined for deployments in other Azure clouds.
`APIM_NAME`                            |                                    | No  | Hostname of the API. Must be a globally unique name. The API will be accessible at `https://<APIM_NAME>.azure-api.net`. If not provided a unique name will be generated.
`RESOURCE_BASE_NAME`                   |                                    | No  | Suffix to apply to all azure resource names. If not provided a unique suffix will be generated.
`AISEARCH_ENDPOINT_SUFFIX`             |                                    | No  | Suffix to apply to AI search endpoint. Will default to `search.windows.net` for Azure Commercial cloud but should be overriden for deployments in other Azure clouds.
`AISEARCH_AUDIENCE`                    |                                    | No  | Audience for AAD for AI Search. Will default to `https://search.azure.com/` for Azure Commercial cloud but should be overriden for deployments in other Azure clouds.D
`REPORTERS`                            |                                    | No  | The type of logging to enable. If not provided, logging will be saved to a file in Azure Storage and to the console in AKS.

### 5. Deploy solution accelerator to the resource group
```shell
cd infra
bash deploy.sh -h # view help menu for additional options
bash deploy.sh -p deploy.parameters.json
```
When deploying for the first time, it will take ~40-50 minutes to deploy. Subsequent runs of this command will be faster.

### 6. Use GraphRAG
Once the deployment has finished, check out our [`Quickstart`](../notebooks/1-Quickstart.ipynb) notebook for a demonstration of how to use the GraphRAG API. To access the API documentation, visit `<APIM_gateway_url>/manpage/docs` in your browser. You can find the `APIM_gateway_url` by looking in the Azure Portal for the deployed APIM instance.
