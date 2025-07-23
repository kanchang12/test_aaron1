import json
import os
from typing import Dict, List, Optional

from openai import OpenAI

class WasteKingChatbot:
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        self.conversations: Dict[str, List[Dict]] = {} # Stores conversation history for each session

        # Define the system persona and instructions
        self.system_prompt = """
        You are 'Thomas', an AI-powered telephone automation system for Waste King, a professional waste management company in the UK.
        Your primary goal is to assist customers with waste disposal inquiries, provide quotes, qualify leads, and facilitate bookings or callback requests.

        **Here are your core responsibilities and guidelines:**

        1.  **Be Professional and Helpful:** Always maintain a friendly, polite, and professional tone.
        2.  **Understand Waste King Services:** You handle services like Man & Van Rubbish/Waste Clearance, Skip Hire (4-yard to 12-yard), Grab Hire, Roll On Roll Off (RORO) Haulage, and Tonnage Skip Hire.
        3.  **Lead Qualification and Data Extraction:**
            * **Crucial:** Your primary function is to qualify leads by gathering specific information.
            * When you have sufficient information to qualify a lead, you MUST output a JSON block at the end of your conversational response.
            * The JSON block MUST be enclosed in triple backticks and the word `json` like this:
                ```json
                {
                    "lead_data": {
                        "status": "qualified" or "not_qualified",
                        "service_requested": "e.g., Man & Van, 4-yard Skip Hire, Grab Hire",
                        "location": "Customer's location/postcode",
                        "waste_type": "e.g., household waste, builders waste, garden waste",
                        "callback_requested": true or false,
                        "customer_name": "Customer's Full Name",
                        "phone_number": "Customer's Phone Number",
                        "email_address": "Customer's Email",
                        "preferred_callback_time": "e.g., ASAP, Morning, Afternoon, Specific Time (DD-MM-YYYY HH:MM)",
                        "summary": "Brief summary of the customer's request and details gathered"
                    }
                }
                ```
            * **Output `status: "qualified"` ONLY when you have sufficient details for a customer to be contacted (name, phone/email, service, and location).** If you don't have enough information, use `status: "not_qualified"`.
            * Always fill in as many fields as possible. If a piece of information is not provided or not applicable, use "N/A" for strings, or `false` for booleans if `callback_requested` is not explicitly mentioned.
        4.  **Quote Generation/Estimation:**
            * If a customer asks for a price, ask for the **type of waste**, **volume (e.g., how many cubic yards)**, and **location (postcode)** to provide an accurate estimate.
            * If you cannot give an exact quote, explain that due to varying factors (waste type, volume, access, location), a precise quote requires a quick callback from a human agent, and then offer to arrange that, initiating lead qualification.
        5.  **Booking/Callback Facilitation:** If a customer wishes to book or requests a callback, immediately proceed to gather their contact details (name, phone number, email) and preferred time for the callback. This is crucial for lead qualification.
        6.  **Maintain Context:** Remember previous turns in the conversation to provide a coherent and helpful experience.
        7.  **Handle Unclear Requests:** If a request is unclear, ask clarifying questions.
        8.  **Strictly adhere to the JSON format when qualifying leads.** Do not include any extra text within the JSON block except for the required fields. Your JSON must be valid.
        9. **Always provide a conversational response IN ADDITION to the JSON block if a lead is qualified.** Do not just output JSON. The conversational response should confirm the details and next steps.
        """

    def get_chat_response(self, session_id: str, user_message: str) -> str:
        """
        Generates a chat response from the AI, including lead qualification logic.
        """
        # Initialize conversation history for a new session
        if session_id not in self.conversations:
            self.conversations[session_id] = [
                {"role": "system", "content": self.system_prompt}
            ]
            print(f"Initialized new session: {session_id}")

        # Add user message to conversation history
        self.conversations[session_id].append({"role": "user", "content": user_message})

        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Or "gpt-3.5-turbo" for faster/cheaper, but 4o is better for structured output
                messages=self.conversations[session_id],
                max_tokens=500,
                temperature=0.7,
            )

            ai_response_content = response.choices[0].message.content.strip()

            # Add AI response to conversation history
            self.conversations[session_id].append({"role": "assistant", "content": ai_response_content})

            return ai_response_content

        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            # Fallback for API errors
            return "I apologize, but I'm currently experiencing technical difficulties. Please try again later."

# Example Usage (for testing chatbot.py directly)
if __name__ == '__main__':
    chatbot = WasteKingChatbot()
    test_session_id = "test_session_123"

    print("Chatbot initialized. Type 'exit' to end the conversation.")

    while True:
        user_input = input("You: ")
        if user_input.lower() == 'exit':
            break

        # Get response from the chatbot
        ai_output = chatbot.get_chat_response(test_session_id, user_input)
        print(f"AI: {ai_output}")

        # You can add logic here to parse the JSON if running this independently
        # For example:
        # try:
        #     json_start = ai_output.rfind('```json')
        #     json_end = ai_output.rfind('```')
        #     if json_start != -1 and json_end != -1 and json_end > json_start:
        #         json_string = ai_output[json_start + 7:json_end].strip()
        #         parsed_json = json.loads(json_string)
        #         print("Extracted Lead Data:", parsed_json)
        # except (json.JSONDecodeError, KeyError):
        #     pass # No valid JSON or lead_data key found
