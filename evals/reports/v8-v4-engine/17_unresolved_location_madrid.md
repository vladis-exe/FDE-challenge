# 17_unresolved_location_madrid: Candidate won't name a city; flagged after two re-asks and the flow moves on

**PASS** · expected `needs_review`, got `needs_review` · 11 candidate messages · 6.9 min · $0.0073

*Monday 19 October 2026*

**Alex** · 13:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 13:00  
> sip empezamos

**Alex** · 13:00  
Genial, empecemos. ¿Me dices tu nombre y apellido completos, por favor?

> **Candidate** · 13:01  
> Javier Moreno Gil

**Alex** · 13:01  
Gracias, Javier Moreno Gil, anotado. ¿Tienes carnet de conducir en vigor, sí o no?

> **Candidate** · 13:02  
> sí, carnet B

**Alex** · 13:02  
Perfecto, anotado el carnet B. ¿En qué ciudad vives y en qué barrio?

> **Candidate** · 13:02  
> por la zona sur

**Alex** · 13:02  
Entiendo, "zona sur" es un poco general. ¿En qué ciudad vives exactamente, y en qué barrio o zona concreta?

> **Candidate** · 13:03  
> eso da igual no? prefiero no decirlo

**Alex** · 13:03  
Entiendo que prefieras no dar el barrio exacto. Pero para saber si hay vacantes en tu zona, ¿me dices al menos la ciudad donde vives?

> **Candidate** · 13:04  
> por ahi, de verdad q da igual. sigue con lo demas

**Alex** · 13:04  
Vale, seguimos. ¿Buscas jornada completa, media jornada, fines de semana o una combinación de esas opciones?

> **Candidate** · 13:04  
> jornada completa

**Alex** · 13:04  
Anotado, jornada completa. ¿Qué turnos te van mejor: mañanas, tardes, noches o algo flexible?

> **Candidate** · 13:05  
> tardes

**Alex** · 13:05  
Anotado, turno de tardes. ¿Has trabajado antes como repartidor, en Glovo, Uber Eats, Just Eat o similares, y cuánto tiempo?

> **Candidate** · 13:06  
> un año en glovo

**Alex** · 13:06  
Anotado, un año en Glovo. ¿Para cuándo podrías empezar?

> **Candidate** · 13:06  
> el próximo lunes

**Alex** · 13:06  
¡Gracias, Javier! Repasemos: Javier Moreno Gil, carnet de conducir: sí, jornada completa, tardes, Glovo 1 año, empiezas el lunes 26 de octubre. ¿Está todo bien?

> **Candidate** · 13:06  
> Sí, todo bien. Lo del lunes 26 vale

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
  "summary": "El candidato Javier Moreno Gil (vacante de repartidor) queda en revisión porque no se pudo determinar su ubicación: tras dos repreguntas siguió sin dar una respuesta concreta (dijo \"por ahí, da igual\"). Tiene carnet de conducir, busca jornada completa en turno de tardes, cuenta con un año de experiencia en Glovo y puede empezar el lunes 26 de octubre de 2026, fecha que confirmó en el resumen. Antes de llamar conviene preguntarle directamente dónde vive o dónde puede trabajar; no hizo preguntas que Alex no pudiera responder y el resto de la conversación transcurrió con normalidad.",
  "preference_score": 0
}
```
