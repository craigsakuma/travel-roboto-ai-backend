# Travel Roboto - Technical Implementation Plan

**Version**: 1.0
**Date**: January 16, 2025
**Status**: Phase 1 - Ready to Implement

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Database Schema](#database-schema)
3. [API Specification](#api-specification)
4. [Agent Design](#agent-design)
5. [Tool Registry](#tool-registry)
6. [Observability](#observability)
7. [Implementation Roadmap](#implementation-roadmap)

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (Next.js)                       │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Auth UI    │  │   Chat UI    │  │  Trip UI     │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                  │                  │              │
│         └──────────────────┴──────────────────┘              │
│                            │                                 │
│                    ┌───────▼────────┐                       │
│                    │   Supabase     │                       │
│                    │  (Auth + UI)   │                       │
│                    └────────────────┘                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ POST /chat
                           │ POST /users/sync
                           │ POST /trips/sync
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                  BACKEND (FastAPI)                          │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                    API Layer                           │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │ │
│  │  │ /chat    │  │ /webhook │  │ /users/trips     │   │ │
│  │  │ endpoint │  │ /gmail   │  │ /sync endpoints  │   │ │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────────────┘   │ │
│  └───────┼─────────────┼─────────────┼──────────────────┘ │
│          │             │             │                     │
│  ┌───────▼─────────────▼─────────────▼──────────────────┐ │
│  │                  Agent Layer                          │ │
│  │  ┌──────────────────┐      ┌────────────────────┐   │ │
│  │  │ Travel Concierge │      │ Trip Coordinator   │   │ │
│  │  │  (Chat Agent)    │      │ (Extract Agent)    │   │ │
│  │  └────────┬─────────┘      └─────────┬──────────┘   │ │
│  │           │                           │               │ │
│  │           └────────┬──────────────────┘               │ │
│  │                    │                                   │ │
│  │           ┌────────▼─────────┐                        │ │
│  │           │   Tool Registry   │                        │ │
│  │           │  - get_trip       │                        │ │
│  │           │  - extract_data   │                        │ │
│  │           └────────┬──────────┘                        │ │
│  └────────────────────┼───────────────────────────────────┘ │
│                       │                                      │
│  ┌────────────────────▼───────────────────────────────────┐ │
│  │               Model Factory                            │ │
│  │  ┌──────────────┐        ┌──────────────┐            │ │
│  │  │   Claude     │        │   OpenAI     │            │ │
│  │  │   Provider   │        │   Provider   │            │ │
│  │  └──────────────┘        └──────────────┘            │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │               PostgreSQL Database                      │ │
│  │  - users                - conversations                │ │
│  │  - trips                - messages                     │ │
│  │  - email_sources        - llm_requests                 │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                     EXTERNAL SERVICES                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Gmail API   │  │ Anthropic    │  │   OpenAI     │     │
│  │  (Pub/Sub)   │  │   Claude     │  │   GPT-4      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow

**User Chat Flow:**
```
1. User types message in Next.js UI
2. Frontend saves to Supabase (for UI display)
3. Frontend calls POST /chat (Backend)
4. Backend:
   - Loads conversation history from PostgreSQL
   - Loads trip context
   - Calls Travel Concierge agent
   - Agent calls LLM (Claude or GPT-4)
   - Saves message + response to PostgreSQL
   - Logs request (tokens, cost, latency)
5. Returns response to frontend
6. Frontend displays response + saves to Supabase
```

**Email Ingestion Flow:**
```
1. User forwards email to travelroboto@gmail.com
2. Gmail → Google Pub/Sub notification
3. Pub/Sub → POST /webhook/gmail (Backend)
4. Backend:
   - Fetches full email via Gmail API
   - Saves to email_sources table
   - Triggers Trip Coordinator agent
   - Agent extracts trip data (flights, hotel, etc.)
   - Matches to existing trip or creates draft
   - Saves to trips.structured_data (JSONB)
   - Logs extraction with confidence scores
5. (Phase 1C) If conflicts detected:
   - Send confirmation email to user
   - Wait for user reply
   - Apply or discard changes based on response
```

---

## Database Schema

### Core Tables

#### users
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,  -- Reuses Supabase user_id
  email VARCHAR(255) NOT NULL UNIQUE,
  phone VARCHAR(50),
  home_city VARCHAR(100),
  first_name VARCHAR(100),
  last_name VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
```

#### trips
```sql
CREATE TABLE trips (
  id UUID PRIMARY KEY,  -- Reuses Supabase trip_id
  name VARCHAR(200) NOT NULL,
  destination VARCHAR(200) NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  created_by_user_id UUID NOT NULL REFERENCES users(id),

  -- Structured data (for querying, frontend display)
  structured_data JSONB DEFAULT '{}',
  -- Example: {
  --   "flights": [{"airline": "United", "number": "UA123", ...}],
  --   "hotels": [{"name": "Hilton Barcelona", "address": "...", ...}],
  --   "activities": [...]
  -- }

  -- Raw extractions (for agent context, debugging)
  raw_extractions JSONB DEFAULT '[]',
  -- Example: [
  --   {"source": "email:msg_123", "data": {...}, "confidence": 0.95},
  --   {"source": "email:msg_456", "data": {...}, "confidence": 0.88}
  -- ]

  -- Agent-readable summary (for prompts)
  summary TEXT,
  -- Example: "10-day Barcelona trip, June 10-20, 2025. 2 travelers: Alice Chen, Bob Smith.
  --           Staying at Hilton Barcelona (June 10-15) then Hotel W (June 15-20).
  --           Flight: UA123 SFO→BCN June 10 10:00 AM"

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_trips_created_by ON trips(created_by_user_id);
CREATE INDEX idx_trips_dates ON trips(start_date, end_date);
```

#### trip_travelers
```sql
CREATE TABLE trip_travelers (
  trip_id UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role VARCHAR(50) DEFAULT 'traveler',  -- 'organizer' | 'traveler'
  joined_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (trip_id, user_id)
);

CREATE INDEX idx_trip_travelers_user ON trip_travelers(user_id);
```

#### conversations
```sql
CREATE TABLE conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  trip_id UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  conversation_type VARCHAR(50) DEFAULT 'chat',  -- 'chat' | 'email_thread'
  next_turn_number INT DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  -- One conversation per user per trip
  UNIQUE(trip_id, user_id, conversation_type)
);

CREATE INDEX idx_conversations_trip ON conversations(trip_id);
CREATE INDEX idx_conversations_user ON conversations(user_id);
```

#### messages
```sql
CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  user_id UUID,  -- NULL if role='assistant' or role='system'
  role VARCHAR(20) NOT NULL,  -- 'user' | 'assistant' | 'system' | 'tool'
  content TEXT NOT NULL,
  turn_number INT NOT NULL,

  -- AI metadata (only for assistant messages)
  model_provider VARCHAR(50),     -- 'anthropic' | 'openai'
  model_name VARCHAR(100),        -- 'claude-3-5-sonnet-20241022'
  prompt_version VARCHAR(20),     -- 'v1', 'v2', 'v3'
  tool_calls JSONB,               -- [{name: 'get_trip', input: {...}, output: {...}}]

  -- Observability
  tokens_input INT,
  tokens_output INT,
  cost_usd DECIMAL(10, 6),
  latency_ms INT,

  -- User feedback (thumbs up/down)
  feedback VARCHAR(10),  -- 'up' | 'down' | NULL

  created_at TIMESTAMPTZ DEFAULT NOW(),

  CONSTRAINT valid_role CHECK (role IN ('user', 'assistant', 'system', 'tool'))
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, turn_number);
CREATE INDEX idx_messages_created_at ON messages(created_at DESC);
```

### Email & Extraction Tables

#### email_sources
```sql
CREATE TABLE email_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  gmail_message_id VARCHAR(100) UNIQUE NOT NULL,
  from_email VARCHAR(255) NOT NULL,
  subject TEXT,
  received_at TIMESTAMPTZ NOT NULL,

  -- Email content
  raw_body TEXT,              -- Plain text body
  raw_html TEXT,              -- HTML body (for rendering)

  -- Attachments (stored separately, referenced here)
  attachments JSONB DEFAULT '[]',
  -- Example: [
  --   {"filename": "boarding_pass.pdf", "mime_type": "application/pdf",
  --    "size_bytes": 12345, "storage_url": "gs://..."}
  -- ]

  -- Processing status
  extraction_status VARCHAR(20) DEFAULT 'pending',
  -- 'pending' | 'processing' | 'completed' | 'failed'

  extraction_error TEXT,  -- Error message if failed

  -- Matched trip
  trip_id UUID REFERENCES trips(id) ON DELETE SET NULL,
  matched_confidence FLOAT,  -- 0.0-1.0, how confident in trip match

  created_at TIMESTAMPTZ DEFAULT NOW(),
  processed_at TIMESTAMPTZ,

  CONSTRAINT valid_status CHECK (extraction_status IN ('pending', 'processing', 'completed', 'failed'))
);

CREATE INDEX idx_email_sources_trip ON email_sources(trip_id);
CREATE INDEX idx_email_sources_status ON email_sources(extraction_status);
CREATE INDEX idx_email_sources_from ON email_sources(from_email);
```

#### trip_field_versions (Phase 1C)
```sql
CREATE TABLE trip_field_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  trip_id UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  field_name VARCHAR(50) NOT NULL,  -- 'hotel_name', 'flight_number', 'check_in_date'
  value TEXT NOT NULL,
  source VARCHAR(200) NOT NULL,     -- 'email:msg_id_123', 'user_edit', 'agent_extraction'
  confidence FLOAT,                 -- 0.0-1.0 (from LLM extraction)
  status VARCHAR(20) DEFAULT 'active',  -- 'active' | 'superseded' | 'conflicted'

  -- Conflict resolution
  conflict_detected BOOLEAN DEFAULT FALSE,
  conflict_resolved_at TIMESTAMPTZ,
  resolved_by VARCHAR(50),  -- 'user_confirmation', 'auto_rule', 'llm_decision'

  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_trip_field_versions_trip ON trip_field_versions(trip_id, field_name);
CREATE INDEX idx_trip_field_versions_status ON trip_field_versions(status);
```

### Privacy & Sharing Tables

#### conversation_sharing (Phase 1B)
```sql
CREATE TABLE conversation_sharing (
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  share_with_trip_members BOOLEAN DEFAULT FALSE,  -- Privacy: OFF by default
  shared_at TIMESTAMPTZ,
  PRIMARY KEY (conversation_id, user_id)
);

CREATE INDEX idx_conversation_sharing_trip ON conversation_sharing(conversation_id)
  WHERE share_with_trip_members = TRUE;
```

### Observability Tables

#### llm_requests
```sql
CREATE TABLE llm_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
  message_id UUID REFERENCES messages(id) ON DELETE CASCADE,

  -- Request details
  model_provider VARCHAR(50) NOT NULL,
  model_name VARCHAR(100) NOT NULL,
  full_prompt TEXT NOT NULL,       -- Exact prompt sent to LLM
  full_response TEXT NOT NULL,     -- Exact response from LLM

  -- Tool calls
  tool_calls JSONB,
  -- Example: [
  --   {"name": "get_trip_details", "input": {"trip_id": "..."},
  --    "output": {...}, "execution_time_ms": 45}
  -- ]

  -- Usage
  tokens_input INT NOT NULL,
  tokens_output INT NOT NULL,
  cost_usd DECIMAL(10, 6) NOT NULL,
  latency_ms INT NOT NULL,

  -- Response metadata
  finish_reason VARCHAR(50),  -- 'stop', 'length', 'tool_use', 'error'
  error_message TEXT,

  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_llm_requests_conversation ON llm_requests(conversation_id);
CREATE INDEX idx_llm_requests_created_at ON llm_requests(created_at DESC);
CREATE INDEX idx_llm_requests_model ON llm_requests(model_provider, model_name);
```

#### metrics (For aggregations)
```sql
CREATE TABLE metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  metric_name VARCHAR(100) NOT NULL,
  metric_value FLOAT NOT NULL,
  dimensions JSONB DEFAULT '{}',  -- {user_id: "...", model: "claude", ...}
  timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_metrics_name_time ON metrics(metric_name, timestamp DESC);
```

### A/B Testing Tables (Phase 2)

#### ab_test_assignments
```sql
CREATE TABLE ab_test_assignments (
  conversation_id UUID PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
  model_variant VARCHAR(50) NOT NULL,  -- 'claude-3-5-sonnet', 'gpt-4o'
  prompt_version VARCHAR(20) NOT NULL,  -- 'v1', 'v2'
  assigned_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ab_assignments_variant ON ab_test_assignments(model_variant);
```

---

## API Specification

### Base URL
```
Development: http://localhost:8000
Production: https://api.travelroboto.com
```

### Authentication
All endpoints require authentication (except health check).

**Headers:**
```
Authorization: Bearer <supabase_jwt_token>
```

Backend validates token with Supabase to extract user_id.

---

### Endpoints

#### Health Check
```
GET /health

Response:
{
  "status": "healthy",
  "environment": "production",
  "ab_testing_enabled": true,
  "timestamp": "2025-01-16T10:00:00Z"
}
```

---

#### Chat Endpoint

```
POST /chat

Request:
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",  // UUID
  "user_id": "550e8400-e29b-41d4-a716-446655440001",
  "trip_id": "550e8400-e29b-41d4-a716-446655440002",
  "message": "What hotel am I staying at?"
}

Response:
{
  "message_id": "550e8400-e29b-41d4-a716-446655440003",
  "role": "assistant",
  "content": "You're staying at the Hilton Barcelona, located at 123 Main Street. Your check-in is on June 10, 2025.",
  "model_used": "claude-3-5-sonnet-20241022",
  "prompt_version": "v1",
  "tool_calls": [
    {
      "name": "get_trip_details",
      "input": {"trip_id": "550e8400-e29b-41d4-a716-446655440002"},
      "output": {"hotel_name": "Hilton Barcelona", "address": "123 Main St", ...}
    }
  ],
  "metadata": {
    "tokens_input": 1500,
    "tokens_output": 150,
    "cost_usd": 0.0023,
    "latency_ms": 2100
  },
  "created_at": "2025-01-16T10:01:30Z"
}

Error Responses:
400 Bad Request - Missing required fields
401 Unauthorized - Invalid token
404 Not Found - Conversation or trip not found
429 Too Many Requests - Rate limit exceeded
500 Internal Server Error - LLM failure (includes retry info)
```

---

#### User Sync

```
POST /users/sync

Request:
{
  "user_id": "550e8400-e29b-41d4-a716-446655440001",  // Supabase user_id
  "email": "alice@example.com",
  "phone": "+1-555-0100",
  "home_city": "San Francisco",
  "first_name": "Alice",
  "last_name": "Chen"
}

Response:
{
  "status": "synced",
  "user_id": "550e8400-e29b-41d4-a716-446655440001",
  "created": false,  // true if new user, false if updated
  "updated_at": "2025-01-16T10:00:00Z"
}

Notes:
- Idempotent: Can be called multiple times safely
- Upserts user (insert or update)
```

---

#### Trip Sync

```
POST /trips/sync

Request:
{
  "trip_id": "550e8400-e29b-41d4-a716-446655440002",  // Supabase trip_id
  "name": "Barcelona Summer 2025",
  "destination": "Barcelona, Spain",
  "start_date": "2025-06-10",
  "end_date": "2025-06-20",
  "travelers": [
    "550e8400-e29b-41d4-a716-446655440001",  // user_id (Alice)
    "550e8400-e29b-41d4-a716-446655440010"   // user_id (Bob)
  ],
  "created_by": "550e8400-e29b-41d4-a716-446655440001"
}

Response:
{
  "status": "synced",
  "trip_id": "550e8400-e29b-41d4-a716-446655440002",
  "created": true,
  "updated_at": "2025-01-16T10:00:00Z"
}

Notes:
- Idempotent
- Creates trip_travelers relationships
- Generates initial summary
```

---

#### Trip Delete

```
DELETE /trips/{trip_id}

Response:
{
  "status": "deleted",
  "trip_id": "550e8400-e29b-41d4-a716-446655440002"
}

Notes:
- Cascades to conversations, messages, email_sources
- Soft delete option: Add deleted_at column instead
```

---

#### Gmail Webhook (Phase 1B)

```
POST /webhook/gmail

Request (from Google Pub/Sub):
{
  "message": {
    "data": "base64_encoded_data",
    "messageId": "...",
    "publishTime": "2025-01-16T10:00:00Z"
  },
  "subscription": "projects/..."
}

Response:
{
  "status": "received",
  "email_id": "550e8400-e29b-41d4-a716-446655440004",
  "extraction_status": "processing"
}

Background Processing:
1. Decode Pub/Sub message to get Gmail historyId
2. Fetch new messages from Gmail API
3. Save to email_sources table
4. Trigger Trip Coordinator agent (async)
5. Return 200 OK immediately (don't block Pub/Sub)

Notes:
- Must respond within 10 seconds to Pub/Sub
- Actual extraction happens asynchronously
```

---

#### Coordinator Extract (Phase 1B - Testing endpoint)

```
POST /coordinator/extract

Request:
{
  "email_text": "Dear Alice, Your hotel reservation at Hilton Barcelona is confirmed...",
  "user_id": "550e8400-e29b-41d4-a716-446655440001"
}

Response:
{
  "extraction_id": "550e8400-e29b-41d4-a716-446655440005",
  "extracted_data": {
    "booking_type": "hotel",
    "hotel_name": "Hilton Barcelona",
    "check_in": "2025-06-10",
    "check_out": "2025-06-15",
    "confirmation_code": "ABC123"
  },
  "confidence": 0.95,
  "matched_trip_id": "550e8400-e29b-41d4-a716-446655440002",
  "match_confidence": 0.88
}

Notes:
- Useful for testing extraction logic without Gmail integration
- Can paste email text directly
```

---

## Agent Design

### Travel Concierge (Phase 1)

**Purpose**: Chat interface for users to ask questions about their trip

**System Prompt (v1):**
```
You are Travel Roboto, an expert travel assistant helping users plan and manage their trips.

Your role:
- Answer questions about trip itineraries, bookings, and logistics
- Help coordinate group travel plans
- Provide helpful reminders about important trip details

Key behaviors:
- Always cite sources when providing information (e.g., "According to your United confirmation email from Jan 15...")
- If information is missing or unclear, ask clarifying questions
- For time-sensitive items (flights, check-ins), emphasize confirmation codes and times
- Be proactive: if user asks about hotel, also mention check-in time if available
- Be friendly and concise

Current trip context:
{trip_summary}

Recent conversation (last 10 messages):
{conversation_history}

Today's date: {current_date}

Available tools:
- get_trip_details(trip_id): Retrieve detailed trip information including flights, hotels, activities
- search_past_messages(query): Search past conversation history (future feature)

Instructions:
- Use tools when you need trip data to answer questions
- Provide accurate information based on trip context
- If you don't have information, admit it and ask the user
- Format responses clearly with bullet points when listing multiple items
```

**Tool Access:**
- `get_trip_details(trip_id)`: Read from trips table

**Context Window:**
- Last 10 message pairs (20 messages total)
- Trip summary
- Current date/time

**Model**: Claude 3.5 Sonnet (Phase 1), GPT-4o (Phase 2)

---

### Trip Coordinator (Phase 1B)

**Purpose**: Extract trip information from emails and documents

**System Prompt (v1):**
```
You are a Trip Coordinator agent specializing in extracting structured travel information from emails and documents.

Your task:
Extract key trip details from the provided text and return structured data.

Information to extract:
- Booking type: flight, hotel, activity, car_rental, other
- Destination: city, country
- Dates: check-in, check-out, departure, arrival
- Provider: airline, hotel chain, booking platform
- Confirmation codes
- Names: travelers, hotels, airlines
- Addresses and locations
- Prices and currencies

Output format (JSON):
{
  "booking_type": "hotel",
  "provider": "Booking.com",
  "hotel_name": "Hilton Barcelona",
  "address": "123 Main Street, Barcelona, Spain",
  "check_in": "2025-06-10",
  "check_out": "2025-06-15",
  "confirmation_code": "ABC123456",
  "total_price": {"amount": 1200.00, "currency": "USD"},
  "guests": ["Alice Chen", "Bob Smith"]
}

Important:
- Only extract information explicitly stated in the text
- For ambiguous fields, provide multiple possibilities with confidence scores
- If critical information is missing (dates, location), note it in "missing_fields"
- Preserve exact values (confirmation codes, addresses) without modification

Confidence scoring:
- 1.0 = Explicitly stated, no ambiguity
- 0.8-0.9 = Clearly implied, high confidence
- 0.5-0.7 = Inferred from context, moderate confidence
- <0.5 = Uncertain, mark for user verification
```

**Tool Access:**
- `extract_trip_data(email_text)`: Parse email/document
- `match_trip(destination, dates, user_id)`: Find matching trip in DB

**Processing Flow:**
1. Receive email text
2. Extract structured data with confidence scores
3. Match to existing trip (by destination + date overlap)
4. If no match, create draft trip
5. Save extraction to trip_field_versions
6. Update trips.structured_data and trips.summary

---

### Agent Router (Phase 2)

**Purpose**: Route user queries to appropriate specialized agent

**System Prompt:**
```
You are an intent classifier for a travel assistant system.

Your task: Classify the user's query into one of these categories:

Categories:
- "general": General trip questions, itinerary, logistics
- "restaurant": Restaurant recommendations, dining, food
- "flight": Flight details, check-in, airline questions
- "transport": Local transportation, travel time, directions
- "activity": Things to do, attractions, events

User query: {user_message}

Respond with JSON:
{
  "intent": "restaurant",
  "confidence": 0.95,
  "reasoning": "User is asking for restaurant recommendations near their hotel"
}
```

**Routing Logic:**
```python
class AgentRouter:
    def __init__(self):
        self.agents = {
            "general": TravelConcierge(),
            "restaurant": RestaurantExpert(),  # Phase 3
            "flight": FlightChecker(),         # Phase 3
            "transport": LocalTransportAgent() # Phase 3
        }

    async def route(self, user_message: str) -> Agent:
        # Classify intent
        intent = await self.classify_intent(user_message)

        # Route to specialist or fallback to general
        agent = self.agents.get(intent["intent"], self.agents["general"])

        logger.info("routing_decision", intent=intent["intent"], confidence=intent["confidence"])

        return agent
```

---

## Tool Registry

### Tool Interface (Pydantic-based)

```python
from pydantic import BaseModel, Field
from typing import Any, Callable, Optional
from enum import Enum

class ToolContext(BaseModel):
    """Context passed to every tool execution"""
    db: Any  # Database session
    user_id: str
    conversation_id: str
    trip_id: Optional[str] = None

class ToolInput(BaseModel):
    """Base class for tool inputs"""
    pass

class ToolOutput(BaseModel):
    """Base class for tool outputs"""
    pass

class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: type[ToolInput]
    output_schema: type[ToolOutput]
    function: Callable

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        input_schema: type[ToolInput],
        output_schema: type[ToolOutput]
    ):
        """Decorator to register a tool"""
        def decorator(func: Callable):
            self._tools[name] = ToolDefinition(
                name=name,
                description=description,
                input_schema=input_schema,
                output_schema=output_schema,
                function=func
            )
            return func
        return decorator

    def get_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def to_anthropic_format(self) -> list[dict]:
        """Convert to Anthropic function calling format"""
        tools = []
        for tool in self._tools.values():
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema.model_json_schema()
            })
        return tools

    def to_openai_format(self) -> list[dict]:
        """Convert to OpenAI function calling format"""
        tools = []
        for tool in self._tools.values():
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema.model_json_schema()
                }
            })
        return tools

    async def execute(
        self,
        tool_name: str,
        tool_input: dict,
        context: ToolContext
    ) -> ToolOutput:
        """Execute a tool and return result"""
        if tool_name not in self._tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool = self._tools[tool_name]

        # Validate input
        validated_input = tool.input_schema(**tool_input)

        # Execute
        result = await tool.function(validated_input, context)

        # Validate output
        if not isinstance(result, tool.output_schema):
            result = tool.output_schema(**result)

        return result
```

---

### Phase 1 Tools

#### get_trip_details

```python
class GetTripDetailsInput(ToolInput):
    trip_id: str = Field(description="UUID of the trip to retrieve")

class GetTripDetailsOutput(ToolOutput):
    trip_name: str
    destination: str
    dates: str  # Human-readable: "June 10-20, 2025"
    travelers: list[str]  # ["Alice Chen", "Bob Smith"]
    summary: str  # Full trip summary for agent context

@tool_registry.register(
    name="get_trip_details",
    description="Retrieve detailed information about a trip including itinerary, bookings, and travelers",
    input_schema=GetTripDetailsInput,
    output_schema=GetTripDetailsOutput
)
async def get_trip_details(input: GetTripDetailsInput, context: ToolContext) -> GetTripDetailsOutput:
    # Verify user has access to trip
    trip = await context.db.trips.get(input.trip_id)

    if not trip:
        raise ValueError(f"Trip {input.trip_id} not found")

    # Check if user is on this trip
    is_traveler = await context.db.trip_travelers.exists(
        trip_id=input.trip_id,
        user_id=context.user_id
    )

    if not is_traveler:
        raise PermissionError(f"User {context.user_id} not authorized for trip {input.trip_id}")

    # Get travelers
    travelers = await context.db.trip_travelers.get_names(input.trip_id)

    return GetTripDetailsOutput(
        trip_name=trip.name,
        destination=trip.destination,
        dates=f"{trip.start_date.strftime('%B %d')} - {trip.end_date.strftime('%B %d, %Y')}",
        travelers=travelers,
        summary=trip.summary
    )
```

---

### Phase 1B Tools

#### extract_trip_data

```python
class ExtractTripDataInput(ToolInput):
    email_text: str = Field(description="Raw email text to extract trip data from")
    extraction_type: str = Field(
        default="auto",
        description="Type of extraction: 'auto', 'flight', 'hotel', 'activity'"
    )

class ExtractTripDataOutput(ToolOutput):
    booking_type: str  # 'flight', 'hotel', 'activity', 'car_rental', 'other'
    extracted_data: dict  # Structured data specific to booking type
    confidence: float  # 0.0-1.0
    missing_fields: list[str]  # Fields that couldn't be extracted

@tool_registry.register(
    name="extract_trip_data",
    description="Extract structured trip information from email text using LLM",
    input_schema=ExtractTripDataInput,
    output_schema=ExtractTripDataOutput
)
async def extract_trip_data(input: ExtractTripDataInput, context: ToolContext) -> ExtractTripDataOutput:
    # Call Trip Coordinator agent for extraction
    coordinator = TripCoordinator()
    result = await coordinator.extract(input.email_text)

    return ExtractTripDataOutput(
        booking_type=result["booking_type"],
        extracted_data=result["data"],
        confidence=result["confidence"],
        missing_fields=result.get("missing_fields", [])
    )
```

---

## Observability

### Structured Logging

**Configuration (utils/logging.py):**
```python
import structlog
import logging
from contextvars import ContextVar

# Context variable for request ID (propagates through async calls)
request_id_var: ContextVar[str] = ContextVar("request_id", default=None)

def configure_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.PrintLoggerFactory(),
    )

def get_logger(name: str):
    return structlog.get_logger(name)

class RequestIdMiddleware:
    """FastAPI middleware to add request_id to all logs"""
    async def __call__(self, request: Request, call_next):
        request_id = str(uuid4())
        request_id_var.set(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)

        structlog.contextvars.unbind_contextvars("request_id")
        return response
```

**Usage in Agents:**
```python
logger = get_logger("travel_concierge")

# Agent turn start
logger.info(
    "agent_turn_start",
    conversation_id=str(conv_id),
    user_id=str(user_id),
    trip_id=str(trip_id),
    user_message=message
)

# Context loaded
logger.info(
    "context_loaded",
    conversation_id=str(conv_id),
    num_messages=len(messages),
    trip_summary_length=len(trip.summary)
)

# Prompt built
logger.info(
    "prompt_built",
    conversation_id=str(conv_id),
    model=model_name,
    estimated_tokens=count_tokens(prompt),
    tools_available=[t.name for t in tools]
)

# LLM request
logger.info("llm_request_sent", model=model_name)

# Tool execution
logger.info(
    "tool_execution",
    tool_name=tool_name,
    tool_input=tool_input,
    execution_time_ms=elapsed
)

# LLM response
logger.info(
    "llm_response_received",
    model=model_name,
    tokens_input=response.usage.input_tokens,
    tokens_output=response.usage.output_tokens,
    cost_usd=cost,
    latency_ms=latency
)

# Agent turn complete
logger.info(
    "agent_turn_complete",
    response_length=len(response.content),
    total_time_ms=total_elapsed
)
```

**Log Output (JSON):**
```json
{
  "event": "agent_turn_start",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440001",
  "user_id": "550e8400-e29b-41d4-a716-446655440002",
  "user_message": "What hotel am I staying at?",
  "timestamp": "2025-01-16T10:00:00.123Z",
  "level": "info"
}
```

---

### Cost Tracking

```python
# Pricing table (update periodically)
MODEL_PRICING = {
    "claude-3-5-sonnet-20241022": {
        "input_per_million": 3.00,
        "output_per_million": 15.00
    },
    "gpt-4o": {
        "input_per_million": 2.50,
        "output_per_million": 10.00
    },
    "claude-3-haiku-20240307": {
        "input_per_million": 0.25,
        "output_per_million": 1.25
    }
}

def calculate_cost(model_name: str, usage: LLMUsage) -> float:
    if model_name not in MODEL_PRICING:
        logger.warning(f"Unknown model for pricing: {model_name}")
        return 0.0

    pricing = MODEL_PRICING[model_name]
    cost = (
        (usage.input_tokens / 1_000_000) * pricing["input_per_million"] +
        (usage.output_tokens / 1_000_000) * pricing["output_per_million"]
    )
    return round(cost, 6)

# After LLM call
response = await anthropic.messages.create(...)
cost = calculate_cost("claude-3-5-sonnet-20241022", response.usage)

# Save to DB
await db.messages.update(
    message_id,
    tokens_input=response.usage.input_tokens,
    tokens_output=response.usage.output_tokens,
    cost_usd=cost
)

# Log metric
await db.metrics.insert(
    metric_name="request_cost_usd",
    metric_value=cost,
    dimensions={
        "user_id": user_id,
        "model": model_name,
        "conversation_id": conversation_id
    }
)
```

---

## Implementation Roadmap

### Phase 1: Basic Chat (Week 1)

**Goal**: User can chat with Travel Concierge about their trip

**Tasks:**
1. ✅ Set up FastAPI project structure
   - main.py with app factory
   - config.py with Settings (already exists)
   - api/, agents/, tools/, models/ directories

2. ✅ Database setup
   - Create Alembic migrations for: users, trips, trip_travelers, conversations, messages
   - Write repository layer (db/repositories/)
   - Add database tests

3. ✅ Model abstraction
   - models/factory.py - Model factory
   - models/providers/claude.py - Claude client
   - Abstract interface for LLM calls

4. ✅ Tool registry
   - tools/registry.py - ToolRegistry class
   - tools/trip_tools.py - get_trip_details implementation
   - Pydantic schemas for tool I/O

5. ✅ Travel Concierge agent
   - agents/travel_concierge.py
   - agents/prompts/travel_concierge/v1_system.txt
   - Context loading (last 10 messages + trip summary)
   - LLM call with tool support

6. ✅ Chat API endpoint
   - api/chat.py - POST /chat
   - Request validation (Pydantic)
   - Response formatting

7. ✅ Sync endpoints
   - api/sync.py - POST /users/sync, POST /trips/sync, DELETE /trips/{id}
   - Idempotent upsert logic

8. ✅ Observability
   - Structured logging (utils/logging.py enhancement)
   - Cost tracking
   - Save llm_requests to DB

9. ✅ Testing
   - Unit tests for tools
   - Integration tests for chat flow (mocked LLM)
   - Fixtures for test data

**Acceptance Criteria:**
- [ ] User sends chat message → Agent responds with trip info
- [ ] Cost tracked and returned in response
- [ ] All requests logged with structured JSON
- [ ] Tests passing with >80% coverage

**Demo Script:**
```bash
# Start server
python main.py

# Sync user
curl -X POST http://localhost:8000/users/sync -H "Authorization: Bearer token" -d '{
  "user_id": "uuid", "email": "alice@example.com", "first_name": "Alice"
}'

# Sync trip
curl -X POST http://localhost:8000/trips/sync -H "Authorization: Bearer token" -d '{
  "trip_id": "uuid", "name": "Barcelona", "destination": "Barcelona, Spain",
  "start_date": "2025-06-10", "end_date": "2025-06-20", "travelers": ["uuid"]
}'

# Chat
curl -X POST http://localhost:8000/chat -H "Authorization: Bearer token" -d '{
  "conversation_id": "uuid", "user_id": "uuid", "trip_id": "uuid",
  "message": "What hotel am I staying at?"
}'

# Expected response:
# {
#   "message_id": "...",
#   "content": "I don't have hotel information yet. Have you received a hotel confirmation email?",
#   "model_used": "claude-3-5-sonnet",
#   "cost_usd": 0.0018,
#   "latency_ms": 1800
# }
```

---

### Phase 1B: Email Extraction (Week 2)

**Goal**: Extract trip data from emails, add multi-model support, privacy sharing

**Tasks:**
1. ✅ Gmail API integration
   - Set up Google Cloud project
   - Enable Gmail API + Pub/Sub
   - Create service account for travelroboto@gmail.com
   - Configure Pub/Sub topic + subscription
   - Store credentials in secrets/

2. ✅ Email webhook endpoint
   - api/webhooks.py - POST /webhook/gmail
   - Decode Pub/Sub message
   - Fetch email via Gmail API
   - Save to email_sources table
   - Trigger background extraction (async)

3. ✅ Trip Coordinator agent
   - agents/trip_coordinator.py
   - agents/prompts/trip_coordinator/v1_extractor.txt
   - Extract structured data from email text
   - Return confidence scores

4. ✅ Email extraction flow
   - tools/email_tools.py - extract_trip_data tool
   - Match email to trip (by destination + dates)
   - Save to trips.structured_data (JSONB)
   - Update trips.summary
   - Save to trip_field_versions

5. ✅ Database migrations
   - Add: email_sources, conversation_sharing tables
   - Migration script

6. ✅ OpenAI provider
   - models/providers/openai.py - GPT-4 client
   - Update factory to support both Claude and OpenAI

7. ✅ Privacy sharing feature
   - conversation_sharing table
   - Update context loading to check sharing settings
   - API endpoint: PUT /conversations/{id}/sharing

8. ✅ Testing endpoint (no Gmail)
   - POST /coordinator/extract - paste email text directly
   - Useful for testing extraction logic

**Acceptance Criteria:**
- [ ] User forwards email → System extracts hotel details
- [ ] Extracted data visible in trips.structured_data
- [ ] User asks "Where am I staying?" → Agent cites email as source
- [ ] Users can opt-in to share conversations with trip members

**Demo Script:**
```bash
# Test extraction (without Gmail)
curl -X POST http://localhost:8000/coordinator/extract -d '{
  "email_text": "Your hotel reservation at Hilton Barcelona is confirmed. Check-in: June 10, 2025...",
  "user_id": "uuid"
}'

# Expected response:
# {
#   "extracted_data": {
#     "booking_type": "hotel",
#     "hotel_name": "Hilton Barcelona",
#     "check_in": "2025-06-10"
#   },
#   "confidence": 0.95,
#   "matched_trip_id": "uuid"
# }

# Chat after extraction
curl -X POST http://localhost:8000/chat -d '{...}'

# Expected response:
# "You're staying at the Hilton Barcelona (from your Booking.com email received Jan 16)"
```

---

### Phase 1C: Conflict Resolution + PDFs + Confirmation Emails (Week 3)

**Goal**: Handle conflicting data, parse PDFs, send confirmation emails

**Tasks:**
1. ✅ Conflict detection
   - tools/conflict_tools.py - detect_conflicts tool
   - Hybrid approach: rules + LLM
   - Save conflicts to trip_field_versions with status='conflicted'

2. ✅ Confirmation email sending
   - tools/email_tools.py - send_confirmation_email tool
   - Gmail API: send email
   - Template: "Hotel changed from X to Y, reply to confirm"
   - Store email thread ID for tracking responses

3. ✅ Email reply processing
   - Extend POST /webhook/gmail to handle replies
   - Parse user intent ("yes", "no", "actually...")
   - Apply or discard changes based on response
   - Update trip_field_versions status

4. ✅ PDF parsing
   - tools/document_tools.py - extract_pdf_text tool
   - Use PyPDF2 for text extraction
   - Feed extracted text to Trip Coordinator
   - Save attachment metadata in email_sources.attachments

5. ✅ Version history
   - trip_field_versions table (already designed)
   - Track all changes with source + confidence
   - Status: active | superseded | conflicted

6. ✅ Testing
   - Test conflict detection with mock data
   - Test PDF extraction
   - Test email confirmation flow

**Acceptance Criteria:**
- [ ] Coordinator detects conflicting hotel names → Sends confirmation email
- [ ] User replies "yes" → Changes applied
- [ ] User replies "no" → Changes discarded
- [ ] PDF boarding pass → Flight details extracted

**Demo Script:**
```bash
# Simulate conflicting email
# Existing trip has: hotel = "Hilton Barcelona"
# New email says: hotel = "Hotel W Barcelona"

curl -X POST http://localhost:8000/coordinator/extract -d '{
  "email_text": "Your reservation at Hotel W Barcelona is confirmed...",
  "user_id": "uuid"
}'

# Backend:
# - Detects conflict (different hotel name)
# - Sends confirmation email to user
# - Logs conflict in trip_field_versions with status='conflicted'

# User receives email:
# "Hotel changed: Hilton → Hotel W. Reply to confirm."

# User replies: "Yes, update my trip"

# Webhook receives reply → Parses intent → Applies changes
# - trip.structured_data updated
# - trip_field_versions status: 'conflicted' → 'active'
```

---

### Phase 2: Multi-Model + A/B Testing + Agent Routing (Week 4)

**Goal**: Compare models, route to specialized agents, prompt versioning

**Tasks:**
1. ✅ A/B testing infrastructure
   - ab_test_assignments table
   - Assign conversation to model variant (hash-based 50/50)
   - Track assignment in DB

2. ✅ Prompt versioning
   - agents/prompts/travel_concierge/v2_system.txt (alternative version)
   - agents/prompts/travel_concierge/active.json (points to v1 or v2)
   - Load prompt based on active version

3. ✅ Agent router
   - agents/orchestrator.py - AgentRouter class
   - LLM-based intent classification
   - Route to appropriate agent

4. ✅ Sub-agent stubs
   - agents/restaurant_expert.py (basic implementation)
   - agents/flight_checker.py (basic implementation)
   - agents/local_transport_agent.py (basic implementation)

5. ✅ Metrics dashboard data
   - Query llm_requests table for metrics
   - Compare: Claude vs GPT-4 (latency, cost, quality)
   - Export to CSV or JSON for analysis

**Acceptance Criteria:**
- [ ] 50% conversations use Claude, 50% use GPT-4o
- [ ] Prompt version logged per request
- [ ] Router classifies "restaurant" queries → Routes to restaurant_expert
- [ ] Metrics show model comparison

**Demo Script:**
```bash
# Conversation A (assigned to Claude)
curl -X POST http://localhost:8000/chat -d '{
  "conversation_id": "conv-a", ...
}'
# Response: model_used = "claude-3-5-sonnet", prompt_version = "v1"

# Conversation B (assigned to GPT-4o)
curl -X POST http://localhost:8000/chat -d '{
  "conversation_id": "conv-b", ...
}'
# Response: model_used = "gpt-4o", prompt_version = "v1"

# Query metrics
curl http://localhost:8000/metrics/summary?days=7

# Response:
# {
#   "claude-3-5-sonnet": {"avg_latency_ms": 2100, "avg_cost": 0.0023, "requests": 50},
#   "gpt-4o": {"avg_latency_ms": 1800, "avg_cost": 0.0019, "requests": 50}
# }
```

---

### Phase 3: Advanced Features (Week 5+)

**Goal**: RAG, summarization, LLM-as-judge, specialized agents

**Tasks:**
1. ✅ Conversation summarization
   - Detect long conversations (>50 messages)
   - Summarize old messages, keep recent 10-25 full
   - Save summary to conversations table

2. ✅ RAG - Vector embeddings
   - message_embeddings table
   - Embed all messages on creation
   - Semantic search for "that restaurant we discussed"

3. ✅ LLM-as-judge evaluation
   - evaluation/test_cases.py - Golden dataset
   - evaluation/llm_judge.py - Judge prompt
   - Weekly eval suite, track scores over time

4. ✅ Specialized agents with external APIs
   - Restaurant expert: Yelp API integration
   - Flight checker: Live flight status API
   - Local transport: Google Maps API for travel time

5. ✅ Multimodal LLM for PDFs
   - Use Claude 3.5 Sonnet with image input
   - Extract from image-based PDFs (scanned boarding passes)

**Acceptance Criteria:**
- [ ] Long conversations auto-summarize
- [ ] User asks about past discussion → RAG finds relevant message
- [ ] Weekly eval shows quality score trend
- [ ] Restaurant agent returns Yelp recommendations

---

## Summary

This technical plan provides:
- ✅ Complete database schema with migrations
- ✅ API specification with request/response formats
- ✅ Agent design with system prompts
- ✅ Tool registry architecture
- ✅ Observability and cost tracking
- ✅ Phased implementation roadmap with acceptance criteria

**Next Steps:**
1. Review this plan
2. Start Phase 1 implementation
3. Create Alembic migrations for database schema
4. Build Travel Concierge agent
5. Implement POST /chat endpoint
6. Test end-to-end chat flow

**Timeline:**
- Phase 1: Week 1 (Basic chat working)
- Phase 1B: Week 2 (Email extraction working)
- Phase 1C: Week 3 (Conflict resolution + PDFs)
- Phase 2: Week 4 (A/B testing + routing)
- Phase 3: Week 5+ (Advanced features)

Ready to start building! 🚀
