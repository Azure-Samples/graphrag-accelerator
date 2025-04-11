# Deployment Guide Quickstart

This guide will walk through the steps required to deploy GraphRAG in Azure.

### Prerequisites
The deployment process requires the following tools to be installed:

* [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) >= v2.55.0
* awk - a standard linux utility
* cut - a standard linux utility
* sed - a standard linux utility
* [curl](https://curl.se) - command line data transfer
* [docker desktop](https://docs.docker.com/get-started/get-docker)
* [helm](https://helm.sh/docs/intro/install) - k8s package manager
* [jq](https://jqlang.github.io/jq/download) >= v1.6
* [kubectl](https://kubernetes.io/docs/tasks/tools) - k8s command line tool
* [kubelogin](https://github.com/Azure/kubelogin) -  client-go credential (exec) plugin implementing azure authentication
* [yq](https://github.com/mikefarah/yq?tab=readme-ov-file#install) >= v4.40.7 - yaml file parser

TIP: If you open this repository as a devcontainer (i.e. VSCode Dev Containers or Codespaces), all required tools for deployment will already be available. Opening a devcontainer using VS Code requires <a href="https://docs.docker.com/engine/install/" target="_blank" >Docker to be installed</a>.

The setup/deployment process has been mostly automated with a shell script and Bicep files (infrastructure as code). Azure CLI will deploy all necessary Azure resources using these Bicep files. The deployment is configurable using values defined in `infra/deploy.parameters.json`. To the utmost extent, we have provided default values but users are still expected to modify some values.


#### RBAC Permissions
You will need the following <a href="https://learn.microsoft.com/en-us/azure/role-based-access-control/overview">Azure Role Based Access </a>permissions to deploy the GraphRAG solution accelerator.  By default, Azure resources will be deployed with <a href="https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/overview">Azure Managed Identities </a>, following security best practices.  Due to this enhanced security configuration, higher level permissions are required in order to deploy the necessary Azure resources:
| Permission | Scope |
| :--- | ---: |
Contributor                                    | Subscription
Role Based Access Control (RBAC) Administrator | Subscription
Owner                                          | Resource Group

#### Resource Providers
The Azure subscription that you deploy this solution accelerator in requires several resource providers to be registered (if they aren't already). They include:

* `Microsoft.OperationsManagement`
* ` Microsoft.Compute`
* `Microsoft.AlertsManagement`

This can be accomplished via the [Azure Portal](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-providers-and-types#azure-ortal) or with the following [Azure CLI](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-providers-and-types#azure-cli) commands:

```shell
# register providers
az provider register --namespace Microsoft.OperationsManagement
az provider register --namespace Microsoft.AlertsManagement
az provider register --namespace Microsoft.Compute
# verify providers were registered
az provider show --namespace Microsoft.OperationsManagement -o table
az provider show --namespace Microsoft.AlertsManagement -o table
az provider show --namespace Microsoft.Compute -o table
```

## Installation

### 1. Azure OpenAI
As a prerequisite to deployment, you will either need access to an already deployed Azure OpenAI (AOAI) resource or have available quota. If an existing AOAI resource is not used, the deployment code in this accelerator will deploy an AOAI resource with some default model choices.
Documentation on how to deploy an AOAI service can be found [here](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource?pivots=web-portal).

Take note of the model deployment name and model name.
Note that the AOAI instance **must** be in the same subscription that you plan to deploy this solution accelerator in.

As a starting point, we recommend the following quota thresholds be used for this solution accelerator to run.
| Model Name | TPM Threshold |
| :--- | ---: |
gpt-4 turbo            | 80K
text-embedding-ada-002 | 300K

### 2. Login to Azure
Login with Azure CLI and set the appropriate Azure subscription.

```shell
# login to Azure - may need to use the "--use-device-code" flag if using a remote host/virtual machine
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

| Variable | Expected/Default Value | Required | Description
| :--- | :--- | --- | ---: |
`LOCATION`                             | <my_location>                                  | Yes | The azure cloud region to deploy GraphRAG resources to (can be different than the location of your AOAI instance). Please use the [compressed form](https://azuretracks.com/2021/04/current-azure-region-names-reference) of a cloud region name (i.e. `eastus2`).
`RESOURCE_GROUP`                       | <my_resource_group>                            | Yes | The resource group that GraphRAG will be deployed in. Will get created automatically if the resource group does not exist.
`GRAPHRAG_API_BASE`                    | https://<my_openai_name>.openai.azure.com      | No  | An existing Azure OpenAI service endpoint.
`GRAPHRAG_API_VERSION`                 | 2023-03-15-preview                             | No  | OpenAI API version.
`GRAPHRAG_LLM_MODEL`                   | gpt-4                                          | No  | Name of the Azure OpenAI LLM model to use (or deploy).
`GRAPHRAG_LLM_MODEL_VERSION`           | turbo-2024-04-09                               | No  | Model version of the LLM model to use (or deploy). Only required if deploying a new AOAI instance (i.e. `GRAPHRAG_API_BASE` is left undefined).
`GRAPHRAG_LLM_DEPLOYMENT_NAME`         | gpt-4                                          | No  | Deployment name of the LLM model to use (or deploy).
`GRAPHRAG_LLM_MODEL_CONCURRENT_REQUEST` | 15                    | No  |  The max number of simultaneous chat completions LLM requests allowed.
`GRAPHRAG_LLM_MODEL_QUOTA`             | 80                                             | No  | TPM quota of the LLM model in units of 1000 (i.e. 10 = 10,000 TPM). Only required if deploying a new AOAI instance (i.e. 
`GRAPHRAG_API_BASE` is left undefined).
`GRAPHRAG_EMBEDDING_MODEL`             | text-embedding-ada-002                         | No  | Name of the Azure OpenAI embedding model.
`GRAPHRAG_EMBEDDING_MODEL_VERSION`     | 2                                              | No  | Model version of the embedding model to use (or deploy). Only required if deploying a new AOAI instance (i.e. `GRAPHRAG_API_BASE` is left undefined).
`GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME`   | text-embedding-ada-002                         | No  | Deployment name of the embedding model to use (or deploy).
`GRAPHRAG_EMBEDDING_MODEL_CONCURRENT_REQUEST` | 15                    | No  | The max number of simultaneous embedding requests allowed.
`GRAPHRAG_EMBEDDING_MODEL_QUOTA`       | 300                                            | No  | TPM quota of the embedding model in units of 1000 (i.e. 10 = 10,000 TPM). Only required if deploying a new AOAI instance (i.e. `GRAPHRAG_API_BASE` is left undefined).
`GRAPHRAG_IMAGE`                       | graphrag:backend                               | No  | The name and tag of the graphrag docker image in the container registry. Will default to `graphrag:backend` and be hosted at `my_container_registry_name>.azurecr.io/graphrag:backend`.
`CONTAINER_REGISTRY_LOGIN_SERVER`      | <container_registry_name>.azurecr.io           | No  | Endpoint of an existing Azure Container Registry where the `GRAPHRAG_IMAGE` docker image is hosted. If not provided, a unique name will be generated (recommended).
`COGNITIVE_SERVICES_AUDIENCE`          | `https://cognitiveservices.azure.com/.default` | No  | Endpoint for cognitive services identity authorization. Should be explicitly set for deployments in other Azure clouds.
`APIM_NAME`                            | <auto_generated_unique_name>                   | No  | Hostname of the graphrag API. Must be a globally unique name. The API will be available at `https://<APIM_NAME>.azure-api.net`.
`APIM_TIER`                            | Developer                                      | No  | The [APIM tier](https://azure.microsoft.com/en-us/pricing/details/api-management) to use. Can be either `Developer` or 
`StandardV2`. `StandardV2` costs more but will deploy faster.
`AI_SEARCH_TIER`                       | standard                                       | No  | The [AI Search tier](https://learn.microsoft.com/en-us/azure/search/search-sku-tier) to use. Can be either `free`, `basic`, `standard`, `standard2`, `standard3`, `storage_optimized_l1`, or `storage_optimized_l2`
`RESOURCE_BASE_NAME`                   |                                                | No  | Suffix to apply to all azure resource names. If not provided a unique suffix will be generated.
`AISEARCH_ENDPOINT_SUFFIX`             | `search.windows.net`                           | No  | Suffix to apply to AI search endpoint. Should be overridden for deployments in other Azure clouds.
`AISEARCH_AUDIENCE`                    | `https://search.azure.com/`                    | No  | AAD audience for AI Search. Should be overridden for deployments in other Azure clouds.


### 5. Deploy solution accelerator to the resource group
```shell
cd infra
bash deploy.sh -h # view help menu for additional options
bash deploy.sh -p deploy.parameters.json
```
When deploying for the first time, it may take ~40-50 minutes to deploy all resources. In cases where a deployment error may occur (e.g. not enough quota), subsequent runs of this command will be faster if you rerun the deployment using the same resource group.

TIP: The choice of `APIM_TIER` is a major contributing factor to the overall deployment time.

### 6. Use GraphRAG
Once the deployment has finished, check out our [`Quickstart`](../notebooks/) notebook for a demonstration of how to use the GraphRAG API. To access the API documentation, visit `<APIM_gateway_url>/manpage/docs` in your browser. You can find the `APIM_gateway_url` by looking in the settings of the deployed APIM instance.
