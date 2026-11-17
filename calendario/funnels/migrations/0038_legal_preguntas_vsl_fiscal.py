# -*- coding: utf-8 -*-
"""Conquer Legal: preguntas 4 a 8 del formulario de prellamada para la VSL de
optimización fiscal, y score como media simple de esas cinco.

Lo pidió el equipo de Legal el 17/11/2026 (PDF «Formulario de agenda · Conquer
Legal»). Aplica a los dos funnels de Legal (legal-eu y legal-eu-2), que hasta
ahora tenían exactamente las mismas preguntas.

- Las preguntas nuevas llevan nombres nuevos. La tabla de puntos
  (`FunnelScoring`) es global y se indexa por nombre de campo:
  `current_problems` lo usan todos los funnels, así que cambiarle los tramos
  de caracteres habría cambiado el score de Blocks, Finance y Languages. Al CRM
  le da igual: recibe las respuestas por posición (q1..q6 según `q_order`).
- `score_sin_pais`: el score de Legal pasa a ser
  (P4 + P5 + P6 + P7 + P8) / 5, sin el país (que hasta ahora entraba en la
  media, con España = 4).
- Nadie se descalifica: `validate` sigue vacío y el único rango de score va de
  0 a 100. El nivel (frío/templado/prioritario/caliente) lo marca el CRM con el
  score; aquí no cambia el evento de reserva.

Se parchea la fila en BD porque el formulario de estos funnels solo vive ahí
(mismo motivo que 0032).
"""
from django.db import migrations

FORM_KEYS = ('LegalEu', 'LegalEu2')

ORDEN_NUEVO = ['work_structure', 'annual_revenue', 'has_partners', 'prior_tax_help', 'tax_concerns']

TRABAJO = {
    'Soy autónomo.': 2,
    'Tengo una sociedad (SL o SA).': 3,
    'Tengo varias sociedades.': 4,
    'Todavía no tengo actividad (estoy empezando).': 1,
}
FACTURACION = {
    'Menos de 100.000 € al año.': 1,
    'Entre 100.000 € y 250.000 € al año.': 2,
    'Entre 250.000 € y 1.000.000 € al año.': 3,
    'Más de 1.000.000 € al año.': 4,
}
SOCIOS = {
    'No, soy el único propietario.': 4,
    'Sí, tengo uno o más socios.': 3,
}
AYUDA_PREVIA = {
    'Sí, pero no me dieron ninguna solución que funcionara.': 4,
    'No, siempre me lo ha llevado mi gestor y nunca hemos revisado la estructura.': 3,
    'No, es la primera vez que busco ayuda con esto.': 2,
    'Sí, y ya tengo una estructura optimizada.': 1,
}


def _opciones(label, puntos, id_):
    return {
        'id': id_,
        'name': 'multiple-choice',
        'attributes': {
            'label': label,
            'choices': [{'label': t, 'value': t} for t in puntos],
            'required': True,
        },
    }


PREGUNTAS_NUEVAS = [
    _opciones('¿Cómo trabajas actualmente?', TRABAJO, 'work_structure'),
    _opciones('¿Cuál es la facturación anual de tu negocio en este momento? (en euros)',
              FACTURACION, 'annual_revenue'),
    _opciones('¿Tienes socios en tu negocio?', SOCIOS, 'has_partners'),
    _opciones('¿Has buscado ayuda antes para pagar menos impuestos dentro de la legalidad?',
              AYUDA_PREVIA, 'prior_tax_help'),
    {
        'id': 'tax_concerns',
        'name': 'long-text',
        'attributes': {
            'label': (
                '¿Dónde sientes que estás pagando más impuestos de la cuenta y qué te '
                'gustaría mejorar de tu situación fiscal actual con la ayuda de Conquer Legal?'
            ),
            'required': True,
            'placeholder': (
                'Cuéntanos tu situación: cómo sacas el dinero del negocio, qué te '
                'preocupa, qué te ha dicho tu gestoría…'
            ),
        },
    },
]


def _puntos(name, tabla):
    return {'name': name, 'type': 'option', 'count_for_score': True, **tabla}


PUNTOS_NUEVOS = [
    _puntos('work_structure', TRABAJO),
    _puntos('annual_revenue', FACTURACION),
    _puntos('has_partners', SOCIOS),
    _puntos('prior_tax_help', AYUDA_PREVIA),
    {
        'name': 'tax_concerns',
        'type': 'length',
        'count_for_score': True,
        'scores': [
            {'from': 0, 'to': 29, 'score': 1},
            {'from': 30, 'to': 99, 'score': 2},
            {'from': 100, 'to': 249, 'score': 3},
            {'from': 250, 'to': 999999999, 'score': 4},
        ],
    },
]

ORDEN_ANTERIOR = ['business_type', 'business_revenue', 'team_size', 'legal_goal', 'current_problems']

PREGUNTAS_ANTERIORES = [
    {
        "id": "business_type",
        "name": "multiple-choice",
        "attributes": {
            "label": "¿Qué tipo de negocio tienes?",
            "choices": [
                {
                    "label": "Tengo un negocio online (infoproductores, servicios online, e-commerce, agencias de marketing, etc.)",
                    "value": "Tengo un negocio online (infoproductores, servicios online, e-commerce, agencias de marketing, etc.)"
                },
                {
                    "label": "Tengo un negocio tradicional (retail, hostelería, servicios personales y técnicos, sector primario, producción industrial, educación, etc.)",
                    "value": "Tengo un negocio tradicional (retail, hostelería, servicios personales y técnicos, sector primario, producción industrial, educación, etc.)"
                }
            ],
            "required": True
        }
    },
    {
        "id": "business_revenue",
        "name": "multiple-choice",
        "attributes": {
            "label": "¿Cuál es el volumen de facturación anual de tu negocio en este momento? (en euros)",
            "choices": [
                {
                    "label": "Menos de 8,000 euros al mes.",
                    "value": "Menos de 8,000 euros al mes."
                },
                {
                    "label": "Entre 8,000 y 15,000 euros al mes.",
                    "value": "Entre 8,000 y 15,000 euros al mes."
                },
                {
                    "label": "Entre 15,000 y 50,000 euros al mes.",
                    "value": "Entre 15,000 y 50,000 euros al mes."
                },
                {
                    "label": "Más de 50,000 euros al mes.",
                    "value": "Más de 50,000 euros al mes."
                }
            ],
            "required": True
        }
    },
    {
        "id": "team_size",
        "name": "multiple-choice",
        "attributes": {
            "label": "¿Qué volumen de personal, entre contractors y empleados, tiene tu negocio en este momento?",
            "choices": [
                {
                    "label": "Soy solo yo en el negocio.",
                    "value": "Soy solo yo en el negocio."
                },
                {
                    "label": "De 2 a 10 personas.",
                    "value": "De 2 a 10 personas."
                },
                {
                    "label": "De 10 a 30 personas.",
                    "value": "De 10 a 30 personas."
                },
                {
                    "label": "Más de 30 personas.",
                    "value": "Más de 30 personas."
                }
            ],
            "required": True
        }
    },
    {
        "id": "legal_goal",
        "name": "multiple-choice",
        "attributes": {
            "label": "¿Cuál es tu objetivo a conseguir en este momento?",
            "choices": [
                {
                    "label": "Quiero ahorrar el máximo dinero posible en impuestos.",
                    "value": "Quiero ahorrar el máximo dinero posible en impuestos."
                },
                {
                    "label": "Quiero prevenir problemas legales y fiscales en mi negocio.",
                    "value": "Quiero prevenir problemas legales y fiscales en mi negocio."
                },
                {
                    "label": "Tengo problemas ya existentes en mi negocio que quiero solucionar.",
                    "value": "Tengo problemas ya existentes en mi negocio que quiero solucionar."
                },
                {
                    "label": "Otro.",
                    "value": "Otro."
                }
            ],
            "required": True
        }
    },
    {
        "id": "current_problems",
        "name": "long-text",
        "attributes": {
            "label": "¿Qué problemas encuentras o quieres evitar en la situación actual de tu negocio que quieres solucionar gracias a la ayuda de Conquer Legal?",
            "required": True,
            "placeholder": "Describe tus principales desafíos o inquietudes actuales."
        }
    }
]


def _cambiar_preguntas(apps, quitar, poner, orden, sin_pais):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    for form in FunnelForm.objects.filter(key__in=FORM_KEYS):
        config = dict(form.config or {})
        blocks = [b for b in config.get('blocks', []) if b.get('id') not in quitar]
        config['blocks'] = blocks + poner
        config['q_order'] = orden
        if sin_pais:
            config['score_sin_pais'] = True
        else:
            config.pop('score_sin_pais', None)
        form.config = config
        form.save(update_fields=['config'])


def _cambiar_puntos(apps, quitar, poner):
    FunnelScoring = apps.get_model('funnels', 'FunnelScoring')
    scoring, _ = FunnelScoring.objects.get_or_create(pk=1)
    tabla = [e for e in (scoring.config or []) if e.get('name') not in quitar]
    scoring.config = tabla + poner
    scoring.save(update_fields=['config'])


def forwards(apps, schema_editor):
    _cambiar_preguntas(apps, set(ORDEN_ANTERIOR) | set(ORDEN_NUEVO), PREGUNTAS_NUEVAS,
                       ORDEN_NUEVO, sin_pais=True)
    _cambiar_puntos(apps, set(ORDEN_NUEVO), PUNTOS_NUEVOS)


def backwards(apps, schema_editor):
    _cambiar_preguntas(apps, set(ORDEN_ANTERIOR) | set(ORDEN_NUEVO), PREGUNTAS_ANTERIORES,
                       ORDEN_ANTERIOR, sin_pais=False)
    _cambiar_puntos(apps, set(ORDEN_NUEVO), [])


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0037_seed_legal_eu_2'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
