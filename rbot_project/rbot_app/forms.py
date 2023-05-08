from django import forms

class RbotForm(forms.Form):
    message = forms.CharField(label='Your message', max_length=1000, widget=forms.Textarea(attrs={'rows': 4, 'cols': 50}))
    decorator = forms.ChoiceField(choices=[('none', 'None'), ('bold', 'Bold'), ('italic', 'Italic'), ('underline', 'Underline')])
