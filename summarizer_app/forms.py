# summarizer_app/forms.py
from django import forms

class UploadEmailFileForm(forms.Form):
    email_file = forms.FileField(label="Upload Email File")
