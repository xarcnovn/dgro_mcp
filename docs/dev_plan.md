# DGRO Web Application - Development Plan

## Implementation Order (Reversed)

**Phase 3 → Phase 2 → Phase 1**

### Why This Order?
1. **Frontend First**: Build UI with mock data, establish patterns and visual feedback
2. **FastAPI Second**: Connect to real database via simple REST (easier debugging)
3. **MCP Last**: Add complex AI chat when frontend is stable

---

## Phase 3: Next.js Frontend (DO FIRST)

### Setup
```bash
npx create-next-app@latest frontend --typescript --tailwind --app --no-src-dir
cd frontend
npm install
```

### Directory Structure
```
frontend/
├── app/
│   ├── layout.tsx                    # Root layout
│   ├── page.tsx                      # Cases list page
│   ├── cases/[id]/page.tsx           # Case detail page
│   └── globals.css                   # Global styles
├── components/
│   ├── Header.tsx                    # Navigation/branding
│   ├── CaseCard.tsx                  # Individual case card
│   ├── CasesList.tsx                 # Cases grid view
│   ├── CaseDetail.tsx                # Full case view
│   ├── ChatModal.tsx                 # New case chat
│   ├── OffersList.tsx                # Offers table
│   └── EmailThreads.tsx              # Email communications
├── lib/
│   ├── api-client.ts                 # FastAPI fetch wrapper (Phase 2)
│   ├── mcp-client.ts                 # MCP HTTP/SSE client (Phase 1 - stub for now)
│   ├── types.ts                      # TypeScript interfaces
│   └── mock-data.ts                  # Mock data for Phase 3
└── hooks/
    └── useMCPChat.ts                 # MCP chat hook (Phase 1 - stub for now)
```

### Mock Data Structure
Match DB schema from mcp_server_incremental.py:

```typescript
// lib/types.ts
export interface Case {
  id: number;
  user_id: number;
  status: 'new' | 'in_progress' | 'vendor_search' | 'negotiation' | 'completed';
  category: string;
  details: string;
  urgency: 'low' | 'medium' | 'high';
  budget_range?: string;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: number;
  name: string;
  email: string;
  company: string;
  phone?: string;
}

export interface Offer {
  id: number;
  case_id: number;
  vendor_email: string;
  price_quoted?: number;
  details: string;
  status: 'pending' | 'accepted' | 'rejected';
  received_at: string;
}

export interface EmailCommunication {
  id: number;
  case_id: number;
  vendor_email: string;
  subject: string;
  body: string;
  direction: 'sent' | 'received';
  timestamp: string;
  thread_id?: string;
}
```

### Component Specifications

**1. Header.tsx**
- Logo/branding "DGRO"
- Navigation: Cases link
- "New Case" button (opens ChatModal)
- Company name from env

**2. CaseCard.tsx**
- Props: `case: Case`
- Display: Case ID, category, status badge (color-coded), created date, urgency indicator
- Click handler: Navigate to `/cases/[id]`
- Tailwind styling: card with hover effect

**3. CasesList.tsx**
- State: cases array, filter (status)
- Data source: Mock data (Phase 3) → API (Phase 2)
- Grid layout: responsive (1/2/3 columns)
- Status filter tabs: All, In Progress, Vendor Search, Negotiation, Completed
- Empty state: "No cases found"

**4. CaseDetail.tsx**
- Props: `caseId: number`
- Sections:
  - Case info card (status, category, urgency, budget, details)
  - User info card (name, email, company, phone)
  - Search history (queries and timestamps)
  - Offers table (OffersList component)
  - Email communications (EmailThreads component)
- Actions: Status dropdown, notes textarea

**5. ChatModal.tsx**
- Opens on "New Case" button
- Modal overlay with close button
- Chat interface:
  - Message bubbles (user/assistant)
  - Scroll container
  - Input field + send button
- Phase 3: Mock conversation flow
- Phase 1: Connect to MCP client for real chat

**6. OffersList.tsx**
- Props: `caseId: number`
- Table columns: Vendor Email, Price, Status, Received Date, Actions
- Actions: Accept/Reject buttons
- Empty state: "No offers yet"

**7. EmailThreads.tsx**
- Props: `caseId: number`
- List of email threads (grouped by thread_id)
- Expandable threads
- Direction indicators: sent (blue), received (gray)
- Empty state: "No communications yet"

### Styling Approach
- Port CSS from frontend.md → Tailwind utility classes
- Color scheme:
  - Primary: Blue (#3B82F6)
  - Success: Green (#10B981)
  - Warning: Yellow (#F59E0B)
  - Danger: Red (#EF4444)
- Status badges: `bg-blue-100 text-blue-800` pattern
- Responsive: mobile-first breakpoints

### Phase 3 Deliverables
- ✅ All components render with mock data
- ✅ Routing works (/ and /cases/[id])
- ✅ ChatModal opens/closes
- ✅ Responsive design
- ✅ TypeScript types defined
- ✅ Ready for API integration

---

## Phase 2: FastAPI REST API (DO SECOND)

### File: backend/api_server.py

```python
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
from typing import List, Optional, Generator
import json

app = FastAPI(title="DGRO API", version="1.0.0")

# CORS for Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "case_search.db"

# Response Models
class Case(BaseModel):
    id: int
    user_id: int
    status: str
    category: str
    details: str
    urgency: str
    budget_range: Optional[str] = None
    created_at: str
    updated_at: str

class User(BaseModel):
    id: int
    name: str
    email: str
    company: str
    phone: Optional[str] = None

class Search(BaseModel):
    id: int
    case_id: int
    query: str
    timestamp: str
    results_json: str

class Offer(BaseModel):
    id: int
    case_id: int
    vendor_email: str
    price_quoted: Optional[float] = None
    details: str
    status: str
    received_at: str

class EmailCommunication(BaseModel):
    id: int
    case_id: int
    vendor_email: str
    subject: str
    body: str
    direction: str
    timestamp: str
    thread_id: Optional[str] = None

# Initialize database with optimal settings
def init_db():
    """Initialize database with WAL mode for better concurrency"""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()
    finally:
        conn.close()

# Run on startup
@app.on_event("startup")
async def startup_event():
    init_db()

# Database dependency with automatic cleanup
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Database connection with automatic cleanup.
    Prevents connection leaks by using FastAPI dependency injection.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# Endpoints with proper error handling and connection management
@app.get("/api/cases", response_model=List[Case])
def get_cases(
    status: Optional[str] = None,
    db: sqlite3.Connection = Depends(get_db)
):
    """Get all cases, optionally filtered by status"""
    try:
        cursor = db.cursor()
        if status:
            cursor.execute(
                "SELECT * FROM cases WHERE status = ? ORDER BY created_at DESC",
                (status,)
            )
        else:
            cursor.execute("SELECT * FROM cases ORDER BY created_at DESC")

        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/cases/{case_id}", response_model=Case)
def get_case(
    case_id: int,
    db: sqlite3.Connection = Depends(get_db)
):
    """Get single case by ID"""
    try:
        cursor = db.cursor()
        cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Case not found")

        return dict(row)
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/cases/{case_id}/searches", response_model=List[Search])
def get_searches(
    case_id: int,
    db: sqlite3.Connection = Depends(get_db)
):
    """Get all searches for a case"""
    try:
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM searches WHERE case_id = ? ORDER BY timestamp DESC",
            (case_id,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/cases/{case_id}/offers", response_model=List[Offer])
def get_offers(
    case_id: int,
    db: sqlite3.Connection = Depends(get_db)
):
    """Get all offers for a case"""
    try:
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM offers WHERE case_id = ? ORDER BY received_at DESC",
            (case_id,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/cases/{case_id}/communications", response_model=List[EmailCommunication])
def get_communications(
    case_id: int,
    db: sqlite3.Connection = Depends(get_db)
):
    """Get all email communications for a case"""
    try:
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM email_communications WHERE case_id = ? ORDER BY timestamp DESC",
            (case_id,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/users/{case_id}", response_model=User)
def get_user_by_case(
    case_id: int,
    db: sqlite3.Connection = Depends(get_db)
):
    """Get user info for a case"""
    try:
        cursor = db.cursor()
        cursor.execute("""
            SELECT u.* FROM users u
            JOIN cases c ON c.user_id = u.id
            WHERE c.id = ?
        """, (case_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        return dict(row)
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
```

### Run FastAPI
```bash
cd backend
pip install fastapi uvicorn
uvicorn api_server:app --reload --port 3001
```

### Frontend Integration (lib/api-client.ts)

```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';

export async function getCases(status?: string) {
  const url = status ? `${API_BASE_URL}/api/cases?status=${status}` : `${API_BASE_URL}/api/cases`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch cases');
  return res.json();
}

export async function getCase(caseId: number) {
  const res = await fetch(`${API_BASE_URL}/api/cases/${caseId}`);
  if (!res.ok) throw new Error('Failed to fetch case');
  return res.json();
}

export async function getOffers(caseId: number) {
  const res = await fetch(`${API_BASE_URL}/api/cases/${caseId}/offers`);
  if (!res.ok) throw new Error('Failed to fetch offers');
  return res.json();
}

export async function getCommunications(caseId: number) {
  const res = await fetch(`${API_BASE_URL}/api/cases/${caseId}/communications`);
  if (!res.ok) throw new Error('Failed to fetch communications');
  return res.json();
}

export async function getUserByCase(caseId: number) {
  const res = await fetch(`${API_BASE_URL}/api/users/${caseId}`);
  if (!res.ok) throw new Error('Failed to fetch user');
  return res.json();
}
```

### Update Components
- Replace mock data imports with API calls
- Use React Server Components (fetch in page.tsx)
- Add loading states
- Add error handling

### Phase 2 Deliverables
- ✅ FastAPI server runs on port 3001
- ✅ All endpoints return correct data
- ✅ CORS configured for localhost:3000
- ✅ Frontend fetches real data from API
- ✅ Cases list displays DB data
- ✅ Case detail displays related data

---

## Phase 1: MCP Server Modification (DO LAST)

### Modify backend/mcp_server_incremental.py

**Current main() function location**: End of file (around line 2100)

**Replace the main() function with:**

```python
from mcp.server.fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware

def main():
    """Run MCP server with StreamableHTTP transport (production-ready)"""

    # Get Starlette app from MCP server
    app = mcp.streamable_http_app()

    # Add CORS middleware - required for browser-based clients
    app = CORSMiddleware(
        app,
        allow_origins=["http://localhost:3000"],
        allow_methods=["GET", "POST", "DELETE"],
        allow_credentials=True,
        expose_headers=["Mcp-Session-Id"],  # Critical for session management!
    )

    # Run with streamable-http transport (supersedes SSE)
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8000,
        # Optional: stateless_http=True for better scalability
    )

if __name__ == "__main__":
    main()  # FastMCP handles asyncio internally
```

**Required dependencies:**
```bash
pip install mcp starlette uvicorn
```

**Key improvements over SSE:**
- ✅ Production-ready transport (SSE is deprecated)
- ✅ Better session management with `Mcp-Session-Id` header
- ✅ Supports stateful and stateless modes
- ✅ Better scalability for multiple clients
- ✅ Resumability with event stores

### Frontend MCP Client (lib/mcp-client.ts)

Based on official `@modelcontextprotocol/sdk` (see docs/mcp_client_typescript.md):

```typescript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { Transport } from "@modelcontextprotocol/sdk/shared/transport.js";

/**
 * HTTP Transport for browser-based MCP connections
 * Official SDK handles protocol details, we just provide transport layer
 */
class HTTPTransport implements Transport {
  private baseUrl: string;
  private sessionId: string | null = null;
  private onMessage?: (message: any) => void;
  private onError?: (error: Error) => void;
  private onClose?: () => void;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async start(): Promise<void> {
    // Connection established
  }

  async send(message: any): Promise<void> {
    try {
      const response = await fetch(`${this.baseUrl}/mcp`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(this.sessionId && { 'Mcp-Session-Id': this.sessionId }),
        },
        body: JSON.stringify(message),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // Extract and store session ID
      const newSessionId = response.headers.get('Mcp-Session-Id');
      if (newSessionId) {
        this.sessionId = newSessionId;
      }

      const data = await response.json();
      if (this.onMessage) {
        this.onMessage(data);
      }
    } catch (error) {
      if (this.onError) {
        this.onError(error as Error);
      }
      throw error;
    }
  }

  async close(): Promise<void> {
    this.sessionId = null;
    if (this.onClose) {
      this.onClose();
    }
  }

  setMessageHandler(handler: (message: any) => void): void {
    this.onMessage = handler;
  }

  setErrorHandler(handler: (error: Error) => void): void {
    this.onError = handler;
  }

  setCloseHandler(handler: () => void): void {
    this.onClose = handler;
  }
}

/**
 * MCP Client using official SDK
 * Handles all protocol details automatically
 */
export class MCPClient {
  private client: Client;
  private transport: HTTPTransport;
  private connected: boolean = false;

  constructor(baseUrl: string = process.env.NEXT_PUBLIC_MCP_URL || 'http://localhost:8000') {
    this.transport = new HTTPTransport(baseUrl);
    this.client = new Client(
      {
        name: 'dgro-web-client',
        version: '1.0.0'
      },
      {
        capabilities: {
          tools: {},  // Support tool calls
        }
      }
    );
  }

  async connect(): Promise<void> {
    if (!this.connected) {
      await this.client.connect(this.transport);
      this.connected = true;
    }
  }

  async sendMessage(content: string, history: Array<{role: string, content: string}>): Promise<string> {
    if (!this.connected) {
      await this.connect();
    }

    // Call the 'chat' tool on your MCP server
    const result = await this.client.callTool({
      name: 'chat',
      arguments: {
        message: content,
        history: history,
      },
    });

    // Extract response from tool result
    if (result.content && result.content.length > 0) {
      const firstContent = result.content[0];
      if (firstContent.type === 'text') {
        return firstContent.text;
      }
    }

    return 'No response';
  }

  async disconnect(): Promise<void> {
    if (this.connected) {
      await this.client.close();
      this.connected = false;
    }
  }
}
```

**Required dependencies (frontend/package.json):**
```json
{
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.5.0",
    "@anthropic-ai/sdk": "^0.36.3"
  }
}
```

**Key improvements:**
- ✅ Uses official SDK - no custom protocol implementation
- ✅ Automatic error handling and retries
- ✅ Proper session management
- ✅ Type-safe with official types
- ✅ Benefits from SDK updates

### React Hook (hooks/useMCPChat.ts)

```typescript
'use client';

import { useState, useRef, useEffect } from 'react';
import { MCPClient } from '@/lib/mcp-client';

export function useMCPChat() {
  const [messages, setMessages] = useState<Array<{ role: string; content: string }>>([]);
  const [isLoading, setIsLoading] = useState(false);
  const clientRef = useRef<MCPClient | null>(null);

  // Initialize client once
  useEffect(() => {
    clientRef.current = new MCPClient();
    return () => {
      clientRef.current?.disconnect();
    };
  }, []);

  const sendMessage = async (content: string) => {
    if (!clientRef.current) return;

    setIsLoading(true);
    setMessages(prev => [...prev, { role: 'user', content }]);

    try {
      const response = await clientRef.current.sendMessage(content, messages);
      setMessages(prev => [...prev, { role: 'assistant', content: response }]);
    } catch (error) {
      console.error('MCP chat error:', error);
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, there was an error processing your request. Please try again.'
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
  };

  return { messages, isLoading, sendMessage, clearChat };
}
```

**Package Installation:**
```bash
cd frontend
npm install @modelcontextprotocol/sdk@latest
```

**Testing Steps:**
1. Check imports resolve: `npm run build` (should succeed)
2. Verify official SDK is used (check node_modules/@modelcontextprotocol)
3. Test chat connection works with MCP server
4. Verify session persistence across messages

### Update ChatModal Component

```typescript
'use client';

import { useState } from 'react';
import { useMCPChat } from '@/hooks/useMCPChat';

export function ChatModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const { messages, isLoading, sendMessage, clearChat } = useMCPChat();
  const [input, setInput] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    await sendMessage(input);
    setInput('');
  };

  const handleClose = () => {
    clearChat();
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg w-full max-w-2xl h-[600px] flex flex-col">
        <div className="p-4 border-b flex justify-between items-center">
          <h2 className="text-xl font-semibold">New Case</h2>
          <button onClick={handleClose} className="text-gray-500 hover:text-gray-700">✕</button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg, idx) => (
            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] rounded-lg p-3 ${
                msg.role === 'user'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-900'
              }`}>
                {msg.content}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 rounded-lg p-3">
                <span className="animate-pulse">Thinking...</span>
              </div>
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="p-4 border-t">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Describe what you need..."
              className="flex-1 border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="bg-blue-500 text-white px-6 py-2 rounded-lg hover:bg-blue-600 disabled:bg-gray-300"
            >
              Send
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

### Environment Variables

**Backend .env:**
```
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
GOOGLE_CSE_ID=...
GOOGLE_CREDENTIALS_FILE=credentials.json
```

**Frontend .env.local:**
```
NEXT_PUBLIC_API_URL=http://localhost:3001
NEXT_PUBLIC_MCP_URL=http://localhost:8000
```

### Phase 1 Deliverables
- ✅ MCP server runs on port 8000 with StreamableHTTP transport
- ✅ CORS configured correctly with `Mcp-Session-Id` header exposed
- ✅ MCP client connects from frontend using official SDK
- ✅ ChatModal sends/receives messages
- ✅ 3-agent system works (Consultant → Researcher → Negotiator)
- ✅ Tools execute (search, scrape, email)
- ✅ New cases written to DB via MCP tools
- ✅ Frontend refreshes to show new case

---

## Testing Checklist

### Phase 3
- [ ] `npm run dev` starts frontend on port 3000
- [ ] Cases list renders with mock data
- [ ] Case detail page shows all sections
- [ ] ChatModal opens/closes
- [ ] All components styled correctly
- [ ] Responsive on mobile/tablet/desktop

### Phase 2
- [ ] FastAPI starts on port 3001
- [ ] `/api/cases` returns cases array
- [ ] `/api/cases/{id}` returns single case
- [ ] `/api/cases/{id}/offers` returns offers
- [ ] `/api/cases/{id}/communications` returns emails
- [ ] Frontend displays real DB data
- [ ] No CORS errors in browser console
- [ ] Database connections properly closed (no leaks under load)
- [ ] WAL mode enabled for better concurrency

### Phase 1
- [ ] MCP server starts on port 8000 with streamable-http transport
- [ ] Can POST to `/mcp` endpoint
- [ ] StreamableHTTP transport works (not deprecated SSE)
- [ ] `Mcp-Session-Id` header present in responses
- [ ] ChatModal connects to MCP using official SDK
- [ ] New case creation flow completes
- [ ] Case appears in cases list immediately
- [ ] All 22+ MCP tools still work
- [ ] Email sending works (Gmail API)
- [ ] Search works (Google Custom Search)
- [ ] Scraping works (BeautifulSoup)

---

## Running All Services

**Terminal 1 - FastAPI:**
```bash
cd backend
uvicorn api_server:app --reload --port 3001
```

**Terminal 2 - MCP Server:**
```bash
cd backend
python mcp_server_incremental.py
```

**Terminal 3 - Next.js:**
```bash
cd frontend
npm run dev
```

**Access:**
- Frontend: http://localhost:3000
- FastAPI docs: http://localhost:3001/docs
- MCP endpoint: http://localhost:8000/mcp
