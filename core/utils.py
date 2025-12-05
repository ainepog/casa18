from datetime import date, timedelta


def calcular_pascua(year):
    """
    Algoritmo matemático para encontrar el Domingo de Resurrección
    en cualquier año (para calcular Viernes Santo).
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451

    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1

    return date(year, month, day)


def obtener_feriados_peru(year):
    """
    Devuelve la lista exacta de feriados de tu imagen para el año solicitado.
    """
    feriados = [
        # --- FECHAS FIJAS (Según tu lista) ---
        date(year, 1, 1),  # Año Nuevo
        date(year, 1, 6),  # Día de los Reyes Magos (NUEVO)
        date(year, 5, 1),  # Día del Trabajo
        date(year, 6, 29),  # San Pedro y San Pablo
        date(year, 7, 28),  # Independencia del Perú
        date(year, 7, 29),  # Fiesta de la Independencia
        date(year, 8, 30),  # Santa Rosa de Lima
        date(year, 10, 8),  # Combate de Angamos
        date(year, 11, 1),  # Día de Todos los Santos
        date(year, 12, 8),  # Inmaculada Concepción
        date(year, 12, 9),  # Batalla de Ayacucho
        date(year, 12, 25),  # Navidad
    ]

    # --- FECHAS VARIABLES (Semana Santa) ---
    domingo_pascua = calcular_pascua(year)
    viernes_santo = domingo_pascua - timedelta(days=2)
    feriados.append(viernes_santo)

    return feriados
