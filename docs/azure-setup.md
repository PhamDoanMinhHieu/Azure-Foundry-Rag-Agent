# Azure Setup Guide

Step-by-step instructions for provisioning the Azure resources this app needs, using the Azure Portal and the Azure AI Foundry portal (`ai.azure.com`). Each section also lists the pitfalls we hit while building this project, so you can avoid them.

> Region availability for Azure AI Foundry Agent Service changes frequently. Before you start, check the [Agent Service region support](https://learn.microsoft.com/azure/ai-services/agents/concepts/model-region-support) page and pick a region that supports the **Standard agent setup** (bring-your-own Azure AI Search + Storage).

## 1. Create a resource group

Azure Portal → **Create a resource** → **Resource group**. Use one resource group for every resource below so cleanup is a single delete.

## 2. Azure AI Foundry project and models

1. Go to `https://ai.azure.com` (a separate portal from `portal.azure.com`).
2. **Create new → Azure AI Foundry resource.** Pick your resource group and a region that supports Agent Service. This also creates a default **project**.
3. Open **Model catalog** and deploy a chat model, e.g. `gpt-4o` or `gpt-4o-mini` (deployment type **Global Standard** or **Standard**).
4. Deploy an embedding model, e.g. `text-embedding-3-small` (**Global Standard**).
5. Open **Playground → Chat**, select your chat deployment, and send a test message to confirm the deployment works.

**Pitfall:** if the **Agents** item doesn't appear in the left navigation after creating the project, the region you picked doesn't support Agent Service — you'll need to create the Foundry resource again in a different region (it can't be changed after creation).

## 3. Storage account for source documents

1. Azure Portal → **Create a resource → Storage account**. Performance **Standard**, redundancy **LRS**.
2. In the new account, create a **Container** named `documents` with **Private** access.
3. Upload a few sample documents (PDF or `.txt`) to the container.

## 4. Azure AI Search index

1. Azure Portal → **Create a resource → Azure AI Search**. Start with the **Free** tier (50 MB limit, enough for a demo). Same region as the Foundry resource is recommended but not required.
2. On the Search service's **Overview**, use **Import data** (shown as "Import and vectorize data" on some portal versions):
   - **Data source**: your storage account and `documents` container.
   - **Vectorize your text**: choose your Foundry resource and the `text-embedding-3-small` deployment.
   - Skip the image-vectorization step.
   - Give the generated objects a recognizable name prefix.
3. Once created, check **Indexers** for a **Success** status, and use **Search explorer** (`*` query) to confirm documents and vector fields are populated. Note the field names — you'll need them in step 6.

**Pitfall:** if your storage account was created with **Hierarchical namespace** enabled, it's technically **Azure Data Lake Storage Gen2**, not plain Blob Storage. The import wizard won't list it under "Azure Blob Storage" — pick **Azure Data Lake Storage Gen2** as the data source type instead.

**Pitfall:** the Free tier occasionally reports "out of resources" when creating the service in a popular region. Retry in a different region, wait a few minutes, or switch to the **Basic** tier.

## 5. Connect Azure AI Search to the Foundry project

1. `ai.azure.com` → your project → **Management center → Connected resources → + New connection → Azure AI Search**.
2. Point it at the Search service from step 4, authenticating with an API key (simplest) or Microsoft Entra ID.

## 6. Create the Agent

1. `ai.azure.com` → your project → **Agents → + New agent**.
2. Select your chat model deployment and write system instructions that tell the agent to answer only from retrieved documents and cite sources.
3. Under **Tools**, add **Azure AI Search**, select the connection from step 5 and the index from step 4, and map the content/vector fields.
4. Test in the **Agent Playground** with a question about your uploaded documents, and a question unrelated to them, before writing any application code.

## 7. Grant the application access (RBAC)

The identity the app runs as (your own account for local development, or the app's managed identity in Azure) needs:

| Resource | Role | Scope |
|---|---|---|
| Storage account | `Storage Blob Data Contributor` | the storage account |
| Azure AI Foundry | `Foundry User` | **the project**, e.g. `.../accounts/<resource>/projects/<project>` |

**Pitfall:** `Azure AI Developer` — a commonly recommended role — does **not** grant access to the newer unified `AIServices` Foundry resource type used by Agent Service. Creating a conversation fails with `403 ... agents/write`. Use `Foundry User` instead.

**Pitfall:** role assignments made only at the parent Cognitive Services account scope are not always sufficient for Agent Service's authorization checks. If you still get a `403` after waiting a few minutes, assign the role directly at the **project** resource scope (`.../accounts/<resource>/projects/<project>`), not just the account.

## 8. Build and deploy the container

1. **Azure Container Registry**: create one (Basic SKU).
2. Build and push the image:
   ```bash
   az acr build --registry <registry-name> --image azure-native-rag:v1 .
   ```
   If this fails with a credential error, build and push locally instead:
   ```bash
   az acr login --name <registry-name>
   docker build -t <registry-name>.azurecr.io/azure-native-rag:v1 .
   docker push <registry-name>.azurecr.io/azure-native-rag:v1
   ```
   **Pitfall:** `push access denied ... insufficient_scope` means your account lacks the `AcrPush` role on the registry — add it under **Access control (IAM)**.
3. **Container Apps**: create a Container App from that image with ingress enabled on port `8000`.
   **Pitfall:** if the deployment fails with `UNAUTHORIZED: authentication required` while pulling the image, the managed-identity-based registry authentication can race with role-assignment propagation on first deploy. Switch **Registry authentication → Authentication type** to **Secrets** (uses the registry's admin credentials, enabled automatically) to get a reliable first deployment, then optionally switch back to managed identity afterwards.
4. Enable a **system-assigned managed identity** on the Container App, then assign it the roles from step 7.
5. Set the environment variables listed in the main [README](../README.md#local-development) on the Container App.

## 9. Application Insights (optional but recommended)

Azure AI Foundry and Azure Container Apps Environments often auto-provision a linked Log Analytics workspace and Application Insights resource when they're first created — check your resource group before creating new ones.

1. If you don't already have one, create a **Log Analytics workspace**, then a **workspace-based Application Insights** resource pointing at it.
2. Copy its **Connection String** and set it as the `APPLICATIONINSIGHTS_CONNECTION_STRING` environment variable on the Container App.
3. In `ai.azure.com` → your project → **Management center → Tracing**, attach the same Application Insights resource so Agent Service traces land in the same place as the app's traces.
4. Verify with **Transaction search** / **Application Map** in Application Insights after sending a few chat requests.

## 10. Clean up

Delete the resource group when you're done to remove every resource in one step. Azure AI Search (Basic tier) and Azure Container Registry bill a small fixed amount per day even when idle; everything else here is either free-tier or pay-per-use.
