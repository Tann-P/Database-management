from django import forms
from .models import DataUpload
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