"""Lógica de scoring del funnel (backend).

Portada de `funnels-new/src/components/mainFormSubmission.js`
(`buildScoreDetails` + cálculo de `avg_score`) y de
`mainForm.helpers.js` (`resolveSchedulingOutcome`).

Funciones puras y testeables en shell. La config de la BD
(`FunnelForm.config` + `FunnelScoring.config`) es la única fuente de verdad;
React solo recoge respuestas y las envía.

Formato de `respuestas` (MVP): dict plano `{campo: 'valor'}`. Se tolera
defensivamente el formato quillforms heredado (`{campo: {'value': [...]}}`).
"""

import logging
from decimal import ROUND_HALF_UP, Decimal

from calendario.event_types.models import EventType
from calendario.funnels.models import FunnelScoring

logger = logging.getLogger(__name__)


def _valor(respuestas, name):
    """Devuelve el valor escalar de una respuesta, tolerando formatos.

    Acepta el formato MVP (`'valor'`) y el heredado de quillforms
    (`{'value': [...]}` o `{'value': 'x'}`). Devuelve `None` si no hay respuesta.
    """
    if not respuestas:
        return None
    raw = respuestas.get(name)
    if isinstance(raw, dict):
        raw = raw.get('value')
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else None
    return raw


def _coincide_regla(respuestas, regla):
    """True si la respuesta del campo de `regla` iguala su valor.

    `regla` es un dict de una sola clave, ej. ``{'age': 'Soy menor de 18 años.'}``.
    """
    for campo, valor in regla.items():
        if _valor(respuestas, campo) == valor:
            return True
    return False


def calcular_score(respuestas, scoring_config, campos=None):
    """Calcula el score de un conjunto de respuestas.

    Réplica de `buildScoreDetails` + promedio (`avg_score`):

    - Por cada campo de `scoring_config` con ``count_for_score=True`` y respuesta
      presente: si es ``option`` busca ``entry[valor]`` (0 por defecto); si es
      ``length`` mide la longitud del texto y busca el rango ``from``/``to``.
    - El promedio se hace sobre los scores **distintos de 0** (los 0 no entran ni
      en el numerador ni en el denominador, igual que el original) y se redondea
      a 1 decimal.
    - Si se pasa `campos`, solo esos campos entran en el promedio (réplica del
      original, que promedia ``country_score + q1..q6``); los demás se calculan
      pero no se promedian.

    Devuelve ``{'score_total', 'detalles', 'promedio'}``.
    """
    detalles = []
    for entry in scoring_config:
        if not entry.get('count_for_score'):
            continue
        name = entry.get('name')
        valor = _valor(respuestas, name)
        if valor is None or valor == '':
            continue

        tipo = entry.get('type')
        if tipo == 'option':
            puntos = entry.get(valor, 0)
        elif tipo == 'length':
            longitud = len(str(valor))
            puntos = 0
            for rango in entry.get('scores', []):
                if rango['from'] <= longitud <= rango['to']:
                    puntos = rango['score']
                    break
        else:
            continue

        detalles.append({'name': name, 'value': valor, 'score': puntos})

    if campos is not None:
        permitidos = set(campos)
        considerados = [d for d in detalles if d['name'] in permitidos]
    else:
        considerados = detalles

    no_cero = [
        d['score'] for d in considerados
        if isinstance(d['score'], (int, float)) and d['score'] != 0
    ]
    score_total = sum(no_cero)
    if no_cero:
        promedio = float(
            Decimal(str(score_total / len(no_cero))).quantize(
                Decimal('0.1'), rounding=ROUND_HALF_UP
            )
        )
    else:
        promedio = 0.0

    return {'score_total': score_total, 'detalles': detalles, 'promedio': promedio}


def aplica_validate(respuestas, validate):
    """True si alguna respuesta coincide con una regla de descalificación."""
    return any(_coincide_regla(respuestas, regla) for regla in (validate or []))


def aplica_never_cancel(respuestas, never_cancel):
    """True si alguna respuesta coincide con una regla de rescate (inmunidad)."""
    return any(_coincide_regla(respuestas, regla) for regla in (never_cancel or []))


def resolver_outcome(funnel, respuestas):
    """Decide el resultado del funnel para un conjunto de respuestas.

    Réplica de `resolveSchedulingOutcome` + selección de calendly de
    `MainForm.jsx`. Orden de precedencia (idéntico al original):

    1. ``neverCancel`` → inmune: nunca se rechaza (salta validate y min_score).
    2. ``validate`` → rechazo.
    3. ``promedio < score_ranges[0].min_score`` → rechazo.
    4. Selección del rango donde ``min_score <= promedio <= max_score``, con
       **fallback al primer rango** si ninguno encaja (réplica de
       ``calendlys.find(...) || calendlys[0]``).
    5. Resolución del ``EventType`` por slug. Si no existe o está inactivo, se
       trata como rechazo y se loguea un warning (ver tabla de riesgos del plan).

    Devuelve un dict con ``resultado`` (``'calendario'`` | ``'rechazado'``),
    ``promedio``, ``score_total``, ``motivo`` y, si es calendario,
    ``event_type_slug`` / ``host_slug`` / ``event_type_id``.
    """
    config = funnel.config or {}
    scoring_config = FunnelScoring.load().config or []
    q_order = config.get('q_order', []) or []
    score_ranges = config.get('score_ranges', []) or []

    # Campos promediados: country + primeras 6 preguntas (paridad con el
    # original: avg sobre country_score + q1..q6).
    campos = ['country'] + list(q_order[:6])
    score = calcular_score(respuestas, scoring_config, campos=campos)
    promedio = score['promedio']

    resultado = {
        'resultado': None,
        'promedio': promedio,
        'score_total': score['score_total'],
        'cancel_screen': config.get('cancel_screen', {}),
    }

    inmune = aplica_never_cancel(respuestas, config.get('neverCancel', []))

    if not inmune:
        if aplica_validate(respuestas, config.get('validate', [])):
            resultado.update(resultado='rechazado', motivo='validate')
            return resultado

        min_score = score_ranges[0]['min_score'] if score_ranges else 0
        if promedio < min_score:
            resultado.update(resultado='rechazado', motivo='score_below_min')
            return resultado

    rango = next(
        (r for r in score_ranges if r['min_score'] <= promedio <= r['max_score']),
        score_ranges[0] if score_ranges else None,
    )
    if rango is None:
        resultado.update(resultado='rechazado', motivo='sin_rangos')
        return resultado

    event_type_id = rango.get('event_type_id')
    event_type = (
        EventType.objects.filter(id=event_type_id, activo=True)
        .select_related('host')
        .first()
    ) if event_type_id else None
    if event_type is None:
        logger.warning(
            "Funnel %s: event_type_id=%s no existe, está inactivo o es null; "
            "se trata como rechazo.",
            funnel.key, event_type_id,
        )
        resultado.update(resultado='rechazado', motivo='event_type_inexistente')
        return resultado

    resultado.update(
        resultado='calendario',
        motivo='ok',
        event_type_slug=event_type.slug,
        host_slug=event_type.host.slug,
        event_type_id=event_type.id,
    )
    return resultado
