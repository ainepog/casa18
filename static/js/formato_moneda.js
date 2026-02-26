(function($) {
    $(document).ready(function() {
        const palabrasClave = ['monto', 'precio', 'capital', 'interes', 'amortizacion', 'total','ingreso','area'];

        function aplicarFormato(input) {
            const name = (input.name || '').toLowerCase();
            const id = (input.id || '').toLowerCase();

            const esDinero = palabrasClave.some(kw => name.includes(kw) || id.includes(kw));

            if (esDinero && !input.dataset.formateado) {
                if (input.type === 'number') {
                    input.type = 'text';
                }
                input.dataset.formateado = 'true';

                if (input.value) {
                    input.value = darFormato(input.value);
                }

                $(input).on('input', function() {
                    let posicionCursor = this.selectionStart;
                    let longitudAnterior = this.value.length;

                    this.value = darFormato(this.value);

                    let nuevaLongitud = this.value.length;
                    posicionCursor = posicionCursor + (nuevaLongitud - longitudAnterior);
                    this.setSelectionRange(posicionCursor, posicionCursor);
                });
            }
        }

        function darFormato(valor) {
            let num = valor.replace(/[^0-9.]/g, '');

            let partes = num.split('.');
            if (partes.length > 2) {
                num = partes[0] + '.' + partes.slice(1).join('');
                partes = num.split('.');
            }

            let enteros = partes[0];
            let decimales = partes.length > 1 ? '.' + partes[1].substring(0, 2) : '';

            enteros = enteros.replace(/\B(?=(\d{3})+(?!\d))/g, ',');

            return enteros + decimales;
        }

        $('input').each(function() {
            aplicarFormato(this);
        });

        $(document).on('formset:added', function(event, $row, formsetName) {
            $row.find('input').each(function() {
                aplicarFormato(this);
            });
        });

        $('form').on('submit', function() {
            $(this).find('input[data-formateado="true"]').each(function() {
                this.value = this.value.replace(/,/g, '');
            });
        });
    });
})(django.jQuery || jQuery);