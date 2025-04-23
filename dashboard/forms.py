from django import forms
from .models import DataUpload, UserRegistration
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field, Div

class DataUploadForm(forms.ModelForm):
    class Meta:
        model = DataUpload
        fields = ['title', 'description', 'file']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_enctype = "multipart/form-data"
        
        # Using a simpler layout that's more compatible with standard Bootstrap 4
        self.helper.layout = Layout(
            Div(
                Div(Field('title'), css_class='col-md-6'),
                Div(Field('file'), css_class='col-md-6'),
                css_class='row'
            ),
            Field('description', rows="4"),
            Div(
                Submit('submit', 'Upload', css_class='btn-primary px-4'),
                css_class='mt-3'
            )
        )
    
    def clean_file(self):
        file = self.cleaned_data.get('file', False)
        if file:
            # Ensure the file is an Excel file
            ext = file.name.split('.')[-1]
            if ext.lower() not in ['xlsx', 'xls', 'csv']:
                raise forms.ValidationError("Only Excel files (xlsx, xls) or CSV files are allowed.")
        return file

class UserRegistrationForm(forms.ModelForm):
    """Form for user registration"""
    
    # Add confirmation fields
    confirm_email = forms.EmailField(
        label="Confirm Email",
        required=True
    )
    
    class Meta:
        model = UserRegistration
        fields = ['full_name', 'citizen_id', 'phone_number', 'email']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'form-horizontal'
        
        self.helper.layout = Layout(
            Div(
                Div(Field('full_name'), css_class='col-md-6'),
                Div(Field('citizen_id'), css_class='col-md-6'),
                css_class='row'
            ),
            Div(
                Div(Field('phone_number'), css_class='col-md-6'),
                Div(Field('email'), css_class='col-md-6'),
                css_class='row'
            ),
            Div(
                Div(Field('confirm_email'), css_class='col-md-6'),
                css_class='row'
            ),
            Div(
                Submit('submit', 'Register', css_class='btn-primary px-4'),
                css_class='mt-3'
            )
        )
        
    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        confirm_email = cleaned_data.get('confirm_email')
        
        if email and confirm_email and email != confirm_email:
            self.add_error('confirm_email', "The email addresses must match.")
        
        return cleaned_data
        
    def clean_citizen_id(self):
        citizen_id = self.cleaned_data.get('citizen_id')
        
        # Check if citizen ID is unique
        if UserRegistration.objects.filter(citizen_id=citizen_id).exists():
            raise forms.ValidationError("This Citizen ID is already registered.")
        
        return citizen_id