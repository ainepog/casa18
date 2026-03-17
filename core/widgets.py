from django.forms.widgets import ClearableFileInput
from django.utils.html import format_html


class CustomFileWidget(ClearableFileInput):
    template_name = None

    def render(self, name, value, attrs=None, renderer=None):
        form_id = "agendapagos_form"

        # Combinamos atributos para rescatar el ID que manda get_form
        final_attrs = self.build_attrs(self.attrs, attrs)
        obj_id = final_attrs.get('data-obj-id', 'null')

        # ESTADO 1: CON ARCHIVO SUBIDO
        if value and hasattr(value, 'url'):
            filename = value.name.split('/')[-1]

            # 🚀 LA MAGIA SUPREMA: Sacamos el texto directamente de la base de datos
            # value.instance es el objeto CuotaInversion exacto. name es 'comprobante', 'factura', etc.
            try:
                file_log = getattr(value.instance, f"{name}_log", "")
            except AttributeError:
                file_log = ""

            log_html = format_html(
                '<div style="font-size: 0.8rem; color: #6c757d; margin-top: 4px; margin-left: 35px; font-style: italic;">{}</div>',
                file_log
            ) if file_log else ''

            return format_html(
                '''
                <div style="display: flex; flex-direction: column; max-width: 500px;">
                    <div style="display: flex; align-items: center; gap: 15px;">
                        <a href="{url}" target="_blank" title="Ver archivo" style="display: flex; align-items: center;">
                            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#007bff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                        </a>
                        <span style="flex-grow: 1; color: #333; font-size: 0.9rem; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            {filename}
                        </span>
                        <label style="margin:0; cursor:pointer;" title="Eliminar">
                            <input type="checkbox" name="{clear_name}" id="{clear_id}" style="display:none;" 
                                   onchange="if(this.checked) {{ document.getElementById('{form_id}').submit(); }}"> 
                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#dc3545" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        </label>
                        <label style="margin:0; cursor:pointer;" title="Cambiar">
                            <input type="file" name="{name}" id="{id}" style="display:none;" 
                                   onchange="document.getElementById('{form_id}').submit();"> 
                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#007bff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2v6h-6"></path><path d="M3 12a9 9 0 0 1 15-6.7L21 8"></path><path d="M3 22v-6h6"></path><path d="M21 12a9 9 0 0 1-15 6.7L3 16"></path></svg>
                        </label>
                    </div>
                    {log_html}
                </div>
                ''',
                url=value.url, filename=filename, name=name, id=final_attrs.get('id', name),
                clear_name=self.clear_checkbox_name(name),
                clear_id=self.clear_checkbox_id(self.clear_checkbox_name(name)),
                form_id=form_id, log_html=log_html
            )

        # ESTADO 2: VACÍO
        return format_html(
            '''
            <div style="text-align: left; line-height: 1;">
                <a href="javascript:void(0);" onclick="abrirModalUpload({obj_id}, '{name}')" title="Subir archivo">
                    <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#28a745" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="17 8 12 3 7 8"></polyline>
                        <line x1="12" y1="3" x2="12" y2="15"></line>
                    </svg>
                </a>
            </div>
            ''',
            obj_id=obj_id,
            name=name
        )