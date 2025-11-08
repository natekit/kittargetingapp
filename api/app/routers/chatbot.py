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

WHEN ALL REQUIRED DATA IS COLLECTED:
- Set ready_for_plan to true
- Summarize what you've collected
- Tell the user their campaign plan is ready and ask if they'd like to proceed

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


def check_if_ready_for_plan(collected_data: Optional[Dict[str, Any]]) -> bool:
    """Check if all required data is collected."""
    if not collected_data:
        return False
    
    required_fields = ['budget', 'cpc']
    has_category_or_advertiser = 'category' in collected_data or 'advertiser_id' in collected_data
    
    return all(field in collected_data for field in required_fields) and has_category_or_advertiser


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
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using mini for cost efficiency, can upgrade to gpt-4 if needed
            messages=openai_messages,
            temperature=0.7,
            max_tokens=500
        )
        
        assistant_message = response.choices[0].message.content
        
        # Check if ready for plan generation
        ready_for_plan = check_if_ready_for_plan(request.collected_data)
        
        return ChatResponse(
            message=assistant_message,
            collected_data=request.collected_data,
            ready_for_plan=ready_for_plan
        )
        
    except Exception as e:
        print(f"DEBUG: OpenAI API error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error communicating with AI: {str(e)}"
        )

