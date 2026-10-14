# 23_kitchen_tiebreak_no_license_guadalajara: Tie-break pair (without license): equal on every required field, ranked by the preferred ones

**PASS** · expected `qualified`, got `qualified` · 10 candidate messages · 6.7 min · $0.0064

*Wednesday 21 October 2026*

**Alex** · 11:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de ayudante de cocina, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 11:00  
> Sí, claro, empecemos

**Alex** · 11:00  
¡Qué bien! Para empezar, ¿me compartes tu nombre y apellido?

> **Candidate** · 11:01  
> Paola Ruiz Ochoa

**Alex** · 11:01  
Gracias, Paola Ruiz Ochoa, anotado. ¿En qué ciudad vives y en qué colonia?

> **Candidate** · 11:02  
> Chapalita, Guadalajara

**Alex** · 11:02  
Anotado, Guadalajara. ¿Buscas jornada completa, media jornada, fines de semana o una combinación de estos?

> **Candidate** · 11:02  
> ¿Y el sueldo cuánto sería más o menos?

**Alex** · 11:02  
Buen dato, el pago depende de la ciudad y de las horas, y el reclutador te dará la cifra exacta en la entrevista. ¿Te interesa jornada completa, media jornada, fines de semana o una combinación de estas?

> **Candidate** · 11:03  
> Completa, tiempo completo

**Alex** · 11:03  
Anotado, jornada completa. ¿Qué turnos te van bien: mañanas, tardes, noches o flexible?

> **Candidate** · 11:03  
> Mañanas y tardes

**Alex** · 11:03  
Anotado, mañanas y tardes. ¿Para cuándo podrías empezar a trabajar?

> **Candidate** · 11:04  
> El lunes 2 de noviembre

**Alex** · 11:04  
Anotado, lunes 2 de noviembre. Es opcional, pero ¿tienes licencia de manejo?

> **Candidate** · 11:05  
> no, no tengo licencia

**Alex** · 11:05  
Anotado, sin licencia. Es opcional, pero ¿tienes tu certificado de manipulador de alimentos?

> **Candidate** · 11:05  
> si, tengo el curso de manejo higienico de alimentos

**Alex** · 11:05  
¡Gracias, Paola! Repasemos: Paola Ruiz Ochoa, Guadalajara, tiempo completo, mañanas y tardes, empiezas el lunes 2 de noviembre, licencia de manejo: no, curso de manejo higiénico de alimentos: sí. ¿Está todo bien?

> **Candidate** · 11:06  
> Sí, todo bien

**Alex** · 11:06 *(close)*  
¡Listo, Paola! Un reclutador de Grupo Sazón te escribirá en los próximos días para concertar una entrevista. ¡Gracias por tu tiempo!

## Final record

```json
{
  "conversation_id": "eval-23_kitchen_tiebreak_no_license_guadalajara",
  "vacancy_id": "kitchen_prep",
  "status": "qualified",
  "language": "es",
  "fields": {
    "full_name": "Paola Ruiz Ochoa",
    "location": {
      "country": "MX",
      "city": "guadalajara"
    },
    "availability": [
      "full_time"
    ],
    "schedule": [
      "morning",
      "afternoon"
    ],
    "start_date": "2026-11-02",
    "has_driver_license": false,
    "food_handler_certificate": true
  },
  "flags": [],
  "disqualify_reason": null,
  "review_reasons": [],
  "summary": "Paola Ruiz Ochoa quedó como calificada para el puesto kitchen_prep, sin motivos de descarte ni puntos por revisar. Vive en Guadalajara, tiene disponibilidad de tiempo completo en turnos de mañana y tarde, y puede empezar el lunes 2 de noviembre de 2026. Tiene certificado de manipulador de alimentos (extra opcional que suma como criterio de desempate) y no cuenta con licencia de manejo, que tampoco es requisito. No hay banderas ni preguntas pendientes, y la candidata confirmó que sus datos eran correctos.",
  "preference_score": 1.0
}
```
