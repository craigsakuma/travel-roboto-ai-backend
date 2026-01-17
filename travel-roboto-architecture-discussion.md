# Travel Roboto Architecture Discussion - Study Guide

**Date**: January 16, 2025
**Purpose**: Documentation of architectural decisions for AI-powered travel planning assistant
**Use Case**: Study guide for understanding AI application architecture decisions

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [System Architecture Decisions](#system-architecture-decisions)
3. [Agent Design Philosophy](#agent-design-philosophy)
4. [Tool & Function Calling](#tool--function-calling)
5. [Context Management Strategy](#context-management-strategy)
6. [Data Synchronization](#data-synchronization)
7. [Email Integration & Extraction](#email-integration--extraction)
8. [Conflict Resolution Intelligence](#conflict-resolution-intelligence)
9. [Privacy & Multi-Tenancy](#privacy--multi-tenancy)
10. [Observability & Debugging](#observability--debugging)
11. [Cost Management](#cost-management)
12. [Testing Strategy](#testing-strategy)
13. [Deployment & Environment](#deployment--environment)
14. [Phased Roadmap](#phased-roadmap)

---

## Project Overview

### Business Context
- **Primary Goal**: Portfolio project demonstrating AI/ML engineering skills
- **Secondary Goal**: Real business potential with active user engagement
- **Target Audience**: AI/ML Engineer job recruiters
- **Success Metrics**: 70% breadth (touch all AI skills), 30% depth (2-3 deep implementations)

### Core User Experience
Users can:
1. Forward travel confirmation emails to the system
2. Chat with AI agent about trip details
3. Collaborate with other travelers (privacy-preserving)
4. Get intelligent responses about itineraries, logistics, bookings

### Tech Stack
**Frontend**: Next.js 15 + React 19 + Supabase (auth + UI data)
**Backend**: FastAPI + PostgreSQL + LLMs (Claude, GPT-4)
**Integration**: Gmail API for email ingestion

---

## System Architecture Decisions

### Question: How Should Frontend and Backend Interact?

**Options Considered:**

**Option A - Replace Supabase Entirely**
- Frontend calls FastAPI for everything
- Single database (PostgreSQL)
- Simpler data model, but requires rewriting all frontend data access

**Option B - Dual Database Strategy** ✅ **CHOSEN**
- Frontend: Supabase for auth + UI state
- Backend: PostgreSQL for AI context + comprehensive history
- Frontend calls FastAPI only for AI generation

**Decision Rationale:**
- Frontend already built with Supabase
- Backend needs rich data for AI context (conversation history, extractions, embeddings)
- Acceptable data duplication (messages stored in both systems)
- **Key Principle**: Backend is source of truth for AI, Supabase is source of truth for UI

**Trade-offs:**
- ✅ Faster to implement (no frontend rewrite)
- ✅ Each system optimized for its purpose
- ❌ Data synchronization complexity
- ❌ Potential consistency issues (mitigated by sync endpoints)

---

### Question: How to Handle User/Trip Data Sync?

**Options Considered:**

**Option A - Sync Endpoints** ✅ **CHOSEN**
```
POST /users/sync - Frontend pushes user create/update
POST /trips/sync - Frontend pushes trip create/update
DELETE /trips/{id} - Frontend notifies deletion
```

**Option B - Full CRUD REST API**
```
POST /users, PUT /users/{id}, GET /users/{id}
POST /trips, PUT /trips/{id}, GET /trips/{id}
Backend becomes primary datastore
```

**Decision Rationale:**
- Frontend owns primary user/trip data (Supabase)
- Backend receives updates for AI context
- Clearer contract: "sync" indicates direction of data flow
- Simpler than distributed transactions

**Implementation:**
- Frontend triggers sync on: account creation, profile edit, trip create/edit/delete
- Backend stores: user_id, email, phone, home_city, first_name, last_name
- Backend stores: trip_id, name, location, start_date, end_date, travelers

---

### Question: Should We Reuse Supabase IDs or Create Separate IDs?

**Options Considered:**

**Option A - Reuse Supabase UUIDs** ✅ **CHOSEN**
- Same user_id, trip_id, conversation_id in both systems
- No mapping table needed

**Option B - Separate IDs with Mapping**
- Backend generates own IDs
- Mapping table: supabase_id → backend_id

**Decision Rationale:**
- Simpler debugging (same ID refers to same entity)
- No mapping overhead
- UUIDs are globally unique anyway
- Backend creates own IDs only for backend-specific entities (messages, embeddings, tool_calls)

---

## Agent Design Philosophy

### Question: Single Agent or Multi-Agent from Day 1?

**Options Considered:**

**Option A - Monolithic Agent**
- Single "Travel Assistant" handles all queries
- Simpler to build and debug

**Option B - Multi-Agent from Start** ✅ **CHOSEN**
- Travel Concierge (chat interface)
- Trip Coordinator (email/doc extraction)
- Clear separation of responsibilities

**Decision Rationale:**
- Showcases agent orchestration skill
- Different agents have different context needs
- **Key Insight**: Start with independent agents (simpler) before building orchestrator
- Evolution path: Independent → Orchestrated → Specialized sub-agents

**Phase 1**: Two independent agents
```
User chat → Travel Concierge (synchronous)
Email webhook → Trip Coordinator (async background job)
Agents don't talk to each other, share data via DB
```

**Phase 3**: Orchestrated collaboration
```
User: "What hotel am I staying at?"
→ Orchestrator checks if itinerary exists
  → If missing: Trip Coordinator searches emails
  → Travel Concierge uses results to answer
```

---

### Question: When to Introduce Agent Routing?

**Options Considered:**

**Option A - Build Routing in Phase 1** ✅ **CHOSEN**
- Create AgentRouter framework early
- Initially only routes to single Concierge
- Easy to add specialists later (restaurant_expert, flight_checker, local_transport_agent)

**Option B - Add Routing in Phase 3**
- Keep simple for MVP
- Refactor when adding specialists

**Decision Rationale:**
- Shows architectural foresight to recruiters
- LLM-based intent classification is itself impressive
- Minimal overhead to build extensible router vs hardcoded routing

**Implementation Pattern:**
```python
# Phase 1: Router with single agent
router = AgentRouter(agents=[travel_concierge])
response = await router.route_and_execute(user_message)

# Phase 3: Just add agents, router stays same
router = AgentRouter(agents=[
    travel_concierge,
    restaurant_expert,
    flight_checker,
    local_transport_agent
])
```

---

### Question: How Much Domain Knowledge in Agent Prompts?

**Options Considered:**

**Style A - Minimal Prompt (Rely on Tools)**
```
You are a helpful travel assistant.
Answer using available tools.
Be friendly and concise.
```

**Style B - Rich Domain Knowledge** ✅ **CHOSEN for MVP**
```
You are Travel Roboto, expert in:
- Flights, hotels, activities, logistics
- Always cite sources (e.g., "According to your United email...")
- If info missing, ask clarifying questions
- Emphasize confirmation codes for time-sensitive items
- Be proactive: suggest related info when relevant

Current trip: {trip_summary}
Recent conversation: {last_n_messages}
```

**Decision Rationale:**
- Style B easier to iterate in early stages (change prompt, not code)
- Shows prompt engineering skill to recruiters
- **Evolution path**: Style B (MVP) → Style A + RAG (later)
  - Move domain knowledge from prompt to retrieval system
  - More scalable, but requires user data first

**Key Principle**: Start with knowledge in prompts, extract to RAG as you gather data

---

## Tool & Function Calling

### Question: How to Structure Tools for Maximum Flexibility?

**Pattern A - Pydantic Models (Type-Safe)** ✅ **CHOSEN**
```python
class GetTripDetailsInput(BaseModel):
    trip_id: str = Field(description="UUID of the trip")

class GetTripDetailsOutput(BaseModel):
    trip_name: str
    destination: str
    dates: str
    summary: str

@tool_registry.register(
    name="get_trip_details",
    description="Retrieve trip information",
    input_schema=GetTripDetailsInput,
    output_schema=GetTripDetailsOutput
)
async def get_trip_details(trip_id: str, context: ToolContext):
    trip = await context.db.trips.get(trip_id)
    return GetTripDetailsOutput(...)
```

**Pattern B - Native LLM Format (JSON Schema)**
```python
{
  "type": "function",
  "function": {
    "name": "get_trip_details",
    "parameters": {
      "type": "object",
      "properties": {"trip_id": {"type": "string"}},
      "required": ["trip_id"]
    }
  }
}
```

**Decision Rationale:**
- Define tools once in Python (DRY principle)
- Auto-generate OpenAI/Anthropic schemas from Pydantic
- Type safety catches errors at development time
- Easy to unit test tools in isolation
- **Shows software engineering discipline alongside AI skills**

---

### Question: Who Triggers Tools - User or System?

**Scenario: Email Extraction Tool**

**Option 1 - User-Initiated (Agent Decision)**
```
User: "I forwarded my hotel confirmation"
→ Concierge calls extract_email_data(email_id)
→ Returns extracted data immediately
```

**Option 2 - System-Initiated (Background Job)** ✅ **CHOSEN**
```
Email webhook triggers → Coordinator runs automatically
→ Extracts data silently in background
→ User asks later: "Where am I staying?" → Data already ready
```

**Decision Rationale:**
- Better UX (data ready when user asks)
- Shows event-driven architecture skill
- Tools are internal implementation, not exposed to chat
- **Key Principle**: Automation over manual triggers

---

### Question: Where Does Business Logic Live?

**Scenario**: User asks "Add Sarah to my Barcelona trip"

**Option A - Agent Decides Everything**
```
Agent calls: add_traveler(trip_id, name="Sarah")
Tool is dumb executor, just writes to DB
All validation in agent prompt
```

**Option B - Backend Enforces Rules** ✅ **CHOSEN**
```
Agent calls: add_traveler(trip_id, name="Sarah")
Backend validates:
  - Is user owner of trip?
  - Max travelers reached?
  - Is Sarah already on trip?
Tool returns error if invalid
Agent handles error gracefully in response
```

**Decision Rationale:**
- **Agents are unreliable** (hallucinations, prompt injection)
- Backend enforces data integrity
- Tools have smart validation logic
- Clear separation: Agent decides intent, Backend enforces rules

**Key Principle**: Never trust LLM for data validation or security

---

### Initial Tool Set

**Phase 1:**
- `get_trip_details(trip_id)` - Read trip from DB

**Phase 1B:**
- `extract_trip_data(email_text)` - Parse email/doc for trip info

**Phase 1C:**
- `detect_conflicts(existing, new)` - LLM-based conflict detection
- `send_confirmation_email(user, changes)` - User validation

**Phase 2:**
- `search_past_conversations(query)` - Semantic search over history

---

## Context Management Strategy

### Question: How Much Conversation History to Send to LLM?

**Options Considered:**

**Option A - All Messages**
- Send entire conversation every time
- Simple, but expensive and slow for long threads

**Option B - Last N Turns** ✅ **CHOSEN for MVP**
- Send last 10 message pairs (20 messages)
- Fixed context window

**Option C - Summarization + Recent**
- Summarize messages 1-50, keep last 10 in full
- Best for long conversations

**Option D - RAG + Semantic Search**
- Embed all messages
- Retrieve relevant past messages for current query

**Decision Rationale:**
- **Phase 1**: Option B (simplest to implement)
- **Phase 2**: Add Option C (after gathering user data)
- **Phase 3**: Add Option D (after proving value)

**Key Insight**: Start simple, add sophistication as you get real usage data

**Implementation:**
```python
MAX_CONTEXT_MESSAGES = 50  # Safety limit

async def get_context_for_agent(conversation_id: UUID):
    # Load recent messages
    messages = await db.messages.get_recent(conversation_id, limit=10)

    # If conversation is very long, add safety
    if len(messages) == 10:  # Hit limit, might be more
        total = await db.messages.count(conversation_id)
        if total > MAX_CONTEXT_MESSAGES:
            # Future: Trigger summarization
            logger.warning("Long conversation, consider summarization")

    return messages
```

---

### Question: Multi-User Trip - Separate or Shared Conversations?

**Scenario**: Alice and Bob both on Barcelona trip

**Options Considered:**

**Option A - Shared Conversation**
- Both users see same chat history
- Privacy concerns

**Option B - Separate Conversations** ✅ **CHOSEN**
- Each user has own conversation with agent
- Privacy preserved

**Option C - Separate + Shared Trip Context** ✅ **CHOSEN**
- Each user: private conversation
- Both agents: access to shared trip data
- Optional: Users can opt-in to share conversations

**Decision Rationale:**
- Privacy by default (critical for any production app)
- Users don't see each other's questions
- Agents still have full trip context (hotel, flights, etc.)
- **Opt-in sharing**: Advanced feature for Phase 1B

**Schema:**
```sql
conversations (
  id UUID,
  trip_id UUID,      -- Multiple conversations per trip
  user_id UUID,      -- One conversation per user per trip
  created_at TIMESTAMPTZ,
  UNIQUE(trip_id, user_id)
)

conversation_sharing (
  conversation_id UUID,
  user_id UUID,
  share_with_trip_members BOOLEAN DEFAULT FALSE,  -- Off by default
  shared_at TIMESTAMPTZ
)
```

**Agent Context Assembly:**
```python
async def get_context(conversation_id, trip_id, user_id):
    # Always get user's own messages
    my_messages = await db.messages.get(conversation_id)

    # Get shared trip data
    trip_data = await db.trips.get(trip_id)

    # Check if other users opted to share
    shared = await db.conversation_sharing.get_shared_for_trip(trip_id)

    context = f"""
    Your conversation with {user.name}:
    {my_messages}

    Trip details (shared):
    {trip_data.summary}

    {f"Other travelers discussed: {summarize(shared)}" if shared else ""}
    """
```

**Privacy Principle**: Off by default, users explicitly opt-in to share

---

### Question: How to Prevent Context Explosion (Cost Control)?

**Problem**: 1000-message conversation = 500K tokens = $1.50 per query

**Solution - Token Limit with Summarization**:
```python
MAX_CONTEXT_TOKENS = 25_000  # ~$0.075 input cost for Claude

async def prepare_context(conversation_id):
    messages = await db.messages.get_all(conversation_id)

    # Estimate tokens (rough: 1 token ≈ 4 chars)
    estimated_tokens = sum(len(m.content) / 4 for m in messages)

    if estimated_tokens > MAX_CONTEXT_TOKENS:
        # Summarize old messages
        old_messages = messages[:-25]  # Keep last 25 full
        summary = await summarize_messages(old_messages)

        context = f"""
        Previous conversation summary:
        {summary}

        Recent messages:
        {messages[-25:]}
        """
    else:
        context = messages

    return context
```

**Cost Control Principles:**
1. Limit context size (prevent runaway costs)
2. Summarize old messages (preserve info, reduce tokens)
3. Log warnings when approaching limits
4. Circuit breaker for single requests > $0.50

---

## Data Synchronization

### Question: What User Data to Sync from Frontend?

**Frontend → Backend Sync Events:**

**On User Account Created/Edited:**
```
POST /users/sync
{
  "user_id": "uuid",        // Supabase user ID
  "email": "alice@example.com",
  "phone": "+1-555-0100",
  "home_city": "San Francisco",
  "first_name": "Alice",
  "last_name": "Chen"
}
```

**On Trip Created/Edited:**
```
POST /trips/sync
{
  "trip_id": "uuid",        // Supabase trip ID
  "name": "Barcelona Summer",
  "destination": "Barcelona, Spain",
  "start_date": "2025-06-10",
  "end_date": "2025-06-20",
  "travelers": ["user_id_1", "user_id_2"],
  "created_by": "user_id_1"
}
```

**On Trip Deleted:**
```
DELETE /trips/{trip_id}
```

**Best Practice**: Frontend is source of truth, backend receives updates

---

### Question: How to Handle Sync Failures?

**Scenarios:**
- Frontend saves to Supabase, but backend sync fails (network error)
- Backend is down during trip creation

**Strategy - Idempotent Sync with Retry:**
```python
@router.post("/trips/sync")
async def sync_trip(trip: TripSyncRequest):
    # Upsert (insert or update)
    await db.trips.upsert(
        id=trip.trip_id,
        name=trip.name,
        destination=trip.destination,
        ...
    )
    # Idempotent: same request can be sent multiple times safely
    return {"status": "synced"}
```

**Frontend Implementation:**
```typescript
async function syncTripToBackend(trip: Trip) {
  const maxRetries = 3;

  for (let i = 0; i < maxRetries; i++) {
    try {
      await fetch('/trips/sync', { method: 'POST', body: JSON.stringify(trip) });
      return; // Success
    } catch (error) {
      if (i === maxRetries - 1) {
        // Log for manual recovery
        console.error('Failed to sync trip after retries', trip.id);
        // Queue for background sync?
      }
      await sleep(1000 * Math.pow(2, i)); // Exponential backoff
    }
  }
}
```

**Principle**: Design for eventual consistency, handle transient failures gracefully

---

## Email Integration & Extraction

### Question: How to Receive Emails from Users?

**Architecture - Gmail API with Pub/Sub:**

```
1. User forwards email to travelroboto@gmail.com
2. Gmail → Google Cloud Pub/Sub topic
3. Pub/Sub → POST /webhook/gmail (your backend)
4. Backend:
   - Receives historyId
   - Calls Gmail API to fetch full email (body + attachments)
   - Triggers Trip Coordinator agent
   - Stores extracted data
```

**MVP Strategy:**
- **Phase 1B**: Free Gmail account (manually renew OAuth tokens)
- **Phase 1C+**: Paid Google Workspace (professional email, better auth)

**Authentication**: Service Account (single travelroboto@gmail.com inbox)

---

### Question: How to Match Email to Trip/User?

**Problem**: Email arrives, which trip does it belong to?

**Strategy - Smart LLM Matching** ✅ **CHOSEN**
```python
async def match_email_to_trip(email: Email, user_id: UUID):
    # Extract destination and dates from email
    extraction = await coordinator.extract(email.body)
    # {destination: "Barcelona", dates: "June 10-20, 2025"}

    # Find matching trip
    trips = await db.trips.get_by_user(user_id)

    for trip in trips:
        if (trip.destination == extraction.destination and
            dates_overlap(trip.dates, extraction.dates)):
            return trip.id

    # No match: Create draft trip
    return await create_draft_trip(extraction, user_id)
```

**Principle**: Use LLM intelligence to reduce user friction (no manual tagging)

---

### Question: What Email Data to Store?

**Schema - Email Sources:**
```sql
CREATE TABLE email_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  gmail_message_id VARCHAR(100) UNIQUE,
  from_email VARCHAR(255),
  subject TEXT,
  received_at TIMESTAMPTZ,
  raw_body TEXT,              -- Full email text
  raw_html TEXT,              -- HTML version (for rendering)
  attachments JSONB,          -- [{filename, mime_type, size, gcs_url}]
  extraction_status VARCHAR(20),  -- 'pending' | 'processing' | 'completed' | 'failed'
  trip_id UUID,               -- NULL until matched
  created_at TIMESTAMPTZ,

  FOREIGN KEY (trip_id) REFERENCES trips(id)
);
```

**Rationale:**
- Store everything for re-processing (if extraction fails)
- Show source email to user for verification
- Audit trail for debugging

**Best Practice**: Never delete source data, even after extraction

---

### Question: How to Parse PDF Attachments?

**Strategies:**

**Phase 1C - Text-Based PDFs:**
```python
from PyPDF2 import PdfReader

async def extract_pdf(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join([page.extract_text() for page in reader.pages])
    return text
```

**Limitation**: Fails on scanned/image-based PDFs

**Phase 2+ - Multimodal LLM:**
```python
# For image-based PDFs (boarding passes, scanned docs)
async def extract_pdf_multimodal(pdf_bytes: bytes) -> dict:
    # Convert PDF to images
    images = pdf_to_images(pdf_bytes)

    # Send to Claude with vision
    response = await anthropic.messages.create(
        model="claude-3-5-sonnet-20241022",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "data": img_base64}},
                {"type": "text", "text": "Extract flight details from this boarding pass"}
            ]
        }]
    )

    return parse_extraction(response.content)
```

**Decision**: Start with PyPDF2 (simple), upgrade to multimodal if accuracy poor

**Trade-off**: Cost (multimodal more expensive) vs Accuracy (better for complex docs)

---

## Conflict Resolution Intelligence

### Question: How to Detect Conflicting Trip Data?

**Problem**: Existing DB says "Hilton Barcelona", new email says "Hotel W Barcelona"

**Strategy - Hybrid Detection:**

**Rule-Based (Fast, Cheap):**
```python
def detect_conflicts_rules(existing: TripData, new: TripData) -> list[Conflict]:
    conflicts = []

    if new.hotel_name != existing.hotel_name:
        conflicts.append(Conflict(
            field="hotel_name",
            old=existing.hotel_name,
            new=new.hotel_name,
            severity="high"
        ))

    if new.check_out != existing.check_out:
        conflicts.append(Conflict(
            field="check_out",
            old=existing.check_out,
            new=new.check_out,
            severity="high"
        ))

    return conflicts
```

**LLM-Based (Smart, Expensive):**
```python
async def detect_conflicts_llm(existing, new) -> ConflictDecision:
    prompt = f"""
    Existing trip data:
    {json.dumps(existing)}

    New email extraction:
    {json.dumps(new)}

    Are these conflicting or complementary?

    Examples:
    - Conflicting: Different hotels for same dates
    - Complementary: Same hotel, new confirmation number (re-booking)
    - Complementary: "Hilton Barcelona" vs "Hilton Barcelona Downtown" (same hotel)

    Respond JSON: {{"conflict": true/false, "reason": "...", "confidence": 0.0-1.0}}
    """

    response = await llm.generate(prompt)
    return parse_decision(response)
```

**Combined Strategy:**
1. Run rule-based detection first (instant, free)
2. If ambiguous, use LLM (e.g., hotel name variations)
3. If confidence < 0.9, send confirmation email to user

**Principle**: Use rules for obvious cases, LLM for nuanced decisions

---

### Question: How to Get User Confirmation?

**Email Confirmation Flow:**

**Phase 1C - Email Reply (Human-Like):**
```
Subject: 🤖 Travel Roboto: Please confirm your Barcelona trip update

Hi Alice,

I processed your hotel confirmation email and noticed some changes:

📧 Source: "Booking.com Confirmation" (received Jan 16, 2025)

Changes detected:
❓ Hotel changed: Hilton Barcelona → Hotel W Barcelona
❓ Check-out extended: June 15 → June 20

Please reply to this email with one of:
- "Yes, update my trip"
- "No, keep original"
- "Actually, [your explanation]..."

I'll process your response and update accordingly.

---
Current trip: Barcelona, June 10-20
View details: https://travelroboto.com/trips/abc123
```

**Why Email Reply vs Buttons:**
- ✅ Traceability (email thread shows full history)
- ✅ Prevents accidental clicks
- ✅ Allows nuanced responses ("Actually, I booked both hotels...")
- ❌ Requires NLP to parse reply (but we have LLMs!)

**Implementation:**
```python
# Backend receives reply via Gmail webhook
async def process_confirmation_reply(email: Email):
    # Extract intent from user's reply
    intent = await llm.classify_intent(email.body)
    # intent: "accept" | "reject" | "clarify"

    if intent == "accept":
        await apply_changes(email.thread_id)
    elif intent == "reject":
        await discard_changes(email.thread_id)
    else:
        # User provided clarification, re-extract
        await coordinator.extract_with_context(email.body)
```

**Future Enhancement - Predictive Confirmation:**
```
Subject: I updated your trip - please verify

Hi Alice,

I'm 85% confident your hotel changed based on this email.
I've updated your trip to Hotel W Barcelona.

If this is wrong, just reply and I'll fix it!
```
- Agent makes prediction
- Sends confirmation after the fact
- Learns from corrections over time

**Principle**: Start conservative (ask first), move to predictive (confirm after)

---

## Privacy & Multi-Tenancy

### Question: How to Prevent Data Leakage Between Users?

**Critical Scenarios:**

**Scenario A - Same Trip, Different Users:**
```
Alice and Bob both on "Barcelona Trip"
Alice asks: "What hotel are we staying at?"
Bob asks same question

Should Bob's agent see Alice's messages? NO
Should both agents see hotel data? YES
```

**Strategy - Database-Level Isolation:**
```python
async def get_messages_for_context(
    conversation_id: UUID,
    user_id: UUID  # Verify ownership!
) -> list[Message]:
    # Verify user owns this conversation
    conv = await db.conversations.get(conversation_id)
    if conv.user_id != user_id:
        raise PermissionError(f"User {user_id} does not own conversation {conversation_id}")

    # Only return messages from THIS conversation
    return await db.messages.get_recent(conversation_id, limit=10)
```

**Agent Prompt Isolation:**
```
You are assisting {user_name} with their {trip_name} trip.

Trip details (shared with all travelers):
{trip.destination}, {trip.dates}
Hotel: {trip.hotel_name}
Flight: {trip.flight_info}

Your conversation with {user_name} (PRIVATE):
{messages_for_this_user_only}

Answer based on trip details and THIS user's conversation only.
DO NOT reference other travelers' conversations.
```

**Testing for Leakage:**
```python
# Security test
async def test_conversation_isolation():
    # Alice and Bob on same trip
    alice_conv_id = await create_conversation(trip_id, alice_id)
    bob_conv_id = await create_conversation(trip_id, bob_id)

    # Alice asks about hotel
    await send_message(alice_conv_id, alice_id, "Where am I staying?")

    # Bob should NOT see Alice's message
    bob_context = await get_messages_for_context(bob_conv_id, bob_id)
    assert "Where am I staying?" not in str(bob_context)
```

**Principle**: Privacy by design, verify at database layer, reinforce in prompts

---

### Question: Should Users Be Able to Share Conversations?

**Feature - Opt-In Conversation Sharing:**

**Default Behavior**: Conversations are private

**Opt-In**: User enables sharing in settings
```sql
CREATE TABLE conversation_sharing (
  conversation_id UUID,
  user_id UUID,
  share_with_trip_members BOOLEAN DEFAULT FALSE,  -- OFF by default
  shared_at TIMESTAMPTZ,
  PRIMARY KEY (conversation_id, user_id)
);
```

**UI Flow:**
```
[Chat Settings]
☐ Share my conversation with other travelers on this trip
   ⚠️ This will let Alice and Bob see your questions and answers
```

**Agent Behavior When Enabled:**
```python
async def get_context(conversation_id, trip_id, user_id):
    # Always get user's own messages
    my_messages = await db.messages.get(conversation_id)

    # Check if other users opted to share
    shared_convs = await db.conversation_sharing.get_shared_for_trip(trip_id)

    context = my_messages

    if shared_convs:
        # Summarize shared conversations
        summary = await summarize_conversations(shared_convs)
        context += f"\n\nOther travelers have discussed:\n{summary}"

    return context
```

**Privacy Principles:**
- Off by default (privacy-first)
- Explicit opt-in required
- Show clear warning about implications
- **Phase 1B scope** (easy to implement, high value for collaboration)

---

## Observability & Debugging

### Question: How to Debug "Agent Gave Wrong Answer"?

**Problem**: User asks "What hotel?", agent says "I don't know", but hotel IS in DB

**Solution - Comprehensive Request Tracing:**

**Structured Logging:**
```python
import structlog

logger = structlog.get_logger()

# At request start
logger.info(
    "agent_turn_start",
    conversation_id=conv_id,
    user_id=user_id,
    user_message=message,
    trip_id=trip_id
)

# Loading context
logger.info(
    "context_loaded",
    conversation_id=conv_id,
    num_messages=len(history),
    num_tokens_estimated=estimate_tokens(history),
    trip_summary=trip.summary
)

# Building prompt
logger.info(
    "prompt_built",
    conversation_id=conv_id,
    prompt_length=len(prompt),
    model=model_name,
    tools_available=[t.name for t in tools]
)

# LLM request
logger.info(
    "llm_request_sent",
    conversation_id=conv_id,
    model=model_name,
    input_tokens=estimated_tokens
)

# Tool call
logger.info(
    "tool_execution",
    conversation_id=conv_id,
    tool_name="get_trip_details",
    tool_input={"trip_id": trip_id},
    tool_output=result,
    execution_time_ms=elapsed
)

# LLM response
logger.info(
    "llm_response_received",
    conversation_id=conv_id,
    model=model_name,
    input_tokens=response.usage.input_tokens,
    output_tokens=response.usage.output_tokens,
    cost_usd=calculate_cost(response.usage),
    latency_ms=elapsed,
    finish_reason=response.stop_reason
)

# Final response
logger.info(
    "agent_turn_complete",
    conversation_id=conv_id,
    response_length=len(response.content),
    total_time_ms=total_elapsed
)
```

**Trace Viewer (Logs):**
```
[2025-01-16 10:23:01] agent_turn_start conversation_id=abc-123 user_message="What hotel?"
[2025-01-16 10:23:01] context_loaded num_messages=10 trip_id=xyz-789
[2025-01-16 10:23:01] prompt_built model=claude-3-5-sonnet tools_available=['get_trip_details']
[2025-01-16 10:23:02] llm_request_sent input_tokens=1500
[2025-01-16 10:23:03] tool_execution tool=get_trip_details output={hotel: "Hilton"} time_ms=45
[2025-01-16 10:23:05] llm_response_received output_tokens=150 cost_usd=0.0023 latency_ms=2100
[2025-01-16 10:23:05] agent_turn_complete total_time_ms=4200
```

**Debugging Workflow:**
1. Find failed request in logs by conversation_id
2. See exact prompt sent to LLM
3. See tool calls and results
4. See final response
5. **Replay request** with same inputs to test fix

---

### Question: Should We Store Full Prompts in DB?

**Options:**

**Option A - Log Files Only**
- Structured logs go to stdout → Cloud logging service
- Searchable, but ephemeral

**Option B - Database Storage** ✅ **RECOMMENDED**
```sql
CREATE TABLE llm_requests (
  id UUID PRIMARY KEY,
  conversation_id UUID,
  message_id UUID,           -- Which message triggered this
  model_provider VARCHAR(50),
  model_name VARCHAR(100),
  full_prompt TEXT,          -- Exact prompt sent
  full_response TEXT,        -- Exact response received
  tool_calls JSONB,
  usage JSONB,               -- {input_tokens, output_tokens, cost_usd}
  latency_ms INT,
  created_at TIMESTAMPTZ
);
```

**Benefits:**
- Replay exact request for debugging
- Analyze prompt evolution over time
- Detect prompt injection attempts
- Train eval models on real data

**Trade-offs:**
- ✅ Invaluable for debugging
- ✅ Shows MLOps maturity
- ❌ Storage cost (mitigated by retention policy: keep 90 days)

**Principle**: In AI systems, observability is not optional

---

### Question: What Metrics to Track?

**Per-Request Metrics:**
- Model used (claude-3-5-sonnet, gpt-4o)
- Prompt version (v1, v2)
- Tokens (input, output)
- Cost (USD)
- Latency (ms)
- Tool calls (which tools, how many)
- Finish reason (stop, length, tool_use)

**Aggregate Metrics (Dashboard):**
- Requests per hour/day
- Average latency by model
- Total cost per day/week
- Tool usage frequency
- Error rate (by error type)
- User engagement (messages per user)

**Database Schema:**
```sql
CREATE TABLE metrics (
  id UUID PRIMARY KEY,
  metric_name VARCHAR(100),
  metric_value FLOAT,
  dimensions JSONB,          -- {model: "claude", user_id: "..."}
  timestamp TIMESTAMPTZ
);

-- Example rows:
-- {name: "request_latency_ms", value: 2100, dimensions: {model: "claude"}}
-- {name: "request_cost_usd", value: 0.0023, dimensions: {user_id: "alice"}}
-- {name: "tool_calls", value: 1, dimensions: {tool_name: "get_trip_details"}}
```

**Principle**: Measure everything, optimize what matters

---

## Cost Management

### Question: How to Prevent Runaway API Costs?

**Cost Scenarios to Prevent:**

**Scenario A - Spam Attack:**
- User sends 100 messages in 1 minute
- 100 × $0.02 = $2.00 in 60 seconds

**Scenario B - Context Explosion:**
- 1000-message conversation
- 500K tokens input per request
- Single query = $1.50

**Scenario C - Tool Loop:**
- Agent hallucinates, calls same tool 20 times
- Request times out after 30 seconds
- Wasted $ on failed request

---

**Strategy - Multi-Layer Safety Rails:**

**1. Rate Limiting:**
```python
RATE_LIMITS = {
    "messages_per_minute": 10,
    "messages_per_hour": 100,
    "messages_per_day": 500
}

@rate_limit(limit=10, window="1m")
async def handle_chat(request: ChatRequest):
    ...
```

**2. Context Size Limits:**
```python
MAX_CONTEXT_MESSAGES = 50
MAX_CONTEXT_TOKENS = 25_000  # ~$0.075 input cost

async def prepare_context(conversation_id):
    messages = await db.messages.get_all(conversation_id)

    if len(messages) > MAX_CONTEXT_MESSAGES:
        # Summarize old messages
        old = messages[:-25]
        summary = await summarize(old)
        context = summary + messages[-25:]
    else:
        context = messages

    return context
```

**3. Tool Call Limits:**
```python
MAX_TOOL_CALLS_PER_TURN = 5

async def execute_agent_turn(message):
    tool_calls = []

    while True:
        response = await agent.generate(message)

        if response.tool_calls:
            tool_calls.extend(response.tool_calls)

            if len(tool_calls) > MAX_TOOL_CALLS_PER_TURN:
                raise ToolLoopError("Agent called too many tools, possible loop")

            # Execute tools and continue
            results = await execute_tools(response.tool_calls)
            message = format_tool_results(results)
        else:
            # Agent finished
            return response
```

**4. Single-Request Circuit Breaker:**
```python
MAX_SINGLE_REQUEST_COST = 0.50  # 50 cents

async def call_llm(prompt, model):
    # Estimate cost before sending
    estimated_tokens = count_tokens(prompt)
    estimated_cost = calculate_cost(estimated_tokens, model)

    if estimated_cost > MAX_SINGLE_REQUEST_COST:
        logger.error("High cost request blocked", estimated_cost=estimated_cost)
        raise CostLimitError("This request would be too expensive. Please simplify.")

    # Proceed with request
    response = await llm.generate(prompt, model)
    return response
```

**5. Daily Budget (Soft Limit):**
```python
DAILY_BUDGET_WARNING = 5.00  # $5/day soft cap

async def check_budget(user_id):
    spend_today = await db.get_daily_spend(user_id)

    if spend_today > DAILY_BUDGET_WARNING:
        logger.warning("User over daily budget", user_id=user_id, spend=spend_today)
        # Still process (don't block users)
        # But alert for monitoring

    return spend_today
```

**Principle**: Soft limits + monitoring for portfolio, hard limits for production

---

### Question: How to Calculate and Display Costs?

**Implementation - Real-Time Cost Tracking:**

```python
# Pricing (as of Jan 2025)
PRICING = {
    "claude-3-5-sonnet-20241022": {
        "input": 3.00 / 1_000_000,   # $3 per 1M tokens
        "output": 15.00 / 1_000_000   # $15 per 1M tokens
    },
    "gpt-4o": {
        "input": 2.50 / 1_000_000,
        "output": 10.00 / 1_000_000
    }
}

def calculate_cost(usage: LLMUsage, model: str) -> float:
    pricing = PRICING[model]
    cost = (
        usage.input_tokens * pricing["input"] +
        usage.output_tokens * pricing["output"]
    )
    return cost

# After LLM call
response = await claude.chat(...)
cost = calculate_cost(response.usage, "claude-3-5-sonnet-20241022")

# Save to DB
await db.messages.update(
    message_id,
    tokens_input=response.usage.input_tokens,
    tokens_output=response.usage.output_tokens,
    cost_usd=cost
)

# Return to frontend
return ChatResponse(
    content=response.content,
    cost_usd=cost  # Frontend can display: "This cost $0.0023"
)
```

**Frontend Display:**
```typescript
// After user sends message
const response = await fetch('/chat', {...});
const data = await response.json();

// Show cost
console.log(`This response cost: $${data.cost_usd.toFixed(4)}`);

// Update daily total
dailySpend += data.cost_usd;
if (dailySpend > 0.50) {
  showWarning("You've used $0.50 today. Consider slowing down!");
}
```

**Principle**: Transparency builds trust, cost awareness prevents abuse

---

## Testing Strategy

### Question: How to Test Non-Deterministic Agents?

**Challenge**: LLM responses vary, hard to write assertions

**Solution - Three-Layer Testing:**

---

**Layer 1 - Unit Tests (Deterministic):**

Test tools and utilities in isolation

```python
def test_get_trip_details():
    # Create test data
    trip = Trip(
        id=uuid4(),
        name="Barcelona Summer",
        destination="Barcelona, Spain",
        start_date=date(2025, 6, 10),
        end_date=date(2025, 6, 20)
    )
    db.trips.create(trip)

    # Test tool
    result = get_trip_details(trip.id)

    # Deterministic assertions
    assert result.trip_name == "Barcelona Summer"
    assert result.destination == "Barcelona, Spain"
    assert "June 10" in result.dates
```

**What to test:**
- Tool execution (get_trip_details, extract_trip_data)
- Database operations (CRUD)
- Utility functions (token counting, cost calculation)
- Sync endpoints (POST /users/sync)

---

**Layer 2 - Integration Tests (Mock LLM):**

Test agent flow with mocked responses

```python
@pytest.fixture
def mock_anthropic():
    with patch('anthropic.Anthropic') as mock:
        mock.return_value.messages.create.return_value = MockResponse(
            content="You're staying at the Hilton Barcelona",
            tool_calls=[],
            usage=Usage(input_tokens=100, output_tokens=20)
        )
        yield mock

async def test_concierge_answers_hotel_question(mock_anthropic):
    # Setup: Create trip with hotel
    trip = await create_test_trip(hotel_name="Hilton Barcelona")
    conv = await create_conversation(trip.id, user.id)

    # Execute: User asks about hotel
    response = await concierge.chat(
        message="Where am I staying?",
        conversation_id=conv.id
    )

    # Assert: Response contains hotel name
    assert "Hilton" in response.content
    assert response.cost_usd > 0

    # Verify LLM was called correctly
    mock_anthropic.messages.create.assert_called_once()
    call_args = mock_anthropic.messages.create.call_args
    assert "Hilton Barcelona" in str(call_args)  # Hotel in context
```

**What to test:**
- Agent flow (context loading → LLM call → response)
- Tool calling logic (agent decides to call tool)
- Error handling (LLM timeout, tool failure)
- Cost calculation
- Message saving to DB

---

**Layer 3 - LLM-as-Judge (Real LLM):**

Evaluate quality of real agent responses

```python
# Test cases (golden dataset)
TEST_CASES = [
    {
        "name": "hotel_question",
        "trip_context": {
            "hotel_name": "Hilton Barcelona",
            "check_in": "June 10",
            "address": "123 Main St"
        },
        "user_message": "What hotel am I staying at?",
        "expected_contains": ["Hilton", "Barcelona"],
        "expected_cites_source": True,
        "min_quality_score": 0.8
    },
    {
        "name": "missing_data",
        "trip_context": {},  # No hotel info
        "user_message": "What hotel am I staying at?",
        "expected_contains": ["don't have", "information"],
        "expected_asks_clarification": True,
        "min_quality_score": 0.7
    }
]

async def test_agent_quality():
    for case in TEST_CASES:
        # Setup test trip
        trip = await create_trip_from_context(case["trip_context"])

        # Run real agent
        response = await concierge.chat(
            message=case["user_message"],
            trip_id=trip.id
        )

        # Judge response quality
        judge_prompt = f"""
        Evaluate this travel assistant's response:

        User asked: "{case['user_message']}"
        Agent responded: "{response.content}"

        Criteria:
        - Contains expected info: {case['expected_contains']}
        - Cites source: {case.get('expected_cites_source', False)}
        - Helpful and accurate

        Score 0.0-1.0: {{"score": X.X, "reasoning": "..."}}
        """

        judge_response = await judge_llm.evaluate(judge_prompt)
        score = parse_score(judge_response)

        # Assert quality threshold
        assert score >= case["min_quality_score"], \
            f"Quality too low: {score} < {case['min_quality_score']}\n{judge_response}"
```

**What to test:**
- Response accuracy (correct info extracted from context)
- Helpfulness (asks clarifying questions when data missing)
- Citation quality (references sources)
- Tone and professionalism
- Edge cases (ambiguous questions, missing data)

**When to run:**
- Unit tests: Every commit (fast, deterministic)
- Integration tests: Every PR (catch regressions)
- LLM-as-judge: Weekly or before releases (expensive, comprehensive)

---

**Principle**: Test at multiple levels, balance speed vs comprehensiveness

---

## Deployment & Environment

### Question: How to Manage Secrets and Configuration?

**Development:**
```bash
# Local .env file
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
DATABASE_URL=postgresql://localhost/travelroboto
GMAIL_CREDENTIALS_PATH=./secrets/gmail-service-account.json
```

**Production (Railway):**
- Environment variables via Railway dashboard
- Database auto-provisioned (managed PostgreSQL)
- Secrets encrypted at rest

**Best Practices:**
1. Never commit secrets to git (.env in .gitignore)
2. Use different API keys for dev/prod
3. Rotate keys periodically
4. Log when secrets are accessed (audit trail)

---

### Question: How to Handle Database Migrations?

**Alembic Strategy:**

```bash
# Local development
alembic revision --autogenerate -m "add email_sources table"
alembic upgrade head

# Production (Railway)
# Add to Procfile or railway.json:
{
  "build": {
    "nixpacks": {
      "plan": {"providers": ["python@3.11"]}
    }
  },
  "deploy": {
    "startCommand": "alembic upgrade head && uvicorn main:create_app --factory --host 0.0.0.0 --port ${PORT}"
  }
}
```

**Migration Safety:**
- Test migrations on local DB first
- Use transactions (Alembic default)
- Have rollback plan (alembic downgrade -1)
- Never drop columns without backup

---

### Question: Staging Environment?

**For MVP:**
- Single production environment (keep it simple)
- Test locally before deploying

**Future (if needed):**
- Staging environment on Railway
- Use cheaper models (claude-3-haiku) to save costs
- Test Gmail webhooks before production

**Principle**: Don't over-engineer infrastructure for portfolio project

---

## Phased Roadmap

### Phase 1 - Basic Chat (Week 1)
**Goal**: User can chat with Travel Concierge about their trip

**Features:**
- ✅ POST /chat endpoint
- ✅ Travel Concierge agent (Claude only)
- ✅ Load last 10 messages for context
- ✅ Simple tool: get_trip_details(trip_id)
- ✅ Save messages to PostgreSQL
- ✅ Log: model, tokens, latency, cost
- ✅ POST /users/sync, POST /trips/sync endpoints

**Schema:**
- users, trips, conversations, messages tables

**Acceptance Criteria:**
- User sends "What hotel am I staying at?" → Agent responds with hotel name
- Cost tracked and returned in response
- All requests logged with structured logging

**Demo:**
```
curl -X POST /chat -d '{
  "conversation_id": "uuid",
  "user_id": "uuid",
  "trip_id": "uuid",
  "message": "What hotel am I staying at?"
}'

Response:
{
  "message_id": "uuid",
  "content": "You're staying at the Hilton Barcelona, checking in June 10.",
  "model_used": "claude-3-5-sonnet",
  "cost_usd": 0.0023,
  "latency_ms": 2100
}
```

---

### Phase 1B - Trip Coordinator + Email Extraction (Week 2)
**Goal**: System can extract trip data from forwarded emails

**Features:**
- ✅ POST /webhook/gmail endpoint
- ✅ Gmail API integration (fetch email body + attachments)
- ✅ Trip Coordinator agent (extraction specialist)
- ✅ Match email to trip (smart LLM-based matching)
- ✅ Tool: extract_trip_data(email_text)
- ✅ Store: email_sources table
- ✅ Privacy: conversation_sharing table (opt-in)
- ✅ Add OpenAI provider (multi-model foundation)

**Schema:**
- email_sources, conversation_sharing

**Acceptance Criteria:**
- User forwards hotel confirmation → Trip Coordinator extracts hotel, dates, address
- Extracted data saved to trips.structured_data (JSONB)
- Email stored with extraction_status = 'completed'
- User can opt-in to share conversation with trip members

**Demo:**
```
# Simulate Gmail webhook
curl -X POST /webhook/gmail -d '{
  "gmail_message_id": "abc123"
}'

# Backend:
# 1. Fetches email via Gmail API
# 2. Coordinator extracts: {hotel: "Hilton Barcelona", check_in: "2025-06-10"}
# 3. Matches to existing trip (or creates draft)
# 4. Saves to trips.structured_data

# User later asks:
POST /chat {"message": "Where am I staying?"}
→ "You're staying at Hilton Barcelona (from your Booking.com email)"
```

---

### Phase 1C - Conflict Resolution + PDF Parsing + Confirmation Emails (Week 3)
**Goal**: Handle conflicting data and parse PDF attachments

**Features:**
- ✅ Conflict detection (hybrid: rules + LLM)
- ✅ Confirmation emails to users (reply-based validation)
- ✅ PDF parsing (PyPDF2 for text-based PDFs)
- ✅ Trip field versioning (track changes over time)
- ✅ Tool: detect_conflicts(existing, new)
- ✅ Tool: send_confirmation_email(user, changes)

**Schema:**
- trip_field_versions (audit trail)

**Acceptance Criteria:**
- Coordinator detects conflicting hotel names → Sends confirmation email
- User replies "Yes, update" → System applies changes
- User replies "No, keep original" → System discards new data
- PDF boarding pass → Text extracted → Flight details saved

**Demo:**
```
# Existing trip: hotel = "Hilton Barcelona"
# New email: hotel = "Hotel W Barcelona"

# Coordinator detects conflict:
Conflict(field="hotel_name", old="Hilton", new="Hotel W", confidence=0.95)

# Sends email:
Subject: Please confirm your Barcelona trip update
Body: Hotel changed: Hilton → Hotel W. Reply to confirm.

# User replies: "Yes, update my trip"

# Backend processes reply:
- Parses intent: "accept"
- Updates trip.hotel_name = "Hotel W"
- Saves version history
- Logs: {old: "Hilton", new: "Hotel W", confirmed_by: user, at: timestamp}
```

---

### Phase 2 - Multi-Model + A/B Testing + Agent Routing (Week 4)
**Goal**: Compare models and route to specialized agents

**Features:**
- ✅ Model factory (abstract Claude vs OpenAI)
- ✅ A/B testing (conversation-level assignment)
- ✅ Prompt versioning (agents/prompts/v1, v2, active.json)
- ✅ Agent router (LLM-based intent classification)
- ✅ Sub-agent stubs (restaurant_expert, flight_checker - basic implementations)

**Schema:**
- ab_test_assignments (conversation_id → model variant)

**Acceptance Criteria:**
- 50% of conversations use Claude, 50% use GPT-4o
- Prompt version tracked per request
- Agent router classifies intent and routes to appropriate agent
- All requests logged with model + prompt version

**Demo:**
```
# Conversation A assigned to Claude
POST /chat {"message": "Where am I staying?"}
→ Uses claude-3-5-sonnet, prompt v1

# Conversation B assigned to GPT-4o
POST /chat {"message": "Where am I staying?"}
→ Uses gpt-4o, prompt v1

# Later: Compare metrics
SELECT model, AVG(latency_ms), AVG(cost_usd), AVG(user_feedback)
FROM messages
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY model;

# Router test:
POST /chat {"message": "Recommend a restaurant near my hotel"}
→ Router detects "restaurant" intent → Routes to restaurant_expert
```

---

### Phase 3 - Advanced Features (Week 5+)
**Goal**: RAG, summarization, LLM-as-judge evaluation

**Features:**
- ✅ Conversation summarization (for long threads)
- ✅ RAG: Embed messages, semantic search
- ✅ LLM-as-judge evaluation framework
- ✅ Specialized sub-agents (restaurant_expert with Yelp API, flight_checker with live data)
- ✅ Multi-modal LLM for image-based PDFs

**Schema:**
- message_embeddings (vector search)
- evaluation_results (LLM-as-judge scores)

**Acceptance Criteria:**
- Conversations > 50 messages → Auto-summarize old messages
- User asks about "that restaurant we discussed" → RAG finds relevant past message
- Weekly eval suite runs on golden test cases → Track quality scores over time
- Restaurant agent calls Yelp API → Returns recommendations near hotel

**Demo:**
```
# Long conversation (100 messages)
POST /chat {"message": "What was that restaurant Alice mentioned?"}

# Backend:
# 1. Embed query: [0.123, 0.456, ...]
# 2. Search message_embeddings for similar vectors
# 3. Find: "Alice: Try La Paradeta, great seafood!" (from message 23)
# 4. Agent responds: "Alice recommended La Paradeta for seafood"

# LLM-as-judge eval:
python scripts/run_eval.py
→ Runs 50 test cases
→ Average quality score: 0.87 (up from 0.82 last week!)
→ Saves results to evaluation_results table
```

---

## Key Principles Summary

### Architecture Principles
1. **Dual database strategy**: Frontend (Supabase) for UI, Backend (PostgreSQL) for AI
2. **Backend is source of truth**: For AI context, conversation history, extractions
3. **Idempotent sync**: Frontend can retry syncs safely
4. **Privacy by design**: Conversations private by default, opt-in sharing

### Agent Principles
1. **Start independent, evolve to orchestrated**: Phase 1 (2 agents, no coordination) → Phase 3 (orchestrator)
2. **Agent routing early**: Build framework in Phase 1, add specialists later
3. **Domain knowledge in prompts initially**: Migrate to RAG as you gather data
4. **Agents are unreliable**: Backend enforces validation, not agents

### Tool Principles
1. **Pydantic models for tools**: Type-safe, auto-generate LLM schemas
2. **System-initiated over user-initiated**: Automation (email webhook) > manual triggers
3. **Business logic in tools**: Validate at backend layer, not in agent prompts

### Context Principles
1. **Start simple (last N turns)**: Add summarization and RAG after proving value
2. **Token limits prevent cost explosion**: Cap context at 25K tokens
3. **Privacy isolation**: Database-level checks, reinforced in prompts

### Data Principles
1. **Hybrid trip data model**: JSONB for flexibility, structured for querying
2. **Store everything**: Email sources, full prompts, tool calls (for debugging)
3. **Version history**: Track changes over time (trip_field_versions)

### Cost Principles
1. **Multi-layer safety rails**: Rate limits + context caps + tool limits + circuit breakers
2. **Soft limits for portfolio**: Monitor but don't block (collect data)
3. **Transparency**: Return cost to frontend, track daily spend

### Observability Principles
1. **Structured logging from day 1**: Every request traced with metadata
2. **Store full prompts**: Invaluable for debugging, enable request replay
3. **Measure everything**: Latency, tokens, cost, tool calls, user feedback

### Testing Principles
1. **Three-layer testing**: Unit (tools), integration (agent flow), LLM-as-judge (quality)
2. **Mock for speed**: Integration tests with mocked LLM
3. **Real LLMs for quality**: Weekly eval suite on golden dataset

### Privacy Principles
1. **Off by default**: Sharing, data collection - require explicit opt-in
2. **Database-level isolation**: Verify user owns resource before loading
3. **Prompt reinforcement**: Remind agent of privacy boundaries

### Deployment Principles
1. **Keep it simple for MVP**: Single production environment, Railway managed DB
2. **Automate migrations**: Alembic upgrade on deploy
3. **Secrets in environment**: Never commit to git, use platform secrets management

---

## Questions to Ask Stakeholders (Template)

When architecting an AI application, ask these questions:

### Product & Business
1. What's the primary goal? (Portfolio, production app, research experiment)
2. Who are the users? (Privacy sensitivity, cost tolerance)
3. What's the success metric? (Engagement, accuracy, cost efficiency)
4. What's the timeline? (MVP in 2 weeks vs polish over 3 months)

### Data & Privacy
1. How sensitive is user data? (Healthcare, finance, personal travel)
2. Should conversations be shareable? (Default private or public)
3. How long to retain data? (GDPR considerations)
4. What data sources? (User input, emails, APIs, web scraping)

### Agent Design
1. Single agent or multi-agent? (Complexity vs capabilities)
2. Should agents collaborate? (Independent vs orchestrated)
3. How much domain knowledge? (Prompt vs RAG vs external APIs)
4. What tools do agents need? (Read-only vs state-changing)

### Context Management
1. How much conversation history? (Last N, summarized, RAG)
2. What's the expected conversation length? (Single query, ongoing threads)
3. Multi-user scenarios? (Shared context, privacy isolation)
4. How to handle long contexts? (Summarization, truncation, cost limits)

### Model Strategy
1. Which LLM providers? (Cost, latency, capabilities)
2. A/B testing needed? (Compare models, prompts)
3. Fallback strategy? (Primary fails, switch to backup)
4. Cost budget? (Per-user, per-day limits)

### Observability
1. How to debug failures? (Logging, tracing, replay)
2. What metrics matter? (Latency, cost, quality, user satisfaction)
3. How to measure quality? (LLM-as-judge, user feedback, golden dataset)
4. Retention for logs/data? (Storage costs, compliance)

### Integration
1. External APIs needed? (Gmail, Yelp, flight data)
2. Webhook triggers? (Email, calendar, notifications)
3. Authentication? (OAuth, service accounts, API keys)

### Cost & Safety
1. What's abuse risk? (Spam, malicious users, cost attacks)
2. Rate limits needed? (Soft warnings, hard blocks)
3. How to prevent cost explosions? (Context caps, tool limits, circuit breakers)
4. Budget for API costs? (Daily, monthly)

### Testing
1. How to ensure quality? (Unit, integration, end-to-end)
2. Non-deterministic behavior? (LLM-as-judge, golden datasets)
3. Regression detection? (Track quality over time)

### Deployment
1. Where will this run? (Cloud provider, region, compliance)
2. Staging environment? (Test before production)
3. Secrets management? (Environment vars, secret managers)
4. Database migrations? (Automated, manual review)

---

## Recommended Reading / Study Topics

### AI Engineering Fundamentals
- **Prompt Engineering**: Chain-of-thought, few-shot, system prompts
- **Function Calling**: Tool use, JSON schemas, error handling
- **Context Windows**: Token limits, summarization strategies
- **RAG (Retrieval-Augmented Generation)**: Vector embeddings, semantic search
- **Agent Orchestration**: ReAct pattern, multi-agent systems

### LLM Providers
- **Anthropic Claude**: Function calling, prompt caching, extended context
- **OpenAI GPT-4**: Function calling, JSON mode, vision capabilities
- **Model Comparison**: Cost, latency, quality trade-offs

### Software Engineering
- **FastAPI**: Async routes, dependency injection, lifespan events
- **Pydantic**: Data validation, schema generation
- **PostgreSQL**: JSONB, full-text search, transactions
- **Alembic**: Database migrations, version control

### MLOps / LLMOps
- **Structured Logging**: JSON logs, request tracing, correlation IDs
- **Observability**: Metrics, dashboards, alerting
- **A/B Testing**: Variant assignment, statistical significance
- **LLM-as-Judge**: Evaluation frameworks, golden datasets

### Security & Privacy
- **Data Isolation**: Multi-tenancy, row-level security
- **Secrets Management**: Environment variables, secret rotation
- **Rate Limiting**: Token buckets, sliding windows
- **Cost Controls**: Circuit breakers, budget alerts

### System Design
- **Event-Driven Architecture**: Webhooks, pub/sub, async processing
- **Idempotency**: Safe retries, duplicate detection
- **Error Handling**: Retries, exponential backoff, fallbacks
- **API Design**: REST patterns, versioning, pagination

---

## Final Thoughts

This architecture discussion covers the **end-to-end decision-making process** for building a production-grade AI application. The key themes:

1. **Start Simple, Iterate**: Phase 1 is MVP, Phases 2-3 add sophistication based on learnings
2. **Observability First**: Can't improve what you don't measure
3. **Cost Awareness**: AI apps can get expensive fast, build safety rails early
4. **Privacy by Design**: Easier to add sharing than to fix data leaks
5. **Show, Don't Tell**: For recruiters, working code > documentation

**Portfolio Strategy**: This project demonstrates:
- ✅ Agent orchestration (multi-agent, routing)
- ✅ Tool design (function calling, validation)
- ✅ Context management (conversation memory, summarization)
- ✅ Multi-model abstraction (provider-agnostic)
- ✅ Observability (structured logging, cost tracking)
- ✅ A/B testing (model comparison)
- ✅ Email integration (Gmail API, webhooks)
- ✅ Conflict resolution (LLM-based intelligence)
- ✅ Privacy engineering (data isolation, opt-in sharing)

Use this document as a **study guide** to understand the reasoning behind each decision. When interviewing, you can explain:
- The problem
- Options considered
- Trade-offs
- Why you chose this approach
- What you'd do differently at scale

Good luck building! 🚀
