import google.generativeai as genai
import os
import json
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# model = genai.GenerativeModel('gemini-pro')
model = genai.GenerativeModel('gemini-flash-latest')

async def evaluate_submission(task_title: str, task_description: str, submitted_content: str):
    # Deterministic check based on frontend validation
    if "/* STATUS:PASSED */" in submitted_content:
        return {
            "score": 100,
            "is_correct": True,
            "feedback": "Great job! All tests passed successfully.",
            "detailed_feedback": [
                {"type": "strength", "content": "Correct implementation matching all requirements."}
            ],
            "course_recommendations": [
                {"title": "Advanced Design Patterns", "provider": "Coursera", "justification": "Master advanced architecture patterns to build even more robust systems."}
            ]
        }
    
    if "/* STATUS:FAILED */" in submitted_content:
        return {
            "score": 0,
            "is_correct": False,
            "feedback": "Tests failed. Please check the console output and try again.",
            "detailed_feedback": [
                {"type": "improvement", "content": "The solution did not pass the automated tests."}
            ],
            "course_recommendations": [
                {"title": "Web Development Bootcamp", "provider": "Udemy", "justification": "Review core web development concepts to strengthen your fundamentals."}
            ]
        }

    # Fallback to Gemini if no status marker (or legacy submissions)
    if not os.getenv("GEMINI_API_KEY"):
         return {
            "score": 0,
            "is_correct": False,
            "feedback": "AI Evaluation unavailable (Missing API Key). However, manual review will be pending.",
            "detailed_feedback": []
        }

    prompt = f"""
    You are an expert technical interviewer and mentor. 
    Evaluate the following submission for the task: "{task_title}".
    
    Task Description:
    {task_description}
    
    User Submission:
    {submitted_content}
    
    Provide your evaluation in strict JSON format. The JSON object must have the following keys:
    - "score": Integer from 0 to 100.
    - "is_correct": Boolean indicating if the solution is functional and correct.
    - "feedback": A detailed string summary of the evaluation.
    - "detailed_feedback": A list of objects, each with "type" ("strength" or "improvement") and "content" (string).
    - "course_recommendations": A list of objects, each with "title" (string), "provider" (string), and "justification" (briefly explaining how it addresses their specific weakness detected in this task).

    
    JSON Response:
    """
    
    print(f"DEBUG: evaluate_submission called for task: {task_title}")
    
    try:
        print(f"DEBUG: Calling Gemini model: {model.model_name}")
        response = model.generate_content(prompt)
        print(f"DEBUG: Gemini response received. Text length: {len(response.text)}")
        text = response.text
        # Cleanup potential markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
            
        result = json.loads(text)
        print(f"DEBUG: Parsed result: {result}")
        return result
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
             return {
                "score": 0,
                "is_correct": False,
                "feedback": "AI Evaluation Quota Exceeded. Please try again later or check your API key limits.",
                "detailed_feedback": []
            }
        
        return {
            "score": 0,
            "is_correct": False,
            "feedback": f"Error evaluating submission with AI: {error_msg[:100]}...",
            "detailed_feedback": []
        }
