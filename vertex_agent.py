import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import vertexai
from vertexai.generative_models import GenerativeModel, Tool, FunctionDeclaration, ToolConfig
import warnings
import json 

# Suppress SDK warnings for cleaner demo logs
warnings.filterwarnings("ignore")



SHEET_NAME = "Pharma_CRM_Database"
SERVICE_ACCOUNT_FILE = "service_account.json"
MODEL_NAME = "gemini-2.0-flash-lite-001" 

try:
    with open(SERVICE_ACCOUNT_FILE, "r") as f:
        key_data = json.load(f)
        PROJECT_ID = key_data.get("project_id")
        LOCATION = key_data.get("location")
        print(f"✅ Loaded Configuration for Project: {PROJECT_ID}")
except FileNotFoundError:
    print("❌ CRITICAL ERROR: service_account.json not found.")
    print("   Please ask the admin for the key or generate one in Google Cloud.")

# --- CONNECTION MANAGER ---
def get_crm_sheet():
    """Establishes secure connection to Google Sheets CRM."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME).sheet1
    except Exception as e:
        return None

# --- UTILITY: ID GENERATOR ---
def get_next_call_id():
    """Fetches the next sequential Call ID to ensure DB integrity."""
    sheet = get_crm_sheet()
    if not sheet: return "CALL_000000"
    try:
        col_values = sheet.col_values(1)
        if len(col_values) <= 1: return "CALL_000001"
        
        last_id = col_values[-1]
        if "CALL_" in last_id:
            num = int(last_id.split("_")[1]) + 1
            return f"CALL_{num:06d}"
        return "CALL_000001"
    except: return "CALL_000001"

# --- THE AGENT'S TOOL (ACTION) ---
def log_crm_entry(call_id, hcp_id, rep_id, call_date, raw_note, summary, sentiment, topics, next_action, risk_flag, coaching_tip):
    """
    The physical action the Agent performs: Writing to the Database.
    """
    sheet = get_crm_sheet()
    if sheet:
        try:
            # Map arguments to exact Sheet Columns
            row = [call_id, hcp_id, rep_id, call_date, raw_note, summary, sentiment, topics, next_action, risk_flag, coaching_tip]
            sheet.append_row(row)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "Database Connection Failed"}

# --- VERTEX AI DEFINITIONS ---

# 1. Define the Tool Capability (Schema)
crm_tool_func = FunctionDeclaration(
    name="log_crm_entry",
    description="Saves analyzed pharmaceutical call data to the CRM database.",
    parameters={
        "type": "object",
        "properties": {
            "call_id": {"type": "string"},
            "hcp_id": {"type": "string"},
            "rep_id": {"type": "string"},
            "call_date": {"type": "string"},
            "summary": {"type": "string", "description": "Concise business summary"},
            "sentiment": {"type": "string", "description": "High/Medium/Low"},
            "topics": {"type": "string", "description": "Medical topics discussed"},
            "next_action": {"type": "string", "description": "Specific follow-up"},
            "risk_flag": {"type": "string", "description": "TRUE if compliance risk detected"},
            "coaching_tip": {"type": "string", "description": "Feedback for the Rep"}
        },
        "required": ["call_id", "summary", "sentiment", "next_action", "risk_flag", "coaching_tip"]
    },
)

# 2. Initialize Agent with Tool
crm_tool = Tool(function_declarations=[crm_tool_func])

# 3. Force Tool Execution (Agentic Behavior)
tool_config = ToolConfig(
    function_calling_config=ToolConfig.FunctionCallingConfig(
        mode=ToolConfig.FunctionCallingConfig.Mode.ANY,
        allowed_function_names=["log_crm_entry"],
    )
)

vertexai.init(project=PROJECT_ID, location=LOCATION)

def run_agent_workflow(call_id, hcp_id, rep_id, call_date, raw_note):
    """
    Executes the Agentic Loop: Perception -> Reasoning -> Action.
    """
    model = GenerativeModel(MODEL_NAME, tools=[crm_tool])
    
    # The Prompt is the "System Instruction" for the Brain
    prompt = f"""
    ROLE: You are an expert Pharmaceutical Sales Operations Agent.
    
    CONTEXT:
    - ID: {call_id} | HCP: {hcp_id} | Rep: {rep_id} | Date: {call_date}
    - INPUT NOTE: "{raw_note}"
    
    GOAL:
    1. Analyze the note for Compliance Risks (Off-label claims, side effects).
    2. Extract Business Intelligence (Sentiment, Topics).
    3. Generate a Coaching Tip for the Rep.
    4. EXECUTE the 'log_crm_entry' tool to save the record.
    """

    try:
        # Generate with forced function calling
        response = model.generate_content(prompt, tool_config=tool_config)
        
        try:
            part = response.candidates[0].content.parts[0]
        except IndexError:
             return {"error": "Agent produced empty response."}

        # Execute the Tool Decision
        if part.function_call and part.function_call.name == "log_crm_entry":
            args = part.function_call.args
            
            # The Agent calls the Python function here
            result_status = log_crm_entry(
                args["call_id"], args["hcp_id"], args["rep_id"], args["call_date"],
                raw_note, # Inject raw note for audit trail
                args["summary"], args["sentiment"], args.get("topics", "General"), 
                args["next_action"], args["risk_flag"], args["coaching_tip"]
            )
            
            if result_status["status"] == "error":
                return {"error": f"DB Write Failed: {result_status.get('message')}"}

            # Return Structured Data for UI
            return {
                "summary": args["summary"],
                "hcp_sentiment": args["sentiment"],
                "next_best_action": args["next_action"],
                "compliance_flag": args["risk_flag"],
                "coaching_tip": args["coaching_tip"],
                "status": "success"
            }
        
        return {"error": "Agent analyzed but refused to execute save."}

    except Exception as e:
        return {"error": f"Workflow Exception: {str(e)}"}
