import os
from flask import Flask, render_template, request, jsonify
from tavily import TavilyClient
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Get API keys from environment variables
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Initialize clients ---
try:
    tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
except Exception as e:
    print(f"Error initializing API clients: {e}")
    # Handle this more gracefully in a production app, e.g., redirect to an error page
    exit(1) # Exit if APIs can't be initialized

# Define the two real live sites for demonstration
REAL_SITE_1_NAME = "Rightmove"
REAL_SITE_1_DOMAIN = "rightmove.co.uk" # Used to target Tavily searches
REAL_SITE_2_NAME = "SDL Property Auctions"
REAL_SITE_2_DOMAIN = "sdlauctions.co.uk" # Used to target Tavily searches

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        user_query = request.form["query"]
        if not user_query:
            return render_template("index.html", error="Please enter a query.")

        search_results = []
        ai_response = ""
        error_message = None

        try:
            # Step 1: Use Tavily to search for property information on the real sites

            # Search Rightmove
            # Formulate the query to encourage Tavily to search within Rightmove's domain
            tavily_query_rightmove = f"{user_query} site:{REAL_SITE_1_DOMAIN}"
            print(f"Tavily Query ({REAL_SITE_1_NAME}): {tavily_query_rightmove}")
            response_rightmove = tavily_client.search(query=tavily_query_rightmove, search_depth="basic", max_results=3)

            if response_rightmove and response_rightmove.get('results'):
                for result in response_rightmove['results']:
                    search_results.append({
                        "source": REAL_SITE_1_NAME,
                        "title": result.get('title', 'No Title'),
                        "url": result.get('url', '#'),
                        "content": result.get('content', 'No content available.')
                    })

            # Search SDL Property Auctions
            # Formulate the query to encourage Tavily to search within SDL's domain
            tavily_query_sdl = f"{user_query} site:{REAL_SITE_2_DOMAIN}"
            print(f"Tavily Query ({REAL_SITE_2_NAME}): {tavily_query_sdl}")
            response_sdl = tavily_client.search(query=tavily_query_sdl, search_depth="basic", max_results=3)

            if response_sdl and response_sdl.get('results'):
                for result in response_sdl['results']:
                    search_results.append({
                        "source": REAL_SITE_2_NAME,
                        "title": result.get('title', 'No Title'),
                        "url": result.get('url', '#'),
                        "content": result.get('content', 'No content available.')
                    })

            if not search_results:
                ai_response = f"No highly relevant property information found from {REAL_SITE_1_NAME} or {REAL_SITE_2_NAME} for your query."
            else:
                # Step 2: Use OpenAI to summarize and provide insights
                # Create a prompt for OpenAI based on the search results
                context_for_openai = "Here are some search results from various UK property sites:\n\n"
                for i, result in enumerate(search_results):
                    context_for_openai += f"--- Result {i+1} from {result['source']} ---\n"
                    context_for_openai += f"Title: {result['title']}\n"
                    context_for_openai += f"URL: {result['url']}\n"
                    context_for_openai += f"Content: {result['content'][:800]}...\n\n" # Truncate content for brevity

                openai_prompt = f"Based on the following UK property information, answer the user's query: '{user_query}'. " \
                                f"Focus on identifying potential property opportunities for investors in the UK. " \
                                f"Summarize findings and highlight key details like property types, price indications, locations, and potential uses (e.g., HMO, development, auction opportunity). " \
                                f"If no direct listings are found but relevant articles are, mention that. Prioritize concrete property details if available.\n\n" \
                                f"{context_for_openai}\n\n" \
                                f"Please provide a concise and helpful response for an investor, strictly based on the provided search results. If the search results are not enough to answer, state that."

                print(f"\nOpenAI Prompt (truncated for display):\n{openai_prompt[:1500]}...") # Print truncated prompt

                chat_completion = openai_client.chat.completions.create(
                    model="gpt-3.5-turbo", # You can use a more advanced model like "gpt-4o" if available/preferred
                    messages=[
                        {"role": "system", "content": "You are a helpful AI assistant specializing in UK property investment. Provide concise and relevant insights based on the provided search data."},
                        {"role": "user", "content": openai_prompt}
                    ],
                    max_tokens=600 # Adjust as needed
                )
                ai_response = chat_completion.choices[0].message.content

        except Exception as e:
            error_message = f"An error occurred: {e}. Please check your API keys, network connection, or try a different query."
            print(f"Error: {e}")

        return render_template("index.html",
                               query=user_query,
                               ai_response=ai_response,
                               search_results=search_results,
                               error=error_message,
                               site1_name=REAL_SITE_1_NAME,
                               site2_name=REAL_SITE_2_NAME)

    return render_template("index.html",
                           query="",
                           ai_response="",
                           search_results=[],
                           error=None,
                           site1_name=REAL_SITE_1_NAME,
                           site2_name=REAL_SITE_2_NAME)

if __name__ == "__main__":
    app.run(debug=True)
