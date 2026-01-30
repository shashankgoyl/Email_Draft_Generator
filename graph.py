"""
LangGraph Workflow - Multi-Address Email Generation with Goal-Based Filtering
1. Fetch emails for multiple addresses and group into threads
2. Extract intent from conversation using LLM (automatic)
3. Filter threads by email goal using LLM (if goal provided)
4. Generate contextual emails from threads OR new emails from scratch
"""

from typing import Dict, Optional, List
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage

from email_provider import fetch_threads, format_thread_for_context

load_dotenv()

# ============================================================================
# LLM SETUP
# ============================================================================

from langchain_aws import ChatBedrock

llm = ChatBedrock(
    model_id="openai.gpt-oss-20b-1:0",
    region_name="eu-west-2",
    model_kwargs={
        "max_tokens": 100000
    }
)

# ============================================================================
# INTENT EXTRACTION FROM CONVERSATION
# ============================================================================

def extract_intent_from_thread(thread: Dict, email_goal: Optional[str] = None) -> str:
    """
    Extract the intent from a conversation thread using LLM

    Args:
        thread: Thread dictionary with conversation history
        email_goal: Optional user's goal for the email

    Returns:
        Intent string: 'reply', 'follow_up', 'reminder', or 'inquiry'
    """
    print(f"\n🎯 Extracting intent from conversation thread...")

    # Format thread context
    thread_summary = f"""
Subject: {thread.get('subject', 'No Subject')}
Total Emails: {thread.get('email_count', 0)}
Participants: {', '.join(thread.get('participants', []))}

Recent Email Snippet: {thread.get('snippet', '')[:300]}
"""

    if thread.get('emails'):
        # Get last 2 emails for context
        last_emails = thread['emails'][-2:]
        for idx, email in enumerate(last_emails):
            thread_summary += f"\n\nEmail #{idx + 1}:\n"
            thread_summary += f"From: {email.get('from', 'Unknown')}\n"
            thread_summary += f"Date: {email.get('date', 'Unknown')}\n"
            thread_summary += f"Body: {email.get('body', '')[:400]}...\n"

    system_msg = """You are an expert email assistant that analyzes conversation threads to determine the appropriate intent for a reply.

Your task: Analyze the conversation thread and determine the most appropriate intent for the next email.

Intent types:
- reply: Direct response to a question or request in the most recent email
- follow_up: Continuing a previous conversation with updates or additional information
- reminder: Gentle reminder about pending items, unanswered questions, or awaiting response
- inquiry: Asking for information, clarification, or updates

Return ONLY ONE WORD: reply, follow_up, reminder, or inquiry"""

    user_msg = f"""Analyze this conversation thread and determine the intent:

{thread_summary}"""

    if email_goal:
        user_msg += f"\n\nUser's Goal: {email_goal}"
        user_msg += "\n\nConsider the user's goal when determining intent."

    user_msg += "\n\nReturn ONLY the intent (reply, follow_up, reminder, or inquiry):"

    try:
        response = llm.invoke([
            SystemMessage(content=system_msg),
            HumanMessage(content=user_msg)
        ])

        intent = response.content.strip().lower()

        # Validate intent
        valid_intents = ['reply', 'follow_up', 'reminder', 'inquiry']
        if intent not in valid_intents:
            # Try to extract valid intent from response
            for valid_intent in valid_intents:
                if valid_intent in intent:
                    intent = valid_intent
                    break
            else:
                intent = 'reply'  # Default fallback

        print(f"✅ Extracted intent: {intent}")
        return intent

    except Exception as e:
        print(f"❌ Error extracting intent: {e}")
        return 'reply'  # Default fallback


# ============================================================================
# MULTI-ADDRESS THREAD FETCHING
# ============================================================================

def get_threads_for_multiple_addresses(
    email_addresses: List[str],
    provider: str = "gmail",
    max_emails: int = 100
) -> Dict:
    """
    Fetch and return conversation threads for multiple email addresses

    Args:
        email_addresses: List of email addresses
        provider: 'gmail' or 'outlook'
        max_emails: Number of emails to fetch per address

    Returns:
        Dictionary with threads for each address
    """
    print("\n" + "="*70)
    print("📧 FETCHING THREADS FOR MULTIPLE ADDRESSES")
    print("="*70)
    print(f"📋 Addresses: {len(email_addresses)}")
    print(f"🌐 Provider: {provider}")
    print(f"📊 Max Emails per Address: {max_emails}")
    print("="*70)

    addresses_data = []

    for email_address in email_addresses:
        print(f"\n🔍 Fetching threads for: {email_address}")

        try:
            # Fetch threads for this address
            threads = fetch_threads(
                provider=provider,
                email_address=email_address,
                max_results=max_emails
            )

            total_emails = sum(t['email_count'] for t in threads)

            addresses_data.append({
                "email_address": email_address,
                "threads": threads,
                "total_emails": total_emails,
                "success": True
            })

            print(f"✅ Found {len(threads)} threads ({total_emails} emails)")

        except Exception as e:
            print(f"❌ Error fetching threads for {email_address}: {e}")
            addresses_data.append({
                "email_address": email_address,
                "threads": [],
                "total_emails": 0,
                "success": False,
                "error": str(e)
            })

    print("\n" + "="*70)
    print("✅ MULTI-ADDRESS FETCH COMPLETE")
    print("="*70)

    return {
        "success": True,
        "addresses_data": addresses_data,
        "total_addresses": len(addresses_data)
    }


# ============================================================================
# GOAL-BASED THREAD FILTERING
# ============================================================================

def filter_threads_by_goal(
    threads: List[Dict],
    email_goal: str
) -> Dict:
    """
    Filter conversation threads based on email goal using LLM

    Args:
        threads: List of thread dictionaries
        email_goal: User's email goal

    Returns:
        Dictionary with filtered relevant threads
    """
    print("\n" + "="*70)
    print("🎯 FILTERING THREADS BY GOAL")
    print("="*70)
    print(f"📝 Email Goal: {email_goal}")
    print(f"📊 Total Threads: {len(threads)}")
    print("="*70)

    if not threads:
        return {
            "success": True,
            "relevant_threads": [],
            "message": "No threads to filter"
        }

    # Prepare thread summaries for LLM
    thread_summaries = []
    for idx, thread in enumerate(threads):
        summary = {
            "index": idx,
            "thread_id": thread["thread_id"],
            "subject": thread["subject"],
            "email_count": thread["email_count"],
            "participants": ", ".join(thread["participants"][:3]),  # First 3 participants
            "snippet": thread["snippet"][:200]  # First 200 chars
        }
        thread_summaries.append(summary)

    # Create prompt for LLM to analyze relevance
    system_msg = """You are an expert email assistant that analyzes conversation threads.

Your task: Given a user's email goal and a list of conversation threads, identify which threads are most relevant to achieving that goal.

Return ONLY a JSON array of thread indices, ordered by relevance (most relevant first).
Example: [2, 5, 0]

If no threads are relevant, return an empty array: []"""

    user_msg = f"""Email Goal:
{email_goal}

Conversation Threads:
{format_threads_for_analysis(thread_summaries)}

Return the indices of threads relevant to this goal, ordered by relevance."""

    try:
        response = llm.invoke([
            SystemMessage(content=system_msg),
            HumanMessage(content=user_msg)
        ])

        # Parse response
        response_text = response.content.strip()

        # Extract JSON array from response
        import json
        import re

        # Try to find JSON array in response
        json_match = re.search(r'\[[\d,\s]*\]', response_text)
        if json_match:
            relevant_indices = json.loads(json_match.group())
        else:
            relevant_indices = []

        # Get relevant threads
        relevant_threads = []
        for idx in relevant_indices:
            if 0 <= idx < len(threads):
                relevant_threads.append(threads[idx])

        print(f"✅ Found {len(relevant_threads)} relevant threads")

        return {
            "success": True,
            "relevant_threads": relevant_threads,
            "total_relevant": len(relevant_threads)
        }

    except Exception as e:
        print(f"❌ Error filtering threads: {e}")
        return {
            "success": False,
            "relevant_threads": [],
            "error": str(e)
        }


def format_threads_for_analysis(thread_summaries: List[Dict]) -> str:
    """Format thread summaries for LLM analysis"""
    formatted = []
    for summary in thread_summaries:
        formatted.append(
            f"Index {summary['index']}: Subject: \"{summary['subject']}\" | "
            f"Emails: {summary['email_count']} | "
            f"Participants: {summary['participants']} | "
            f"Snippet: {summary['snippet']}"
        )
    return "\n".join(formatted)


# ============================================================================
# EMAIL GENERATION FROM THREAD
# ============================================================================

def node_fetch_threads(state: Dict) -> Dict:
    """Node 1: Fetch emails and group them into conversation threads"""
    print("\n" + "="*60)
    print("📧 NODE 1: FETCHING EMAILS & CREATING THREADS")
    print("="*60)

    email_address = state.get("email_address")
    provider = state.get("provider", "gmail")
    max_emails = state.get("max_emails", 100)

    if not email_address:
        print("⚠️ No email address provided")
        state["threads"] = []
        state["error"] = "No email address provided"
        return state

    try:
        threads = fetch_threads(
            provider=provider,
            email_address=email_address,
            max_results=max_emails
        )

        state["threads"] = threads
        state["total_emails"] = sum(t['email_count'] for t in threads)

        print(f"✅ Created {len(threads)} conversation threads from {state['total_emails']} emails")

    except Exception as e:
        print(f"❌ Error fetching threads: {e}")
        state["threads"] = []
        state["error"] = f"Failed to fetch emails: {str(e)}"

    return state


def node_prepare_context(state: Dict) -> Dict:
    """Node 2: Prepare context from selected thread and extract intent using LLM"""
    print("\n" + "="*60)
    print("🧵 NODE 2: PREPARING THREAD CONTEXT & EXTRACTING INTENT")
    print("="*60)

    threads = state.get("threads", [])
    selected_thread_id = state.get("selected_thread_id")
    selected_email_index = state.get("selected_email_index")
    email_goal = state.get("email_goal", "")

    if not threads:
        print("⚠️ No threads available")
        state["error"] = "No threads available"
        return state

    # Find the selected thread
    selected_thread = None
    for thread in threads:
        if thread["thread_id"] == selected_thread_id:
            selected_thread = thread
            break

    if not selected_thread:
        print("⚠️ Selected thread not found")
        state["error"] = "Selected thread not found"
        return state

    # Extract intent from thread using LLM (automatic)
    intent = extract_intent_from_thread(selected_thread, email_goal)
    state["intent"] = intent

    print(f"📧 Thread: {selected_thread['subject']}")
    print(f"📊 Emails in thread: {selected_thread['email_count']}")
    print(f"🎯 Extracted Intent: {intent}")
    if selected_email_index is not None:
        print(f"🔍 Focusing on email #{selected_email_index + 1}")

    # Format thread context
    thread_context = format_thread_for_context(selected_thread, selected_email_index)
    state["thread_context"] = thread_context
    state["selected_thread"] = selected_thread

    print("✅ Context prepared with auto-extracted intent")

    return state


def node_generate_email(state: Dict) -> Dict:
    """Node 3: Generate email using LLM with extracted intent"""
    print("\n" + "="*60)
    print("✍️ NODE 3: GENERATING EMAIL")
    print("="*60)

    thread_context = state.get("thread_context", "")
    intent = state.get("intent", "reply")
    tone = state.get("tone", "professional")
    email_goal = state.get("email_goal", "")

    if not thread_context:
        print("⚠️ No thread context available")
        state["error"] = "No thread context available"
        return state

    print(f"🎯 Intent: {intent}")
    print(f"🎨 Tone: {tone}")
    if email_goal:
        print(f"📝 Goal: {email_goal}")

    # Intent-specific instructions
    intent_instructions = {
        "reply": "Write a direct, responsive reply to the most recent email in the thread. Address their questions or points clearly.",
        "follow_up": "Write a follow-up email continuing the conversation. Provide updates, additional information, or move the discussion forward.",
        "reminder": "Write a gentle reminder about pending items or unanswered questions. Be polite and professional, not pushy.",
        "inquiry": "Write an email asking for information, clarification, or updates. Be specific about what you need."
    }

    intent_instruction = intent_instructions.get(intent, intent_instructions["reply"])

    system_msg = f"""You are a professional email writer with expertise in business communication.

TASK: Generate an email based on the conversation thread provided.

TONE: {tone}

INTENT: {intent}
{intent_instruction}

IMPORTANT:
- Write in a {tone} tone
- Reference relevant parts of the conversation naturally
- Keep it concise and focused
- Include appropriate greeting and closing
- Do not makeup any PII
- Use proper email etiquette

Email Format:
Subject: [Clear subject line]

[Email body with greeting, content, and closing]"""

    user_msg = f"""Generate an email based on this conversation thread:

{thread_context}

Email Goal: {email_goal if email_goal else 'None - use the thread context and intent to write an appropriate email.'}

Intent: {intent}

Write a complete email with subject and body that fulfills the user's goal."""

    try:
        response = llm.invoke([
            SystemMessage(content=system_msg),
            HumanMessage(content=user_msg)
        ])

        email_text = response.content.partition("</reasoning>")[2].strip()

        # Extract subject and remove it from email body
        subject = "Email"
        email_body = email_text

        if "Subject:" in email_text:
            lines = email_text.split('\n')
            subject_line_idx = None

            for idx, line in enumerate(lines):
                if line.strip().startswith('Subject:'):
                    subject = line.split('Subject:', 1)[1].strip()
                    subject_line_idx = idx
                    break

            # Remove the subject line from email body
            if subject_line_idx is not None:
                body_lines = lines[:subject_line_idx] + lines[subject_line_idx + 1:]
                # Remove leading empty lines
                while body_lines and not body_lines[0].strip():
                    body_lines.pop(0)
                email_body = '\n'.join(body_lines).strip()

        state["generated_email"] = email_body
        state["subject"] = subject

        print(f"✅ Email generated")
        print(f"Subject: {subject}")

    except Exception as e:
        print(f"❌ Error generating email: {e}")
        state["generated_email"] = "Failed to generate email."
        state["subject"] = "Error"
        state["error"] = f"Generation failed: {str(e)}"

    return state


# ============================================================================
# NEW EMAIL GENERATION (FROM SCRATCH)
# ============================================================================

def generate_new_email(
    email_address: str,
    email_goal: str,
    tone: str = "professional"
) -> Dict:
    """
    Generate a new email from scratch (no thread context)

    Args:
        email_address: Recipient email address
        email_goal: Purpose of the email
        tone: Email tone

    Returns:
        Dictionary with generated email
    """
    print("\n" + "="*70)
    print("📝 GENERATING NEW EMAIL FROM SCRATCH")
    print("="*70)
    print(f"📧 To: {email_address}")
    print(f"🎯 Goal: {email_goal}")
    print(f"🎨 Tone: {tone}")
    print("="*70)

    system_msg = f"""You are a professional email writer.

TASK: Write a new email from scratch.

TONE: {tone}

IMPORTANT:
- Write a clear, professional email
- Stay focused on the user's stated goal
- Include appropriate greeting and closing
- Do not reference any previous conversation (this is a new email)
- Include a clear subject line
- Do not makeup any PII

Email Format:
Subject: [Clear subject line]

[Email body with greeting, content, and closing]"""

    user_msg = f"""Write a new email to {email_address} with the following goal:

{email_goal}

Tone: {tone}

Write a complete email with subject and body."""

    try:
        response = llm.invoke([
            SystemMessage(content=system_msg),
            HumanMessage(content=user_msg)
        ])

        email_text = response.content.partition("</reasoning>")[2].strip()

        # Extract subject
        subject = "Email"
        email_body = email_text

        if "Subject:" in email_text:
            lines = email_text.split('\n')
            for idx, line in enumerate(lines):
                if line.strip().startswith('Subject:'):
                    subject = line.split('Subject:', 1)[1].strip()
                    # Remove subject line from body
                    body_lines = lines[:idx] + lines[idx + 1:]
                    while body_lines and not body_lines[0].strip():
                        body_lines.pop(0)
                    email_body = '\n'.join(body_lines).strip()
                    break

        print(f"✅ New email generated")
        print(f"Subject: {subject}")

        return {
            "success": True,
            "subject": subject,
            "email": email_body,
            "is_new_email": True,
            "intent": "new"
        }

    except Exception as e:
        print(f"❌ Error generating new email: {e}")
        return {
            "success": False,
            "error": f"Generation failed: {str(e)}",
            "is_new_email": True,
            "intent": "new"
        }


# ============================================================================
# BUILD WORKFLOW
# ============================================================================

def build_workflow():
    """Build the LangGraph workflow for thread-based email generation"""

    workflow = StateGraph(dict)

    # Add nodes
    workflow.add_node("fetch_threads", node_fetch_threads)
    workflow.add_node("prepare_context", node_prepare_context)
    workflow.add_node("generate_email", node_generate_email)

    # Define flow
    workflow.set_entry_point("fetch_threads")
    workflow.add_edge("fetch_threads", "prepare_context")
    workflow.add_edge("prepare_context", "generate_email")
    workflow.add_edge("generate_email", END)

    return workflow.compile()


# Create workflow instance
email_workflow = build_workflow()


# ============================================================================
# MAIN EXECUTION FUNCTIONS
# ============================================================================

def generate_email_from_thread(
    email_address: str,
    thread_id: str,
    intent: Optional[str] = None,  # Now optional - will be auto-extracted
    selected_email_index: Optional[int] = None,
    email_goal: str = "",
    provider: str = "gmail",
    tone: str = "professional",
    max_emails: int = 100
) -> Dict:
    """
    Generate email based on selected thread with auto-extracted intent

    Args:
        email_address: Email address to fetch conversation history
        thread_id: ID of the selected conversation thread
        intent: Optional manual intent override (if None, will be auto-extracted)
        selected_email_index: Index of specific email to focus on (0-based, optional)
        email_goal: User's goal for the email
        provider: 'gmail' or 'outlook'
        tone: Email tone
        max_emails: Number of emails to fetch

    Returns:
        Dictionary with generated email
    """
    print("\n" + "="*70)
    print("🚀 EMAIL GENERATION WORKFLOW")
    print("="*70)
    print(f"📧 Email Address: {email_address}")
    print(f"🧵 Thread ID: {thread_id}")
    if intent:
        print(f"🎯 Manual Intent Override: {intent}")
    else:
        print(f"🎯 Intent: Auto-extracting from conversation")
    if selected_email_index is not None:
        print(f"🔍 Focused Email: #{selected_email_index + 1}")
    if email_goal:
        print(f"🎯 Goal: {email_goal}")
    print(f"🎨 Tone: {tone}")
    print("="*70)

    state = {
        "email_address": email_address,
        "provider": provider,
        "max_emails": max_emails,
        "selected_thread_id": thread_id,
        "selected_email_index": selected_email_index,
        "intent": intent,  # Can be None - will be auto-extracted
        "tone": tone,
        "email_goal": email_goal,
        "threads": [],
        "thread_context": "",
        "generated_email": "",
        "subject": "",
        "error": None
    }

    # Run workflow
    result = email_workflow.invoke(state)

    if result.get("error"):
        return {
            "success": False,
            "error": result["error"]
        }

    print("\n" + "="*70)
    print("✅ EMAIL GENERATION COMPLETE")
    print("="*70)

    return {
        "success": True,
        "subject": result.get("subject", ""),
        "email": result.get("generated_email", ""),
        "thread_subject": result.get("selected_thread", {}).get("subject", ""),
        "thread_email_count": result.get("selected_thread", {}).get("email_count", 0),
        "intent": result.get("intent", "reply")  # Return the extracted intent
    }