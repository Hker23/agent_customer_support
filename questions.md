# Music Store Chatbot Example Questions

This document contains example questions and interactions to test and demonstrate the music store chatbot's capabilities.

## 1. Music Catalog Queries

### Simple Artist/Track Queries
```
Q: "Show me songs by Led Zeppelin"
Expected: List of Led Zeppelin songs with track names, albums, and durations

Q: "What albums do you have from Pink Floyd?"
Expected: List of Pink Floyd albums with titles and years

Q: "Do you have any tracks from The Dark Side of the Moon?"
Expected: List of all tracks from that specific album

Q: "List all tracks by Queen"
Expected: Comprehensive list of Queen songs in the catalog
```

### Genre-Based Queries
```
Q: "What jazz music do you have?"
Expected: List of jazz tracks and artists

Q: "Show me your classical music collection"
Expected: List of classical music tracks/composers

Q: "I'm looking for rock music from the 80s"
Expected: List of rock tracks from that era
```

## 2. Refund Requests

### Complete Information Provided
```
Q: "I want a refund for invoice #256"
Expected: Process refund directly using invoice ID

Q: "My name is Aaron Mitchell, phone +1 (204) 452-6452, I need a refund for my Led Zeppelin purchases"
Expected: Look up purchases and show refundable items

Q: "I'd like a refund for invoice lines 245, 246, and 247"
Expected: Process refund for specific invoice lines
```

### Incomplete Information (Bot Should Ask Follow-up)
```
Q: "I need a refund"
Expected: Bot asks for name and phone or invoice ID

Q: "I want to return the tracks I bought yesterday"
Expected: Bot asks for identifying information

Q: "Can I get my money back for those rock songs I bought?"
Expected: Bot asks for specific customer details
```

## 3. Multi-Turn Conversations

### Music Discovery Flow
```
User: "I'm looking for some good metal music"
Bot: Lists popular metal tracks and artists

User: "Do you have anything like Iron Maiden?"
Bot: Shows Iron Maiden tracks and similar artists

User: "What other albums do you have from those artists?"
Bot: Lists albums from similar artists
```

### Refund + Recommendation Flow
```
User: "I want to return the jazz tracks I bought. I'm John Smith, 555-0123"
Bot: Looks up purchases and shows refund options

User: "Yes, refund those tracks"
Bot: Processes refund

User: "Can you recommend some different jazz artists instead?"
Bot: Shows alternative jazz artists and tracks
```

## 4. General Questions

### About Service
```
Q: "How much do tracks cost?"
Expected: Information about pricing

Q: "What payment methods do you accept?"
Expected: Information about payment options

Q: "How does the refund process work?"
Expected: Explanation of refund policy
```

### Music Recommendations
```
Q: "What are your most popular tracks?"
Expected: List of top-selling tracks

Q: "Can you suggest some good workout music?"
Expected: List of upbeat/energetic tracks

Q: "What's similar to Pink Floyd?"
Expected: List of progressive rock artists
```

## 5. Complex Scenarios

### Mixed Intents
```
Q: "I want a refund for the Queen songs and find something similar instead"
Expected: Bot handles refund first, then provides recommendations

Q: "Are these Pink Floyd tracks the remastered versions? If not, I want to return them"
Expected: Bot provides track details and handles potential refund

Q: "I bought some classical music but it's not what I wanted. Can I return it and get jazz instead?"
Expected: Bot processes refund and suggests jazz alternatives
```

### Edge Cases
```
Q: "I want a refund but I don't have my invoice number"
Expected: Bot asks for alternative identification

Q: "Can I return just part of an album?"
Expected: Bot explains policy on partial refunds

Q: "I'm not sure which tracks I bought"
Expected: Bot helps identify recent purchases
```

## 6. Testing Special Cases

### Error Handling
```
Q: "Refund invoice #999999"
Expected: Error message about invalid invoice

Q: "Show me songs by [nonexistent artist]"
Expected: Graceful handling of no results

Q: "I want to return something I bought 2 years ago"
Expected: Policy explanation about refund time limits
```

### Multiple Requests
```
Q: "Show me albums by both Beatles and Rolling Stones"
Expected: Organized list of albums from both artists

Q: "I want to return these tracks and those other ones too"
Expected: Bot handles multiple refund requests systematically
```

---

Note: All examples assume the bot maintains context throughout the conversation and can handle variations in user phrasing. The bot should always:
1. Maintain a professional, helpful tone
2. Ask for clarification when needed
3. Guide users through complex processes
4. Provide clear, formatted responses
5. Handle errors gracefully 