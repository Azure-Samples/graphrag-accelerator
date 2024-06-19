# Deployment Guide Quickstart

This guide will walk through the steps required to deploy GraphRAG in Azure.

### Installation Requirements
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

TIP: If you open this repository inside a devcontainer (i.e. VSCode Dev Containers or Codespaces), all required tools for deployment will already be available.

The setup/deployment process has been mostly automated with a shell script and Bicep files (infrastructure as code). Azure CLI will deploy all necessary Azure resources using these Bicep files. The deployment is configurable using values defined in `infra/deploy.parameters.json`. To the utmost extent, we have provided default values but users are still expected to modify some values.

## 1. Deploy Azure OpenAI Service
You will need access to a deployed Azure OpenAI resource. Documentation on how to deploy an Azure OpenAI service resource can be found [here](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource?pivots=web-portal). Ensure deployments for the `gpt-4-turbo` model and `text-embedding-ada-002` embedding model are setup. Take note of the model deployment name and model name.

As a starting point, we recommend the following quota thresholds be setup for this solution accelerator to run.
| Model Name | TPM Threshold |
| :--- | ---: |
gpt-4 turbo            | 80K
text-embedding-ada-002 | 300K

## 2. Login to Azure
Login with Azure CLI and set the appropriate Azure subscription.
```shell
# login to Azure (if needed)
> az login  # or az login --use-device-code if using a remote host/virtual machine
# check what subscription you are logged into
> az account show
# set appropriate subscription if necessary
> az account set --subscription "<subscription_id>"
```

The Azure subscription that you deploy the accelerator in will require the `Microsoft.OperationsManagement` resource provider to be registered.
This can be accomplished via the [Portal](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-providers-and-types#azure-ortal) or these [Azure CLI](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-providers-and-types#azure-cli) commands:

```shell
# Register provider
az provider register --namespace Microsoft.OperationsManagement
# Verify provider was registered
az provider show --namespace Microsoft.OperationsManagement -o table
```

## 3. Deploy Azure Container Registry (ACR) and host the `graphrag` docker image in the registry
ACR may be deployed using the [Portal](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-get-started-portal?tabs=azure-cli) or [Azure CLI](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-get-started-azure-cli).

```shell
# create a new resource group and deploy ACR
> az group create --name <my_resource_group> --location <my_location>
> az acr create --resource-group <my_resource_group> --name <my_container_registry> --sku Standard
# cd to the root directory of this repo and build/push the docker image to ACR
> az acr build --registry <my_container_registry> -f docker/Dockerfile-backend --image graphrag:backend .
```

## 4. Fill out `infra/deploy.parameters.json`

In the `deploy.parameters.json` file, provide values for the following required variables, if not already filled out.

| Variable | Expected Value | Required | Description
| :--- | :--- | --- | ---: |
`RESOURCE_GROUP`                     | <my_resource_group>                | Yes | The resource group that GraphRAG will be deployed in. Will get created automatically if the resource group does not exist.
`LOCATION`                           | <my_location>                      | Yes | The azure cloud region to deploy GraphRAG resources in.
`CONTAINER_REGISTRY_SERVER`          | <my_container_registry>.azurecr.io | Yes | Name of the Azure Container Registry where the `graphrag` docker image is hosted.
`GRAPHRAG_IMAGE`                     | graphrag:backend                   | Yes | The name and tag of the graphrag docker image in the container registry.
`GRAPHRAG_API_BASE`                  |                                    | Yes | Azure OpenAI service endpoint.
`GRAPHRAG_API_VERSION`               | 2023-03-15-preview                 | Yes | Azure OpenAI API version.
`GRAPHRAG_LLM_MODEL`                 | gpt-4                              | Yes | Name of the gpt-4 turbo model.
`GRAPHRAG_LLM_DEPLOYMENT_NAME`       |                                    | Yes | Deployment name of the gpt-4 turbo model.
`GRAPHRAG_EMBEDDING_MODEL`           | text-embedding-ada-002             | Yes | Name of the Azure OpenAI embedding model.
`GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME` |                                    | Yes | Deployment name of the Azure OpenAI embedding model.
`APIM_NAME`                          |                                    | No  | Hostname of the API. Must be a globally unique name. The API will be accessible at `https://<APIM_NAME>.azure-api.net`. If not provided a unique name will be generated.
`RESOURCE_BASE_NAME`                 |                                    | No  | Suffix to apply to all azure resource names. If not provided a unique suffix will be generated.
`AISEARCH_ENDPOINT_SUFFIX`           |                                    | No  | Suffix to apply to AI search endpoint. Will default to `search.windows.net` for Azure Commercial cloud but should be overriden for deployments in other Azure clouds.
`AISEARCH_AUDIENCE`           |                                    | No  | Audience for AAD for AI Search. Default is `https://search.azure.com/`, which will default to Azure Commerical cloud.
`REPORTERS`                          |                                    | No  | The type of logging to enable. If not provided, logging will be saved to a file in Azure Storage and to the console in AKS.
`GRAPHRAG_COGNITIVE_SERVICES_ENDPOINT` |                                  | No  | Endpoint for cognitive services identity authorization. Will default to `https://cognitiveservices.azure.com/.default` for Azure Commercial cloud but should be defined for deployments in other Azure clouds.

## 5. Deploy the solution accelerator
```
> cd infra
> bash deploy.sh deploy.parameters.json
```
When deploying for the first time, it will take ~40-50 minutes to deploy. Subsequent runs of this command will be faster.

## 6. Use GraphRAG
Once the deployment has finished, check out our [`Hello World`](../notebooks/HelloWorld.ipynb) notebook for a demonstration of how to use the GraphRAG API. To access the API documentation, visit `<APIM_gateway_url>/manpage/docs` in your browser. You can find the `APIM_gateway_url` by looking in the Azure Portal for the deployed APIM instance.
