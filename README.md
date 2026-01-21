# 💊 PharmaField AI Agent (Vertex AI + Cloud Run)

An autonomous AI agent that transforms unstructured field rep notes into structured, compliant CRM data using Google Vertex AI (Gemini 1.5 Flash).

## 🔗 Try the Live Demo
**[[Cloud Run URL Here](https://pharma-agent-mvp-80905374660.us-central1.run.app)]**

---

## 🛠️ How to Access the Live Database
To see the Agent syncing data in real-time, you need access to the backend Google Sheet.

### Step 1: Request Access
The application writes to a secured Google Sheet using a Cloud Identity. To verify the sync works:
1.  Ask the developer (Me) to share the **`Pharma_CRM_Database`** sheet with your email.
2.  Once shared, keep the Sheet open in one tab and the App in another.

### Step 2: (For Developers) Granting Cloud Identity Access
*If deploying a fresh instance or troubleshooting permissions:*

The Cloud Run application uses a specific **Service Account** to talk to Google Sheets. If the app cannot write to the sheet, you must find this email and give it "Editor" access in the Sheet.

**Run this command in your terminal to find the identity:**
```bash
gcloud run services describe pharma-agent-v1 --region us-central1 --format="value(spec.template.spec.serviceAccountName)"