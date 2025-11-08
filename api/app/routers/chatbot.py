from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
from openai import OpenAI
from app.db import get_db
from app.config import settings

router = APIRouter()

# Initialize OpenAI client lazily (only when needed and key is available)
openai_client = None

def get_openai_client():
    """Get or create OpenAI client. Returns None if API key is not configured."""
    global openai_client
    if openai_client is not None:
        return openai_client
    
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        return None
    
    try:
        # Initialize OpenAI client - let it use default http client
        openai_client = OpenAI(api_key=openai_api_key)
        print("DEBUG: OpenAI client initialized successfully")
        return openai_client
    except Exception as e:
        print(f"DEBUG: Failed to initialize OpenAI client: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        return None


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    collected_data: Optional[Dict[str, Any]] = None  # Data collected so far


class ChatResponse(BaseModel):
    message: str
    collected_data: Optional[Dict[str, Any]] = None
    ready_for_plan: bool = False  # True when all required data is collected


# System prompt with platform knowledge
SYSTEM_PROMPT = """You are a helpful AI assistant for Kit Targeting, a platform that helps advertisers find and work with content creators for their campaigns.

Your role is to guide advertisers through a conversation to collect the following information needed to create a campaign plan:

REQUIRED INFORMATION:
1. Budget (required) - The total budget for the campaign in dollars
2. Category OR Advertiser info (required) - Either the advertiser category (e.g., "News", "Finance", "Tech") OR advertiser details
3. CPC (required) - Cost per click in dollars (e.g., 0.45, 1.25)

OPTIONAL INFORMATION:
4. Target CPA (optional) - Target cost per acquisition/acquisition in dollars
5. Advertiser Average CVR (optional) - Average conversion rate as a decimal (e.g., 0.025 for 2.5%)
6. Horizon Days (optional) - Campaign duration in days (default: 30)
7. Demographics (all optional):
   - Target Age Range (e.g., "25-34", "18-24")
   - Target Gender Skew (e.g., "mostly men", "mostly women", "even split")
   - Target Location (e.g., "US", "UK", "AU", "NZ")
   - Target Interests (comma-separated, e.g., "cooking, fitness, travel")

HOW TO COLLECT DATA:
- Ask questions naturally in a conversational way
- Don't ask for all information at once - have a natural conversation
- If the user provides information, acknowledge it and move to the next question
- Be friendly and helpful
- If the user asks about the platform or how it works, explain briefly
- Collect data in this order:
  1. Budget (required)
  2. Category or advertiser info (required)
  3. CPC (required)
  4. Target CPA (optional)
  5. Average CVR (optional)
  6. Campaign duration/horizon days (optional)
  7. Demographics: age range, gender skew, location, interests (all optional but should be discussed)

DATA COLLECTION PROCESS:
- Use the extract_campaign_data function whenever the user provides campaign information
- Extract and save data incrementally as the conversation progresses
- After collecting demographics (age, gender, location, interests), ask if they want to add anything else

WHEN ALL DATA IS COLLECTED (including demographics):
- Summarize everything you've collected
- Ask the user: "Your campaign plan is ready! Would you like me to generate your campaign plan now?"
- DO NOT set ready_for_plan to true until the user explicitly confirms (says "yes", "proceed", "generate", "let's do it", etc.)
- Only after the user explicitly confirms should you indicate the plan is ready

IMPORTANT: 
- Always use the extract_campaign_data function to save data as it's provided
- Wait for explicit user confirmation before indicating the plan is ready
- Don't rush - make sure all optional demographics are discussed before asking for confirmation

PLATFORM CONTEXT:
- Kit Targeting matches advertisers with content creators based on performance data, demographics, and similarity
- The platform uses smart matching to find the best creators for each campaign
- Plans include expected clicks, conversions, spend, and CPA for each creator
- Advertisers can see detailed forecasts and performance metrics

Keep responses concise and conversational. Don't overwhelm the user with too much information at once."""


def build_messages_for_openai(messages: List[ChatMessage], collected_data: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """Build messages array for OpenAI API."""
    system_message = {
        "role": "system",
        "content": SYSTEM_PROMPT
    }
    
    # Add context about collected data if available
    if collected_data:
        data_summary = f"\n\nCOLLECTED DATA SO FAR:\n{collected_data}\n\nUse this information to avoid asking for data you already have."
        system_message["content"] += data_summary
    
    openai_messages = [system_message]
    
    # Convert chat messages to OpenAI format
    for msg in messages:
        openai_messages.append({
            "role": msg.role,
            "content": msg.content
        })
    
    return openai_messages


def check_if_ready_for_plan(collected_data: Optional[Dict[str, Any]], last_user_message: Optional[str] = None) -> bool:
    """Check if all required data is collected AND user has explicitly confirmed."""
    if not collected_data:
        return False
    
    # Check required fields
    required_fields = ['budget', 'cpc']
    has_category_or_advertiser = 'category' in collected_data or 'advertiser_id' in collected_data
    
    if not (all(field in collected_data for field in required_fields) and has_category_or_advertiser):
        return False
    
    # Check if user has explicitly confirmed
    if last_user_message:
        confirmation_keywords = ['yes', 'proceed', 'generate', 'let\'s do it', 'go ahead', 'sure', 'ok', 'okay', 'confirm', 'ready', 'create', 'build']
        last_message_lower = last_user_message.lower()
        if any(keyword in last_message_lower for keyword in confirmation_keywords):
            return True
    
    return False


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """Handle chatbot conversation with OpenAI."""
    client = get_openai_client()
    if not client:
        raise HTTPException(
            status_code=500,
            detail="OpenAI API key not configured. Please set OPENAI_API_KEY environment variable."
        )
    
    try:
        # Build messages for OpenAI
        openai_messages = build_messages_for_openai(request.messages, request.collected_data)
        
        # Define function for extracting campaign data
        extract_data_function = {
            "type": "function",
            "function": {
                "name": "extract_campaign_data",
                "description": "Extract structured campaign data from the conversation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "budget": {"type": "number", "description": "Campaign budget in dollars"},
                        "category": {"type": "string", "description": "Advertiser category (e.g., Tech, News, Finance)"},
                        "advertiser_id": {"type": "integer", "description": "Advertiser ID if known"},
                        "cpc": {"type": "number", "description": "Cost per click in dollars"},
                        "target_cpa": {"type": "number", "description": "Target cost per acquisition"},
                        "advertiser_avg_cvr": {"type": "number", "description": "Average conversion rate as decimal (e.g., 0.20 for 20%)"},
                        "horizon_days": {"type": "integer", "description": "Campaign duration in days"},
                        "target_age_range": {"type": "string", "description": "Target age range (e.g., 25-54)"},
                        "target_gender_skew": {"type": "string", "description": "Target gender skew (e.g., mostly female, mostly male, even split)"},
                        "target_location": {"type": "string", "description": "Target location (e.g., US, UK)"},
                        "target_interests": {"type": "string", "description": "Target interests (comma-separated)"}
                    }
                }
            }
        }
        
        # Call OpenAI API with function calling
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=openai_messages,
            temperature=0.7,
            max_tokens=500,
            tools=[{"type": "function", "function": extract_data_function["function"]}],
            tool_choice="auto"
        )
        
        # Get assistant message (may be None if only tool calls)
        assistant_message = response.choices[0].message.content or ""
        
        # Extract structured data from function call if present
        updated_collected_data = request.collected_data.copy() if request.collected_data else {}
        
        tool_calls_present = response.choices[0].message.tool_calls is not None and len(response.choices[0].message.tool_calls) > 0
        tool_messages = []  # Initialize tool messages list
        
        if tool_calls_present:
            # Build tool response messages for each tool call
            for tool_call in response.choices[0].message.tool_calls:
                if tool_call.function.name == "extract_campaign_data":
                    import json
                    try:
                        extracted_data = json.loads(tool_call.function.arguments)
                        # Merge extracted data with existing collected data
                        for key, value in extracted_data.items():
                            if value is not None:  # Only update if value is not None
                                updated_collected_data[key] = value
                        print(f"DEBUG: Extracted campaign data: {extracted_data}")
                        
                        # Add tool response message
                        tool_messages.append({
                            "role": "tool",
                            "content": json.dumps({"status": "success", "extracted": extracted_data}),
                            "tool_call_id": tool_call.id
                        })
                    except json.JSONDecodeError as e:
                        print(f"DEBUG: Error parsing extracted data: {e}")
                        tool_messages.append({
                            "role": "tool",
                            "content": json.dumps({"status": "error", "message": str(e)}),
                            "tool_call_id": tool_call.id
                        })
        
        # If assistant message is empty but we have tool calls, generate a follow-up message
        if not assistant_message and tool_calls_present:
            # Make a follow-up call to get the assistant's response
            # Include the assistant message with tool calls and tool responses
            follow_up_messages = openai_messages + [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in response.choices[0].message.tool_calls
                    ]
                }
            ] + tool_messages
            
            follow_up_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=follow_up_messages,
                temperature=0.7,
                max_tokens=500
            )
            assistant_message = follow_up_response.choices[0].message.content or assistant_message
        
        # Get the last user message to check for confirmation
        last_user_message = None
        if request.messages:
            # Find the last user message
            for msg in reversed(request.messages):
                if msg.role == 'user':
                    last_user_message = msg.content
                    break
        
        # Check if ready for plan generation (requires data + explicit confirmation)
        ready_for_plan = check_if_ready_for_plan(updated_collected_data, last_user_message)
        
        print(f"DEBUG: Ready for plan: {ready_for_plan}, Collected data keys: {list(updated_collected_data.keys())}")
        print(f"DEBUG: Last user message: {last_user_message}")
        
        return ChatResponse(
            message=assistant_message,
            collected_data=updated_collected_data,
            ready_for_plan=ready_for_plan
        )
        
    except Exception as e:
        print(f"DEBUG: OpenAI API error: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Error communicating with AI: {str(e)}"
        )

