# 22_kitchen_tiebreak_with_license_guadalajara: Tie-break pair (with license): equal on every required field, ranked by the preferred ones

**PASS** · expected `qualified`, got `qualified` · 9 candidate messages · 7.0 min · $0.0065

*Wednesday 21 October 2026*

**Alex** · 11:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de ayudante de cocina, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 11:00  
> Sí, empecemos

**Alex** · 11:00  
¡Genial, empezamos! Para comenzar, ¿me das tu nombre y apellido?

> **Candidate** · 11:01  
> Andrea Salinas Ochoa

**Alex** · 11:01  
Gracias, Andrea Salinas Ochoa, anotado. ¿En qué ciudad vives y en qué colonia?

> **Candidate** · 11:02  
> Chapalita, Guadalajara

**Alex** · 11:02  
¡Genial, Guadalajara anotado! ¿Buscas tiempo completo, medio tiempo, fines de semana o una combinación?

> **Candidate** · 11:03  
> Tiempo completo

**Alex** · 11:03  
Tiempo completo, anotado. ¿Qué turnos te van mejor: mañanas, tardes, noches u horario flexible?

> **Candidate** · 11:03  
> Mañanas y tardes

**Alex** · 11:03  
Perfecto, mañanas y tardes anotado. ¿Desde cuándo podrías empezar?

> **Candidate** · 11:04  
> El lunes 2 de noviembre

**Alex** · 11:04  
Corrected: Anotado, lunes 2 de noviembre. No es obligatorio para este puesto, pero ¿tienes licencia de manejo?

> **Candidate** · 11:05  
> sí, tengo licencia de manejo vigente

**Alex** · 11:05  
Anotado, licencia vigente. Por cierto, no es obligatorio para este puesto, pero ¿tienes tu certificado de manipulador de alimentos?

> **Candidate** · 11:06  
> si, tengo el curso de manejo higienico de alimentos

**Alex** · 11:06  
¡Gracias, Andrea! Repasemos: Andrea Salinas Ochoa, Guadalajara, tiempo completo, mañanas y tardes, empiezas el lunes 2 de noviembre, licencia de manejo: sí, curso de manejo higiénico de alimentos: sí. ¿Está todo bien?

> **Candidate** · 11:06  
> Sí, todo bien, gracias

**Alex** · 11:06 *(close)*  
¡Listo, Andrea! Un reclutador de Grupo Sazón te escribirá en los próximos días para concertar una entrevista. ¡Gracias por tu tiempo!

## Final record

```json
{
  "conversation_id": "eval-22_kitchen_tiebreak_with_license_guadalajara",
  "vacancy_id": "kitchen_prep",
  "status": "qualified",
  "language": "es",
  "fields": {
    "full_name": "Andrea Salinas Ochoa",
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
    "has_driver_license": true,
    "food_handler_certificate": true
  },
  "flags": [],
  "disqualify_reason": null,
  "review_reasons": [],
  "summary": "Andrea Salinas Ochoa, de Guadalajara, quedó como calificada para Ayudante de cocina, sin motivos de descalificación, banderas ni puntos a revisar. Tiene disponibilidad de tiempo completo en turnos de mañana y tarde, y puede empezar el lunes 2 de noviembre de 2026. Su puntaje de preferencia es 2.5 porque cuenta con dos extras opcionales: licencia de manejo vigente y certificado (curso) de manejo higiénico de alimentos. En la conversación no se registró experiencia previa, y confirmó que todos sus datos eran correctos.",
  "preference_score": 2.5
}
```
