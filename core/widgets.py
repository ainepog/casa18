from django.forms.widgets import ClearableFileInput
from django.utils.html import format_html


class CustomFileWidget(ClearableFileInput):
    template_name = None

    def render(self, name, value, attrs=None, renderer=None):
        form_id = "agendapagos_form"

        if value and hasattr(value, 'url'):
            filename = value.name.split('/')[-1]

            return format_html(
                '''
                <div style="display: flex; align-items: center; gap: 15px; background: #fff; padding: 10px; border: 1px solid #ced4da; border-radius: 4px; max-width: 550px;">
                    <a href="{url}" target="_blank" title="Ver archivo">
                        <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#007bff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                    </a>

                    <span style="flex-grow: 1; color: #495057; font-size: 0.9rem; font-family: monospace;">{filename}</span>

                    <label style="margin:0; cursor:pointer;" title="Eliminar">
                        <input type="checkbox" name="{clear_name}" id="{clear_id}" style="display:none;" 
                               onchange="if(this.checked) document.getElementById('{form_id}').submit();"> 
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#dc3545" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </label>

                    <label style="margin:0; cursor:pointer;" title="Cambiar">
                        <input type="file" name="{name}" id="{id}" style="display:none;" 
                               onchange="document.getElementById('{form_id}').submit();"> 
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#007bff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2v6h-6"></path><path d="M3 12a9 9 0 0 1 15-6.7L21 8"></path><path d="M3 22v-6h6"></path><path d="M21 12a9 9 0 0 1-15 6.7L3 16"></path></svg>
                    </label>
                </div>
                ''',
                url=value.url,
                filename=filename,
                clear_name=self.clear_checkbox_name(name),
                clear_id=self.clear_checkbox_id(self.clear_checkbox_name(name)),
                name=name,
                id=attrs.get('id', name),
                form_id=form_id
            )

        return format_html(
            '''
            <label style="cursor: pointer; display: inline-flex; align-items: center; gap: 10px; background: #f0faff; border: 1px dashed #007bff; padding: 10px 20px; border-radius: 4px; color: #007bff; font-weight: bold;">
                <input type="file" name="{name}" id="{id}" style="display: none;" 
                       onchange="document.getElementById('{form_id}').submit();">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#007bff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                <span>Seleccionar Constancia</span>
            </label>
            ''',
            name=name,
            id=attrs.get('id', name),
            form_id=form_id
        )