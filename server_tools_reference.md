# MCP Server Tools Reference

## Available Tools for iOS Client

Based on the `mcp_server_incremental.py` implementation, here are the tools exposed by the server that your iOS client can call:

### Case Management Tools

#### 1. `create_case`
Create a new case record in the database
```json
{
  "subject": "string",
  "features": "string",
  "location": "string",
  "budget": number,
  "timeline": "string",
  "additional_features": "string"
}
```

#### 2. `update_case`
Update an existing case record
```json
{
  "case_id": number,
  "subject": "string",
  "features": "string",
  "location": "string",
  "budget": number,
  "timeline": "string",
  "additional_features": "string"
}
```

#### 3. `get_case`
Retrieve a case by ID
```json
{
  "case_id": number
}
```

### User Management Tools

#### 4. `create_user`
Create a new user record
```json
{
  "case_id": number,
  "name": "string",
  "email": "string",
  "phone": "string"
}
```

#### 5. `update_user`
Update an existing user record
```json
{
  "user_id": number,
  "case_id": number,
  "name": "string",
  "email": "string",
  "phone": "string"
}
```

#### 6. `get_user`
Retrieve a user by case ID
```json
{
  "case_id": number
}
```

### Search Tools

#### 7. `create_search`
Create a new search record
```json
{
  "case_id": number,
  "search_goal": "string",
  "search_query": "string",
  "search_results": "string"
}
```

#### 8. `execute_google_search`
Execute a Google Custom Search
```json
{
  "case_id": number,
  "query": "string"
}
```

#### 9. `scrape_website_contacts`
Scrape contact information from websites
```json
{
  "case_id": number,
  "websites": ["string"]
}
```

### Email Communication Tools

#### 10. `send_email_to_vendor`
Send an initial outreach email to a vendor
```json
{
  "case_id": number,
  "vendor_email": "string",
  "vendor_name": "string",
  "vendor_website": "string",
  "subject": "string",
  "message": "string"
}
```

#### 11. `get_unread_vendor_emails`
Check for new responses from vendors
```json
{
  "case_id": number
}
```

#### 12. `reply_to_vendor_email`
Reply to a vendor's email
```json
{
  "case_id": number,
  "vendor_email": "string",
  "message_id": "string",
  "thread_id": "string",
  "message": "string"
}
```

#### 13. `mark_email_as_read`
Mark emails as read after processing
```json
{
  "message_ids": ["string"]
}
```

#### 14. `get_email_thread`
View the full conversation with a vendor
```json
{
  "case_id": number,
  "vendor_email": "string"
}
```

#### 15. `get_case_communications`
View all communications for a specific case
```json
{
  "case_id": number
}
```

### Offer Management Tools

#### 16. `create_offer`
Create a new offer record in the database
```json
{
  "case_id": number,
  "price": number,
  "timeline": "string",
  "accuracy": number,
  "additional_details": "string",
  "communication_thread_id": "string",
  "vendor_email": "string"
}
```

#### 17. `update_offer`
Update an existing offer record
```json
{
  "offer_id": number,
  "status": "pending|active|accepted|rejected|expired",
  "price": number,
  "timeline": "string",
  "accuracy": number,
  "additional_details": "string"
}
```

#### 18. `get_offer`
Get an offer record from the database
```json
{
  "offer_id": number
}
```

#### 19. `get_case_offers`
Get all offers for a specific case
```json
{
  "case_id": number
}
```

## System Prompt

The server also exposes a system prompt that describes the multi-agent system behavior:
- **Consultant Agent**: Gathers user requirements and creates cases
- **Researcher Agent**: Finds vendors and scrapes contact information
- **Negotiator Agent**: Manages email communications and tracks offers

## Usage in iOS Client

When implementing the iOS client, you'll:

1. **List available tools** on connection:
```swift
let (tools, _) = try await client.listTools()
```

2. **Call tools** as needed:
```swift
let result = try await client.callTool(
    name: "create_case",
    arguments: [
        "subject": "Website Development",
        "features": "E-commerce, payment integration",
        "location": "San Francisco",
        "budget": 50000,
        "timeline": "3 months",
        "additional_features": "Mobile responsive"
    ]
)
```

3. **Process results** from tool calls:
```swift
// Results come back as content blocks
for item in result.content {
    switch item {
    case .text(let text):
        print("Result: \(text)")
    default:
        break
    }
}
```

## Database Schema Reference

The tools interact with these database tables:
- **cases**: Main case records
- **users**: User information linked to cases
- **searches**: Search history and results
- **email_communications**: Email threads with vendors
- **offers**: Vendor offers with status tracking

## Notes for Implementation

1. All tool calls are asynchronous
2. Tools may return errors - handle appropriately
3. Some tools require case_id - maintain state in your app
4. Email tools require Gmail OAuth setup on server side
5. Google Search requires API key configuration on server
