window.addEventListener('load', function() {
    console.log("Script Equity ");

    const selectTipo = document.querySelector('select[name="tipo_calculo"]');
    if(!selectTipo) return;

    function toggleCampos() {
        const isEquity = selectTipo.value === 'EQUITY';
        console.log(" Es Equity?:", isEquity);

        const campos = ['tea_anual', 'plazo_meses', 'frecuencia'];

        campos.forEach(campo => {
            const div = document.querySelector(`.form-group.field-${campo}`);
            if(div) {
                div.style.setProperty('display', isEquity ? 'none' : 'block', 'important');
            }
        });
    }

    setTimeout(toggleCampos, 200);

    if (window.jQuery) {
        window.jQuery(selectTipo).on('change', toggleCampos);
    } else {
        selectTipo.addEventListener('change', toggleCampos);
    }
});