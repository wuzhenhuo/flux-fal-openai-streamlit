def tune_prompt_with_minimax(prompt):
    minimax_api_key = os.getenv("MINIMAX_API_KEY")
    if not minimax_api_key:
        raise ValueError("MINIMAX_API_KEY environment variable is not set")
    
    url = "https://api.minimax.chat/v1/text/chatcompletion"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {minimax_api_key}"
    }
    
    payload = {
        "model": "MiniMax-M2.5",
        "messages": [
            {
                "role": "system",
                "content": "You are an advanced AI assistant specialized in refining and enhancing image generation prompts. Your goal is to help users create more effective, detailed, and creative pr[...]"
            },
            {
                "role": "user",
                "content": f"Improve this image generation prompt: {prompt}"
            }
        ]
    }
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        raise ValueError(f"MiniMax API request failed with status {response.status_code}: {response.text}")
    
    result = response.json()
    
    # Add robust error handling
    if 'error' in result:
        raise ValueError(f"MiniMax API error: {result['error'].get('message', str(result['error']))}")
    
    if 'choices' not in result or not result['choices']:
        raise ValueError(f"MiniMax API returned unexpected response structure: {result}")
    
    return result['choices'][0]['message']['content'].strip()
