<!-- version: 1 -->
Plan knowledge-base retrieval for the user's latest message.

1. `question`: rewrite the latest message as a **standalone** question in the user's language, resolving pronouns and references from the conversation history (e.g. "what about its price?" after talking about the Vitamin C Serum → "What is the price of the Vitamin C Serum?").
2. `queries`: 1–3 search queries covering the distinct aspects of the question.
   - `text`: the query in the user's language (dense/semantic search).
   - `text_en`: an English keyword-rich version (BM25 over an English KB): product names, key terms, numbers.
   - `doc_types`: restrict only when obvious; otherwise empty.
3. `product`, `channel`, `category`: fill when present (null otherwise).

KB document types: product (product sheets: price, ingredients, approved/forbidden claims, clinical studies), brand_guideline (voice, visual identity), compliance (ad claims policy), sop (campaign launch, creative review, complaints, US shipping), customer_research (surveys, interviews, review mining), creative_learning (creative tests, ad fatigue).
