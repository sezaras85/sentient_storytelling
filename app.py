from flask import Flask, render_template, request, jsonify
import requests
import json
import re
import os
from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)

# Kendi API anahtarınızı buraya yazın
API_KEY = os.getenv("API_KEY")
API_ENDPOINT = "https://api.fireworks.ai/inference/v1/completions"
MODEL_NAME = "accounts/sentientfoundation/models/dobby-unhinged-llama-3-3-70b-new"

# Hikaye geçmişini saklayacak bir liste
story_history = []

@app.route('/')
def index():
    return render_template('index.html')

def generate_story_with_dobby(prompt):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "accounts/sentientfoundation/models/dobby-unhinged-llama-3-3-70b-new",
        "prompt": prompt,
        "max_tokens": 500,
        "temperature": 0.5
    }
    
    try:
        response = requests.post(API_ENDPOINT, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        
        completion = response.json()
        raw_text = completion['choices'][0]['text']
        
        # Küfür ve uygunsuz kelimeleri sansürle
        bad_words = ["bitch", "fuck", "shit", "bastard", "idiot", "coward"]
        for word in bad_words:
            raw_text = re.sub(r'\b' + re.escape(word) + r'\b', '[censored]', raw_text, flags=re.IGNORECASE)

        options_match = re.search(r'\n(1\))', raw_text)
        if options_match:
            story_segment_end_index = options_match.start()
            story_segment = raw_text[:story_segment_end_index].strip()
            options_text = raw_text[story_segment_end_index:].strip()
            
            lines = options_text.split('\n')
            cleaned_choices = []
            unique_choices = set()
            for line in lines:
                if re.match(r'\d\)', line) and len(cleaned_choices) < 3:
                    choice_content = line.strip()
                    if choice_content not in unique_choices:
                        unique_choices.add(choice_content)
                        cleaned_choices.append(choice_content)
        else:
            story_segment = raw_text.strip()
            cleaned_choices = [
                "1) Continue the story in a generic way.",
                "2) Try a different path.",
                "3) Stay put and observe."
            ]

        while len(cleaned_choices) < 3:
            choice_num = len(cleaned_choices) + 1
            cleaned_choices.append(f"{choice_num}) Continue the story in a generic way.")
            
        final_output = story_segment + "\n\n" + "\n".join(cleaned_choices)
        
        return final_output
        
    except requests.exceptions.RequestException as e:
        print(f"API isteği hatası: {e}")
        return "Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin."

@app.route('/start_story', methods=['POST'])
def start_story():
    global story_history
    story_history = [] 
    
    user_input = request.json.get('userInput')
    story_type = request.json.get('storyType')
    
    initial_prompt = f"""The user wants to start a story. The genre is {story_type}. The user's opening is: '{user_input}'. 
Continue the story for one paragraph (maximum 100 words). Then, provide EXACTLY 3 distinct and appropriate choices for the next step. 
Each choice should be a short, clear sentence. Label them as 1), 2), and 3). 
Do NOT include any additional text, comments, or rhetorical questions. Ensure the language is neutral and polite. 
Write the response in English."""
    
    bot_response = generate_story_with_dobby(initial_prompt)
    story_history.append(f"User: {user_input}")
    story_history.append(f"Bot: {bot_response}")
    
    return jsonify({"story": bot_response})

@app.route('/continue_story', methods=['POST'])
def continue_story():
    global story_history
    choice = request.json.get('choice')

    if re.match(r'\d\)', choice):
        user_choice_text = choice
        prompt_segment = f"Based on the user's choice '{user_choice_text}'"
    else:
        user_choice_text = f"You continue the story with the idea: '{choice}'"
        prompt_segment = f"Based on the user's custom idea: '{choice}'"

    story_history.append(f"User's choice: {user_choice_text}")
    
    full_story_prompt = "\n".join(story_history) + f"""\n\n{prompt_segment}, continue the story for one paragraph (maximum 100 words). 
Then, provide EXACTLY 3 distinct and appropriate choices for the next step. 
Each choice should be a short, clear sentence. Label them as 1), 2), and 3). 
Do NOT include any additional text, comments, or rhetorical questions. Ensure the language is neutral and polite. 
Write the response in English."""

    bot_response = generate_story_with_dobby(full_story_prompt)
    story_history.append(f"Bot: {bot_response}")
    
    return jsonify({"story": bot_response})

@app.route('/revise_story', methods=['POST'])
def revise_story():
    global story_history
    revision_prompt = request.json.get('revisionPrompt')
    
    last_bot_response = story_history[-1] if story_history else ""
    
    full_revision_prompt = f"""{last_bot_response}\n\nREVISION REQUEST: '{revision_prompt}'. 
Please rewrite the last part of the story (one paragraph, max 100 words) according to this request. 
Remember to keep EXACTLY 3 distinct and appropriate choices at the end, labeled 1), 2), and 3). 
Do NOT include any additional text, comments, or rhetorical questions. The response should be in English."""
    
    revised_response = generate_story_with_dobby(full_revision_prompt)
    
    story_history[-1] = revised_response
    
    return jsonify({"story": revised_response})

@app.route('/get_summary', methods=['GET'])
def get_summary():
    global story_history
    
    summary_prompt = "Summarize the following story so far. The summary should be in English and be no longer than 3-4 sentences. Write the summary in a neutral and polite tone, avoiding any inappropriate language.\n\n" + "\n".join(story_history)
    
    summary_response = generate_story_with_dobby(summary_prompt)
    
    return jsonify({"summary": summary_response})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
