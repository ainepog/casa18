(function($) {
    // 1. CSS NUCLEAR
    $('<style>').text(`
        #cuotas-group th.delete, #cuotas-group td.delete { display: none !important; width: 0 !important; padding: 0 !important; }
        #cuotas-group .add-related, #cuotas-group .change-related, #cuotas-group .related-widget-wrapper-link { display: none !important; }
        #cuotas-group img[src*="icon-addlink"] { display: none !important; }
        #cuotas-group td.field-nro_cuota { display: flex !important; align-items: center !important; gap: 8px !important; border-bottom: none !important; }
        #cuotas-group .add-row { justify-content: flex-start !important; padding-left: 10px !important; }
    `).appendTo('head');

    $(document).ready(function() {
        function enumerarCuotas() {
            let contador = 1;
            $('#cuotas-group tbody tr.form-row:not(.empty-form)').each(function() {
                let fila = $(this);
                let checkboxEliminar = fila.find('input[name$="-DELETE"]');
                if (!checkboxEliminar.is(':checked')) {
                    fila.find('input[name$="-nro_cuota"]').val(contador);
                    contador++;
                }
            });
        }

        function configurarBotonMenos() {
            $('#cuotas-group tbody tr.form-row').each(function() {
                let fila = $(this);
                let tdNroCuota = fila.find('td.field-nro_cuota');

                // Buscamos si Django imprimió los controles reales de eliminación
                let inputDeleteHidden = fila.find('input[name$="-DELETE"]');
                let deleteLink = fila.find('.inline-deletelink');

                // LA MAGIA: Solo dibujamos el botón rojo si existen los controles nativos de Django
                if ((inputDeleteHidden.length > 0 || deleteLink.length > 0) && !tdNroCuota.find('.btn-menos').length) {

                    let btnMenos = $('<div class="btn-menos" style="color:white; background:#dc3545; border-radius:4px; width:28px; height:28px; line-height:26px; text-align:center; font-weight:bold; font-size:18px; cursor:pointer; flex-shrink:0;" title="Eliminar">-</div>');

                    btnMenos.on('click', function() {
                        if (deleteLink.length) {
                            deleteLink[0].click();
                        } else if (inputDeleteHidden.length) {
                            inputDeleteHidden.prop('checked', !inputDeleteHidden.prop('checked'));
                            fila.css('opacity', inputDeleteHidden.prop('checked') ? '0.3' : '1');
                            enumerarCuotas();
                        }
                    });

                    tdNroCuota.prepend(btnMenos);
                }
            });
        }

        setTimeout(function() {
            configurarBotonMenos();
            enumerarCuotas();
        }, 150);

        $(document).on('formset:added formset:removed', function(event, $row, formsetName) {
            if (formsetName === 'cuotas') {
                configurarBotonMenos();
                enumerarCuotas();
            }
        });
    });
})(django.jQuery || jQuery);