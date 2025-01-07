# Managed App Instructions

This guide is a temporary document that walks through the progress made so far to convert the graphrag solution accelerator to a managed app.

1. Auto format the bicep code

```bash
find . -type f -name "*.bicep" -exec az bicep format --file {} \;
```

2. Convert bicep -> ARM
```bash
az bicep build --file main.bicep --outfile managed-app/mainTemplate.json
```

3. Test the Portal Interface
Use the [Azure Portal Sandbox](https://portal.azure.com/#blade/Microsoft_Azure_CreateUIDef/SandboxBlade) to test and make any UI changes in `managed-app/createUiDefinition.json`. To make additional changes to the Azure portal experience, start by reading some [documentation](https://learn.microsoft.com/en-us/azure/azure-resource-manager/managed-applications/create-uidefinition-overview) and copying the contents of `createUiDefinition.json` into the sandbox environment.
