import json

import boto3

from config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    BEDROCK_REGION,
    BEDROCK_MODEL_ID,
)


def _get_bedrock_client():
    return boto3.client(
        "bedrock-runtime",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=BEDROCK_REGION,
    )


def ask_llm(question: str, context_chunks: list[str], chat_history: list[dict] = None) -> str:
    """Send a question + retrieved context to Bedrock and get an answer.
    
    Cost-saving measures:
    - max_tokens capped at 512 (shorter answers = less output cost)
    - Context chunks truncated to 500 chars each to reduce input tokens
    - Only top-3 chunks sent (fewer input tokens)
    """
    client = _get_bedrock_client()

    # Truncate each chunk to save input tokens
    trimmed = [c[:500] for c in context_chunks[:3]]
    context = "\n\n---\n\n".join(trimmed)

    # Build conversation history string
    history_str = ""
    if chat_history:
        # Keep last 4 exchanges to stay within token budget
        recent = chat_history[-4:]
        pairs = []
        for h in recent:
            pairs.append(f"User: {h['question']}\nAssistant: {h['answer'][:300]}")
        history_str = "\n\n".join(pairs)

    prompt = f"""Answer the question using ONLY the context below. Be concise and clear.
The context may contain OCR artifacts or formatting noise — ignore garbled text and focus on readable content.
If the answer is not in the context, say "I couldn't find that in the document."

Context:
{context}"""

    if history_str:
        prompt += f"""\n\nPrevious conversation (use for understanding follow-up questions):
{history_str}"""

    prompt += f"""\n\nQuestion: {question}\n\nAnswer:"""

    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 512,
            "messages": [{"role": "user", "content": prompt}],
        }
    )

    response = client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=body,
        contentType="application/json",
        accept="application/json",
    )

    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def generate_followups(question: str, answer: str, context_chunks: list[str]) -> list[str]:
    """Generate 3 follow-up question suggestions based on the Q&A and context."""
    client = _get_bedrock_client()

    context_brief = " ".join(c[:200] for c in context_chunks[:2])

    prompt = f"""Based on this Q&A about a document, suggest exactly 3 short follow-up questions the user might ask next.
Return ONLY the 3 questions, one per line, numbered 1-3. No explanations.

Document context: {context_brief}

Q: {question}
A: {answer[:300]}

Follow-up questions:"""

    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 150,
            "messages": [{"role": "user", "content": prompt}],
        }
    )

    try:
        response = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        raw = result["content"][0]["text"].strip()
        # Parse numbered lines into a clean list
        lines = [l.strip().lstrip("0123456789.").strip() for l in raw.split("\n") if l.strip()]
        return [l for l in lines if l][:3]
    except Exception:
        return []


def chat_general(question: str) -> str:
    """Handle greetings and general questions without document context."""
    client = _get_bedrock_client()

    prompt = f"""You are a friendly PDF Q&A assistant. The user has uploaded documents and can ask questions about them.
If the user greets you, greet them back warmly and briefly explain what you can do.
If the user asks a general question, answer it briefly.
Keep responses short and friendly.

User: {question}

Assistant:"""

    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 256,
            "messages": [{"role": "user", "content": prompt}],
        }
    )

    response = client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=body,
        contentType="application/json",
        accept="application/json",
    )

    result = json.loads(response["body"].read())
    return result["content"][0]["text"]
