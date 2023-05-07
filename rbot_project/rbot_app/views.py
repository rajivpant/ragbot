from django.shortcuts import render
from django.http import JsonResponse
from .utils import chat  # You'll create this function in the next step

def rbot_view(request):
    if request.method == 'POST':
        prompt = request.POST.get('prompt', '')
        decorator = request.POST.get('decorator', '')
        # Call the chat function from the original rbot.py script
        response = chat(prompt=prompt, conversation_decorator=decorator)
        return JsonResponse({'response': response})
    return render(request, 'rbot_app/rbot.html')  # You'll create this template in step 7
