# Managed App Instructions

This guide is a temporary document that walks through the process to convert the graphrag solution accelerator to a managed app.

### 1. Auto format the bicep code

As a precaution, start by auto-formating and linting the bicep code to detect any mistakes early-on.

```bash
cd <repo_root_directory>/infra
find . -type f -name "*.bicep" -exec az bicep format --file {} \;
find . -type f -name "*.bicep" -exec az bicep lint --file {} \;
```

### 2. Convert bicep -> ARM
```bash
az bicep build --file main.bicep --outfile managed-app/mainTemplate.json
```

### 3. Create & test the Azure portal interface

Use the [Azure Portal Sandbox](https://portal.azure.com/#blade/Microsoft_Azure_CreateUIDef/SandboxBlade) to test and make any UI changes that are defined in [createUiDefinition.json](createUiDefinition.json). To make additional changes to the Azure portal experience, start by reading some [documentation](https://learn.microsoft.com/en-us/azure/azure-resource-manager/managed-applications/create-uidefinition-overview) and copying the contents of `createUiDefinition.json` into the sandbox environment.

### 4. Package up the managed app code

The name of the final two files (`mainTemplate.json` and `createUiDefinition.json`) cannot be changed. The file names are also case-sensitive and cannot be changed at this time. Managed apps require these files to be packaged up into a zip file (where the json files must be at the root directory).

```bash
cd <repo_root_directory>/infra/managed-app
zip -rj managed-app.zip .
```

This zip file can then be uploaded to an Azure Storage location when setting up a [Service Catalog Managed Application Definition](https://ms.portal.azure.com/#view/Microsoft_Azure_Marketplace/GalleryItemDetailsBladeNopdl/id/Microsoft.ApplianceDefinition/selectionMode~/false/resourceGroupId//resourceGroupLocation//dontDiscardJourney~/false/selectedMenuId/home/launchingContext~/%7B%22galleryItemId%22%3A%22Microsoft.ApplianceDefinition%22%2C%22source%22%3A%5B%22GalleryFeaturedMenuItemPart%22%2C%22VirtualizedTileDetails%22%5D%2C%22menuItemId%22%3A%22home%22%2C%22subMenuItemId%22%3A%22Search%20results%22%2C%22telemetryId%22%3A%2220409084-39a1-4800-bbce-d0b26a6f46a4%22%7D/searchTelemetryId/d7d20e05-ca16-47f7-bed5-9c7b8d2fa641).

### 5. Create the Service Catalog Managed App Definition

In the Azure Portal, go to Marketplace and create a `Service Catalog Managed App Definition`. You must provide a uri link to the uploaded `managed-app.zip` file as part of the creation process.

### 6. Deploy the managed app

In the Azure Portal, find and click on the managed app definition resource that was created in the previous step. A button option to `Deploy from definition` will be available. Click on it and proceed through the setup steps (defined by the `createUiDefinitions.json` file) that a consumer would experience when installing the managed app.


[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FAzure-Samples%2Fgraphrag-accelerator%2Frefs%2Fheads%2Fharjit-managed-app%2Finfra%2FmainTemplate.json)

