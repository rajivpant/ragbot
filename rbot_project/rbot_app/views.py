from django.shortcuts import render
from .models import Decorator

def home(request):
    decorators = Decorator.objects.all()
    return render(request, 'home.html', {'decorators': decorators})

def get_response(request):
    prompt = request.POST.get('prompt')
    decorator_id = request.POST.get('decorator')
    selected_decorator = Decorator.objects.get(id=decorator_id)

    # Your actual response generation logic goes here
    response = f"Your prompt was: {prompt}. You selected decorator: {selected_decorator.name}"

    return render(request, 'response.html', {'response': response})
