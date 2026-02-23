window.addEventListener("load", function() {
    // 1. Buscamos los elementos exactos por su ID y Clase
    const selectBanco = document.getElementById('id_banco');
    const divBancoPersonalizado = document.querySelector('.field-banco_personalizado');
    const inputBancoPersonalizado = document.getElementById('id_banco_personalizado');


    function toggleBanco() {
        console.log("Opción seleccionada:", selectBanco.value);
        if (selectBanco.value === 'OTRO') {
            divBancoPersonalizado.style.setProperty('display', 'block', 'important');
        } else {
            divBancoPersonalizado.style.setProperty('display', 'none', 'important');
            if(inputBancoPersonalizado) inputBancoPersonalizado.value = '';
        }
    }

    setTimeout(toggleBanco, 300);

    if (window.jQuery) {
        window.jQuery('#id_banco').on('change', toggleBanco);
    } else {
        selectBanco.addEventListener('change', toggleBanco);
    }
});