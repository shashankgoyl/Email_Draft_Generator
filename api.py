"""
FastAPI Server for Multi-Address Email Generation
New Flow:
1. Accept one or more email addresses + optional Email Goal
2. Fetch emails and group into threads for each address
3. Auto-extract intent from conversation using LLM (no manual selection needed)
4. If Email Goal provided: Filter relevant threads using LLM
5. If NO Email Goal: Show all threads OR allow new email from scratch
6. Generate contextual or new emails for each address
7. Save to SQLite database with edit capabilities
"""

import os
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from dotenv import load_dotenv

from graph import (
    get_threads_for_multiple_addresses,
    filter_threads_by_goal,
    generate_email_from_thread,
    generate_new_email
)
from database import (
    save_generation,
    update_session,
    get_all_sessions,
    get_session_by_id,
    delete_session,
    clear_all_history,
    get_stats
)

load_dotenv()

# ============================================================================
# REQUEST/RESPONSE MODELS (Pydantic)
# ============================================================================

class FetchThreadsRequest(BaseModel):
    """Request model for fetching conversation threads for multiple addresses"""
    email_addresses: str = Field(..., description="Email address(es) - comma-separated for multiple")
    email_goal: Optional[str] = Field(None, description="Optional email goal to filter relevant threads")
    provider: Optional[str] = Field("gmail", description="Email provider: gmail or outlook")
    max_emails: Optional[int] = Field(100, description="Max emails to fetch per address (50-100)")


class GenerateEmailRequest(BaseModel):
    """Request model for generating email - intent is now auto-extracted"""
    email_address: str = Field(..., description="Email address to generate for")
    thread_id: Optional[str] = Field(None, description="ID of conversation thread (None for new email)")
    selected_email_index: Optional[int] = Field(None, description="Index of specific email to focus on (0-based)")
    email_goal: Optional[str] = Field("", description="User's goal for the email")
    provider: Optional[str] = Field("gmail", description="Email provider")
    tone: Optional[str] = Field("professional", description="Email tone")
    max_emails: Optional[int] = Field(100, description="Max emails to fetch")


class GenerateMultipleEmailsRequest(BaseModel):
    """Request model for generating emails for multiple addresses"""
    email_addresses: str = Field(..., description="Email addresses - comma-separated")
    email_goal: str = Field(..., description="Email goal/purpose")
    tone: Optional[str] = Field("professional", description="Email tone")
    provider: Optional[str] = Field("gmail", description="Email provider")
    max_emails: Optional[int] = Field(100, description="Max emails to fetch")


class UpdateSessionRequest(BaseModel):
    """Request model for updating a session"""
    subject: Optional[str] = Field(None, description="Updated subject")
    email_body: Optional[str] = Field(None, description="Updated email body")
    email_goal: Optional[str] = Field(None, description="Updated email goal")
    tone: Optional[str] = Field(None, description="Updated tone")


class AddressThreadsResponse(BaseModel):
    """Response model for threads of a single address"""
    email_address: str
    threads: list = []
    total_emails: int = 0
    relevant_threads: Optional[list] = None  # If filtered by goal
    has_context: bool = True


class MultiAddressThreadsResponse(BaseModel):
    """Response model for threads of multiple addresses"""
    success: bool
    addresses_data: List[AddressThreadsResponse] = []
    email_goal: Optional[str] = None
    total_addresses: int = 0
    message: Optional[str] = None

        
class EmailResponse(BaseModel):
    """Response model for email generation"""
    success: bool
    email_address: str = ""
    subject: str = ""
    email: str = ""
    thread_subject: Optional[str] = None
    thread_email_count: int = 0
    is_new_email: bool = False
    intent: Optional[str] = None  # Auto-extracted intent
    session_id: Optional[str] = None
    message: Optional[str] = None


class MultiEmailResponse(BaseModel):
    """Response model for multiple email generation"""
    success: bool
    emails: List[EmailResponse] = []
    total_generated: int = 0
    message: Optional[str] = None


class HistoryResponse(BaseModel):
    """Response model for history retrieval"""
    success: bool
    sessions: List[dict] = []
    total: int = 0
    message: Optional[str] = None


class StatsResponse(BaseModel):
    """Response model for statistics"""
    success: bool
    stats: dict = {}
    message: Optional[str] = None


class UpdateResponse(BaseModel):
    """Response model for update operations"""
    success: bool
    message: str


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Multi-Address Email Generator with Auto-Intent",
    description="Generate contextual emails with automatic intent extraction and SQLite database",
    version="5.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Multi-Address Email Generator with Auto-Intent",
        "version": "5.0.0",
        "status": "running",
        "features": [
            "Support for multiple email addresses",
            "Automatic intent extraction from conversations (LLM-powered)",
            "Optional Email Goal for context filtering",
            "Fetch and group emails into threads",
            "Goal-based thread filtering using LLM",
            "Generate contextual or new emails",
            "SQLite database for history tracking",
            "Edit and update generated emails"
        ],
        "improvements": [
            "✨ No manual intent selection - automatically extracted by LLM",
            "💾 SQLite database instead of JSON for better performance",
            "✏️ Enhanced edit capabilities with database persistence"
        ],
        "endpoints": {
            "health": "/health",
            "fetch_threads": "/fetch-threads",
            "generate_email": "/generate-email",
            "generate_multiple": "/generate-multiple",
            "update_session": "/history/{session_id}",
            "history": "/history",
            "history_by_id": "/history/{session_id}",
            "delete_history": "/history/{session_id}",
            "clear_history": "/history/clear",
            "stats": "/stats"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        llm_model = os.getenv("LLM_MODEL", "gpt-oss-20b")

        return {
            "status": "healthy",
            "llm": {
                "model": llm_model,
                "status": "connected",
                "features": ["auto_intent_extraction", "thread_filtering"]
            },
            "providers": {
                "gmail": "available",
                "outlook": "coming soon"
            },
            "database": {
                "type": "SQLite",
                "status": "connected",
                "stats": get_stats()
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.post("/fetch-threads", response_model=MultiAddressThreadsResponse)
async def fetch_threads_endpoint(request: FetchThreadsRequest):
    """
    Fetch emails and group into threads for one or more email addresses

    If email_goal is provided:
        - Fetch all threads
        - Use LLM to filter threads relevant to the goal
        - Return both all threads and filtered relevant threads

    If NO email_goal:
        - Fetch all threads
        - Return all threads for user to select or create new

    Args:
        request: FetchThreadsRequest with email_addresses, optional email_goal

    Returns:
        MultiAddressThreadsResponse with threads for each address
    """
    try:
        # Parse email addresses (comma-separated)
        email_addresses = [addr.strip() for addr in request.email_addresses.split(',') if addr.strip()]

        if not email_addresses:
            raise HTTPException(
                status_code=400,
                detail="At least one email address is required"
            )

        # Validate provider
        if request.provider.lower() not in ["gmail", "outlook"]:
            raise HTTPException(
                status_code=400,
                detail="Provider must be 'gmail' or 'outlook'"
            )

        # Fetch threads for all addresses
        result = get_threads_for_multiple_addresses(
            email_addresses=email_addresses,
            provider=request.provider,
            max_emails=request.max_emails
        )

        if not result.get("success"):
            return MultiAddressThreadsResponse(
                success=False,
                message=result.get("error", "Failed to fetch threads")
            )

        addresses_data = []

        for address_result in result.get("addresses_data", []):
            email_address = address_result["email_address"]
            threads = address_result["threads"]
            total_emails = address_result["total_emails"]

            # Check if there are any threads
            has_context = len(threads) > 0

            address_data = AddressThreadsResponse(
                email_address=email_address,
                threads=threads,
                total_emails=total_emails,
                has_context=has_context
            )

            # If email_goal provided, filter relevant threads
            if request.email_goal and has_context:
                filtered_result = filter_threads_by_goal(
                    threads=threads,
                    email_goal=request.email_goal
                )

                if filtered_result.get("success"):
                    address_data.relevant_threads = filtered_result.get("relevant_threads", [])

            addresses_data.append(address_data)

        return MultiAddressThreadsResponse(
            success=True,
            addresses_data=addresses_data,
            email_goal=request.email_goal,
            total_addresses=len(addresses_data),
            message="Threads fetched successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        return MultiAddressThreadsResponse(
            success=False,
            message=f"Server error: {str(e)}"
        )


@app.post("/generate-email", response_model=EmailResponse)
async def generate_email_endpoint(request: GenerateEmailRequest):
    """
    Generate email for a single address with automatic intent extraction

    Can generate either:
    - Contextual email from a thread (if thread_id provided) - intent auto-extracted
    - New email from scratch (if thread_id is None)

    Args:
        request: GenerateEmailRequest (no manual intent needed)

    Returns:
        EmailResponse with generated email and auto-extracted intent
    """
    try:
        # Validate provider
        if request.provider.lower() not in ["gmail", "outlook"]:
            raise HTTPException(
                status_code=400,
                detail="Provider must be 'gmail' or 'outlook'"
            )

        # Determine if this is a new email or contextual
        is_new_email = request.thread_id is None

        if is_new_email:
            # Generate new email from scratch
            result = generate_new_email(
                email_address=request.email_address,
                email_goal=request.email_goal,
                tone=request.tone
            )
        else:
            # Generate contextual email from thread - intent will be auto-extracted
            result = generate_email_from_thread(
                email_address=request.email_address,
                thread_id=request.thread_id,
                intent=None,  # Let the LLM extract intent automatically
                selected_email_index=request.selected_email_index,
                email_goal=request.email_goal,
                provider=request.provider,
                tone=request.tone,
                max_emails=request.max_emails
            )

        if result.get("success"):
            # Get the auto-extracted intent
            extracted_intent = result.get("intent", "new" if is_new_email else "reply")

            # Save to database
            session_id = save_generation({
                "email_address": request.email_address,
                "thread_subject": result.get("thread_subject", "New Email"),
                "intent": extracted_intent,
                "subject": result.get("subject", ""),
                "email": result.get("email", ""),
                "tone": request.tone,
                "selected_email_index": request.selected_email_index,
                "email_goal": request.email_goal,
                "thread_email_count": result.get("thread_email_count", 0),
                "is_new_email": is_new_email
            })

            return EmailResponse(
                success=True,
                email_address=request.email_address,
                subject=result.get("subject", ""),
                email=result.get("email", ""),
                thread_subject=result.get("thread_subject"),
                thread_email_count=result.get("thread_email_count", 0),
                is_new_email=is_new_email,
                intent=extracted_intent,
                session_id=session_id,
                message=f"Email generated successfully (Intent: {extracted_intent})"
            )
        else:
            return EmailResponse(
                success=False,
                email_address=request.email_address,
                message=result.get("error", "Unknown error occurred")
            )

    except HTTPException:
        raise
    except Exception as e:
        return EmailResponse(
            success=False,
            email_address=request.email_address,
            message=f"Server error: {str(e)}"
        )


@app.post("/generate-multiple", response_model=MultiEmailResponse)
async def generate_multiple_emails_endpoint(request: GenerateMultipleEmailsRequest):
    """
    Generate emails for multiple addresses based on email goal
    Intent is automatically extracted for each conversation

    For each address:
    - Fetch threads
    - Find most relevant thread based on goal
    - Auto-extract intent from conversation
    - Generate contextual email OR new email if no context

    Args:
        request: GenerateMultipleEmailsRequest

    Returns:
        MultiEmailResponse with emails for each address
    """
    try:
        # Parse email addresses
        email_addresses = [addr.strip() for addr in request.email_addresses.split(',') if addr.strip()]

        if not email_addresses:
            raise HTTPException(
                status_code=400,
                detail="At least one email address is required"
            )

        if not request.email_goal:
            raise HTTPException(
                status_code=400,
                detail="Email goal is required for multiple email generation"
            )

        # Validate provider
        if request.provider.lower() not in ["gmail", "outlook"]:
            raise HTTPException(
                status_code=400,
                detail="Provider must be 'gmail' or 'outlook'"
            )

        generated_emails = []

        for email_address in email_addresses:
            try:
                # Fetch threads for this address
                threads_result = get_threads_for_multiple_addresses(
                    email_addresses=[email_address],
                    provider=request.provider,
                    max_emails=request.max_emails
                )

                if not threads_result.get("success"):
                    # No threads - generate new email
                    email_result = generate_new_email(
                        email_address=email_address,
                        email_goal=request.email_goal,
                        tone=request.tone
                    )

                    if email_result.get("success"):
                        session_id = save_generation({
                            "email_address": email_address,
                            "thread_subject": "New Email",
                            "intent": "new",
                            "subject": email_result.get("subject", ""),
                            "email": email_result.get("email", ""),
                            "tone": request.tone,
                            "email_goal": request.email_goal,
                            "is_new_email": True
                        })

                        generated_emails.append(EmailResponse(
                            success=True,
                            email_address=email_address,
                            subject=email_result.get("subject", ""),
                            email=email_result.get("email", ""),
                            is_new_email=True,
                            intent="new",
                            session_id=session_id
                        ))
                    continue

                # Get threads for this address
                address_data = threads_result["addresses_data"][0]
                threads = address_data["threads"]

                if not threads:
                    # No context - generate new email
                    email_result = generate_new_email(
                        email_address=email_address,
                        email_goal=request.email_goal,
                        tone=request.tone
                    )
                else:
                    # Filter threads by goal
                    filtered_result = filter_threads_by_goal(
                        threads=threads,
                        email_goal=request.email_goal
                    )

                    if filtered_result.get("success") and filtered_result.get("relevant_threads"):
                        # Use most relevant thread
                        most_relevant_thread = filtered_result["relevant_threads"][0]

                        # Generate contextual email with auto-extracted intent
                        email_result = generate_email_from_thread(
                            email_address=email_address,
                            thread_id=most_relevant_thread["thread_id"],
                            intent=None,  # Auto-extract intent
                            email_goal=request.email_goal,
                            provider=request.provider,
                            tone=request.tone,
                            max_emails=request.max_emails
                        )
                    else:
                        # No relevant threads - generate new
                        email_result = generate_new_email(
                            email_address=email_address,
                            email_goal=request.email_goal,
                            tone=request.tone
                        )

                if email_result.get("success"):
                    is_new = email_result.get("is_new_email", False)
                    extracted_intent = email_result.get("intent", "new" if is_new else "reply")

                    session_id = save_generation({
                        "email_address": email_address,
                        "thread_subject": email_result.get("thread_subject", "New Email"),
                        "intent": extracted_intent,
                        "subject": email_result.get("subject", ""),
                        "email": email_result.get("email", ""),
                        "tone": request.tone,
                        "email_goal": request.email_goal,
                        "thread_email_count": email_result.get("thread_email_count", 0),
                        "is_new_email": is_new
                    })

                    generated_emails.append(EmailResponse(
                        success=True,
                        email_address=email_address,
                        subject=email_result.get("subject", ""),
                        email=email_result.get("email", ""),
                        thread_subject=email_result.get("thread_subject"),
                        thread_email_count=email_result.get("thread_email_count", 0),
                        is_new_email=is_new,
                        intent=extracted_intent,
                        session_id=session_id
                    ))
                else:
                    generated_emails.append(EmailResponse(
                        success=False,
                        email_address=email_address,
                        message=email_result.get("error", "Failed to generate")
                    ))

            except Exception as e:
                generated_emails.append(EmailResponse(
                    success=False,
                    email_address=email_address,
                    message=f"Error: {str(e)}"
                ))

        return MultiEmailResponse(
            success=True,
            emails=generated_emails,
            total_generated=len([e for e in generated_emails if e.success]),
            message=f"Generated {len([e for e in generated_emails if e.success])} emails successfully with auto-extracted intents"
        )

    except HTTPException:
        raise
    except Exception as e:
        return MultiEmailResponse(
            success=False,
            message=f"Server error: {str(e)}"
        )


@app.put("/history/{session_id}", response_model=UpdateResponse)
async def update_session_endpoint(session_id: str, request: UpdateSessionRequest):
    """Update an existing session with edited email content"""
    try:
        session = get_session_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        update_data = {}
        if request.subject is not None:
            update_data["subject"] = request.subject
        if request.email_body is not None:
            update_data["email_body"] = request.email_body
        if request.email_goal is not None:
            update_data["email_goal"] = request.email_goal
        if request.tone is not None:
            update_data["tone"] = request.tone

        success = update_session(session_id, update_data)

        return UpdateResponse(
            success=success,
            message="Session updated successfully in database" if success else "Failed to update session"
        )

    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error updating session: {str(e)}"}
        )


@app.get("/history", response_model=HistoryResponse)
async def get_history(limit: int = 50):
    """Get email generation history from SQLite database"""
    try:
        sessions = get_all_sessions(limit=limit)
        return HistoryResponse(
            success=True,
            sessions=sessions,
            total=len(sessions),
            message="History retrieved successfully from database"
        )
    except Exception as e:
        return HistoryResponse(success=False, message=f"Error retrieving history: {str(e)}")


@app.get("/history/{session_id}")
async def get_history_by_id(session_id: str):
    """Get specific session from history"""
    try:
        session = get_session_by_id(session_id)
        if session:
            return {"success": True, "session": session, "message": "Session retrieved successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error retrieving session: {str(e)}"}
        )


@app.delete("/history/{session_id}")
async def delete_history_item(session_id: str):
    """Delete specific session from history"""
    try:
        deleted = delete_session(session_id)
        if deleted:
            return {"success": True, "message": "Session deleted successfully from database"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error deleting session: {str(e)}"}
        )


@app.post("/history/clear")
async def clear_history():
    """Clear all history"""
    try:
        success = clear_all_history()
        if success:
            return {"success": True, "message": "All history cleared from database"}
        else:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "Failed to clear history"}
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error clearing history: {str(e)}"}
        )


@app.get("/stats", response_model=StatsResponse)
async def get_statistics():
    """Get statistics about email generation history"""
    try:
        stats = get_stats()
        return StatsResponse(success=True, stats=stats, message="Statistics retrieved successfully")
    except Exception as e:
        return StatsResponse(success=False, message=f"Error retrieving statistics: {str(e)}")


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  MULTI-ADDRESS EMAIL GENERATOR v5.0 - AUTO-INTENT + SQLITE")
    print("="*70)
    print(f"\n🌐 Server: http://localhost:8000")
    print(f"📚 API Docs: http://localhost:8000/docs")
    print(f"🤖 LLM: {os.getenv('LLM_MODEL', 'gpt-oss-20b')}")
    print(f"📧 Providers: Gmail (Outlook coming soon)")
    print(f"💾 Database: SQLite (email_history.db)")
    print(f"\n✨ NEW IN v5.0:")
    print(f"  • Automatic intent extraction from conversations (LLM-powered)")
    print(f"  • SQLite database instead of JSON")
    print(f"  • Enhanced edit capabilities with database persistence")
    print(f"\n📊 Workflow:")
    print(f"  1. Accept multiple email addresses (comma-separated)")
    print(f"  2. Optional Email Goal for context filtering")
    print(f"  3. Fetch emails and group into threads")
    print(f"  4. Auto-extract intent from conversation (reply/follow_up/reminder/inquiry)")
    print(f"  5. Filter threads by goal using LLM (if goal provided)")
    print(f"  6. Generate contextual OR new emails")
    print(f"  7. Save to SQLite database with full edit support")
    print(f"\n✨ Features:")
    print(f"  • Multiple email addresses support")
    print(f"  • Automatic intent extraction (no manual selection)")
    print(f"  • Goal-based thread filtering")
    print(f"  • Contextual email generation")
    print(f"  • New email from scratch")
    print(f"  • Edit and update emails in database")
    print(f"  • Full history management with SQLite")
    print("\n" + "="*70)
    print("✅ Server starting...\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")