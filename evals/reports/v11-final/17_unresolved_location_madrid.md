# 17_unresolved_location_madrid: Candidate won't name a city; flagged after two re-asks and the flow moves on

**PASS** · expected `needs_review`, got `needs_review` · 11 candidate messages · 6.9 min · $0.0069

*Monday 19 October 2026*

**Alex** · 13:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 13:00  
> empezamos

**Alex** · 13:00  
Genial, empezamos. ¿Me dices tu nombre y apellido completos?

> **Candidate** · 13:01  
> Javier Moreno Gil

**Alex** · 13:01  
Perfecto, anotado. Javier, ¿tienes carnet de conducir en vigor, sí o no?

> **Candidate** · 13:02  
> Carnet B, sí

**Alex** · 13:02  
Genial, con carnet B vas bien para el reparto. ¿En qué ciudad vives y en qué barrio?

> **Candidate** · 13:02  
> por la zona sur

**Alex** · 13:02  
Entiendo, "zona sur" nos sirve de pista. ¿En qué ciudad estás exactamente, y en qué barrio o zona concreta vives?

> **Candidate** · 13:03  
> eso da igual no? prefiero no decirlo

**Alex** · 13:03  
Entiendo que prefieras no dar detalles exactos. Para el reparto necesitamos saber la ciudad donde vivirías, así que, ¿me dices solo la ciudad, aunque no quieras dar el barrio?

> **Candidate** · 13:04  
> por ahi, de verdad q da igual. sigue con lo demas

**Alex** · 13:04  
Vale, seguimos. ¿Buscas jornada completa, media jornada, fines de semana o una combinación?

> **Candidate** · 13:04  
> jornada completa

**Alex** · 13:04  
Vale, jornada completa anotada. ¿Qué turnos te van bien: mañanas, tardes, noches u horario flexible?

> **Candidate** · 13:05  
> tardes

**Alex** · 13:05  
¡Vale, tardes anotado! ¿Has trabajado antes en reparto, con Glovo, Uber Eats, Just Eat u otra app, y cuánto tiempo?

> **Candidate** · 13:06  
> un año en Glovo

**Alex** · 13:06  
Vale, un año en Glovo anotado. ¿Desde qué fecha podrías empezar?

> **Candidate** · 13:06  
> el lunes que viene

**Alex** · 13:06  
¡Gracias, Javier! Repasemos: Javier Moreno Gil, carnet de conducir: sí, jornada completa, tardes, Glovo 1 año, empiezas el lunes 26 de octubre. ¿Está todo bien?

> **Candidate** · 13:06  
> Sí, todo bien

**Alex** · 13:06 *(close)*  
¡Listo, Javier! Un reclutador de Grupo Sazón te escribirá en los próximos días para concertar una entrevista. ¡Gracias por tu tiempo!

## Final record

```json
{
  "conversation_id": "eval-17_unresolved_location_madrid",
  "vacancy_id": "driver",
  "status": "needs_review",
  "language": "es",
  "fields": {
    "full_name": "Javier Moreno Gil",
    "has_driver_license": true,
    "availability": [
      "full_time"
    ],
    "schedule": [
      "afternoon"
    ],
    "experience": [
      {
        "platform": "glovo",
        "years": 1.0
      }
    ],
    "start_date": "2026-10-26"
  },
  "flags": [
    {
      "field": "location",
      "note": "unresolved after 2 re-asks"
    }
  ],
  "disqualify_reason": null,
  "review_reasons": [
    "unresolved:location"
  ],
  "summary": "La candidatura de Javier Moreno Gil para Repartidor queda en revisión porque no se pudo determinar su ubicación: tras dos repreguntas, solo respondió \"por ahí, da igual\" y siguió con lo demás. Busca jornada completa en turno de tarde, tiene carnet de conducir, cuenta con un año de experiencia en Glovo y podría empezar el lunes 26 de octubre de 2026. Antes de llamarlo conviene confirmar en qué zona o ciudad vive, ya que ese dato quedó sin resolver; por lo demás, confirmó el resumen sin correcciones.",
  "preference_score": 0.0
}
```
