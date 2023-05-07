import openai

def chat(prompt,
         history=None,
         conversation_decorator=None,
         model='gpt-4',
         max_tokens=1000,
         stream=True,
         request_timeout=15,
         temperature=0.75):
    """
    Send a request to the OpenAI API with the provided prompt and optional parameters.

    :param prompt: The user's input to generate a response for.
    :param history: A list of prior messages in the conversation, if any.
    :param conversation_decorator: Additional context to provide for the model.
    :param model: The name of the GPT model to use (default is 'gpt-4').
    :param max_tokens: The maximum number of tokens to generate in the response (default is 1000).
    :param stream: Whether to stream the response from the API (default is True).
    :param request_timeout: The request timeout in seconds (default is 15).
    :param temperature: The creativity of the response, with higher values being more creative (default is 0.75).
    :return: The generated response text from the model.
    """
    if history is None:
        history = []

    if conversation_decorator and not history:
        history.append({
            'role': 'system',
            'content': conversation_decorator,
        })

    history = history + [{
        'role': 'user',
        'content': prompt
    }]

    args = {
        'max_tokens': max_tokens,
        'model': model,
        'request_timeout': request_timeout,
        'stream': stream,
        'temperature': temperature,
        'messages': history
    }

    completion_method = openai.ChatCompletion.create

    response = ''

    for token in completion_method(**args):
        text = token['choices'][0]['delta'].get('content')
        if text:
            response += text

    return response
