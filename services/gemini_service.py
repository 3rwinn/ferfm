from google import genai
from core.settings import GEMINI_API_KEY


def generate_answer(user_question, knowledge_snippets):
    """Generates an answer using the Gemini model."""

    client = genai.Client(api_key=GEMINI_API_KEY)

    # model = genai.GenerativeModel('gemini-pro')

    prompt = f"""
    INSTRUCTIONS: You are a helpful virtual assistant providing support in FRENCH. Base your answers solely on the provided knowledge base.
    Always refer to the knowledge base as "your knowledge" don't call it documents or anything else.

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
