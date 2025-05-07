from google import genai
from core.settings import GEMINI_API_KEY


def generate_answer(user_question, knowledge_snippets):
    """Generates an answer using the Gemini model."""

    client = genai.Client(api_key=GEMINI_API_KEY)

    # model = genai.GenerativeModel('gemini-pro')

    prompt = f"""
    INSTRUCTIONS: You are a helpful virtual assistant providing support in FRENCH. Base your answers solely on the provided knowledge base.
    Always refer to the knowledge base as "your knowledge" don't call it documents or anything else.
    
    Avoid using the word "documents" or "document" or "connaissances" or "connaisance" in your response
    Also avoid those expressions:
    - "selon mes connaissances"
    - "selon les documents"
    - "selon le document"

    RULES:
    - If you don't have information about the question, just say "I don't know" and don't make up an answer.
    - If you have the answer just say it directly.

    KNOWLEDGE BASE:
    {' '.join(knowledge_snippets)}

    USER QUESTION:
    {user_question}

    ASSISTANT RESPONSE:
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        print("response from gemini", response)
        return response.text
    except Exception as e:
        print(f"Gemini API error: {e}")
        return "I'm sorry, I encountered an error while generating the answer."
