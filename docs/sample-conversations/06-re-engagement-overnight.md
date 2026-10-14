# Re-engagement: silent overnight, back in the morning

*Spain · outcome `qualified` · 9 candidate messages · eval scenario `16_silence_late_reply_barcelona`*

A candidate who stops answering at 20:34 and comes back the next morning. Nuria starts in the evening, goes quiet at the experience question, and replies at 09:35.

**What to notice**

- The 15-minute reminder goes out at 20:49. The 2-hour one would land at 22:34, inside quiet hours (21:00–09:00 local), so it waits until 09:00.
- She picks up where she left off; nothing is asked twice.
- "mañana mismo", said on Friday the 23rd, is stored as Saturday 24 October, resolved against the timestamp of the reply, not of the first message.

## Conversation

*Thursday 22 October 2026*

**Alex** · 20:30  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 20:31  
> hola! si venga, empezamos

**Alex** · 20:31  
Genial, empecemos. ¿Me dices tu nombre y apellido completos, por favor?

> **Candidate** · 20:32  
> nuria vidal roca

**Alex** · 20:32  
Gracias, Nuria, anotado. ¿Tienes carnet de conducir en vigor, sí o no?

> **Candidate** · 20:32  
> sí, carnet B

**Alex** · 20:32  
Anotado, gracias. ¿En qué ciudad vives y en qué barrio?

> **Candidate** · 20:33  
> en barcelona, en sants

**Alex** · 20:33  
Anotado, Barcelona y Sants. ¿Buscas jornada completa, media jornada, fines de semana o una combinación de esas opciones?

> **Candidate** · 20:34  
> media jornada

**Alex** · 20:34  
Anotado, media jornada. ¿Qué turnos te van mejor: mañanas, tardes, noches o algo flexible?

> **Candidate** · 20:34  
> mañanas

**Alex** · 20:34  
Anotado, mañanas. ¿Has trabajado antes en reparto, con Glovo, Uber Eats o Just Eat, y cuánto tiempo?

**Alex** · 20:49 *(reminder)*  
¿Sigues por ahí, Nuria? Cuando puedas, contéstame y seguimos donde lo dejamos 🙂

*Friday 23 October 2026*

**Alex** · 09:00 *(reminder)*  
Hola, Nuria, te queda muy poco para terminar tu candidatura. ¿Seguimos?

> **Candidate** · 09:35  
> perdona me quedé dormida. no, nunca he trabajado en reparto

**Alex** · 09:35  
Gracias por contestar, Nuria, no pasa nada. ¿Cuándo podrías empezar?

> **Candidate** · 09:36  
> mañana mismo

**Alex** · 09:36  
¡Gracias, Nuria! Repasemos: Nuria Vidal Roca, carnet de conducir: sí, Barcelona, media jornada, mañanas, sin experiencia en reparto, empiezas el sábado 24 de octubre. ¿Está todo bien?

> **Candidate** · 09:36  
> sí, todo bien

**Alex** · 09:36 *(close)*  
¡Listo, Nuria! Un reclutador de Grupo Sazón te escribirá en los próximos días para concertar una entrevista. ¡Gracias por tu tiempo!

## What the recruiter gets

> Nuria Vidal Roca queda como calificada para la vacante de repartidora (driver), sin motivos de revisión ni descalificación. Tiene carnet de conducir, vive en Barcelona, busca media jornada en turno de mañana, no tiene experiencia previa en reparto y dijo que puede empezar "mañana mismo", que quedó registrado como el 24 de octubre de 2026 y que ella confirmó en el resumen. No hay extras opcionales (preference_score 0). Como detalle, tardó en responder a mitad de la conversación (explicó que se había quedado dormida) y luego continuó con normalidad.

```json
{
  "conversation_id": "eval-16_silence_late_reply_barcelona",
  "vacancy_id": "driver",
  "status": "qualified",
  "language": "es",
  "fields": {
    "full_name": "nuria vidal roca",
    "has_driver_license": true,
    "location": {
      "country": "ES",
      "city": "barcelona"
    },
    "availability": [
      "part_time"
    ],
    "schedule": [
      "morning"
    ],
    "experience": [],
    "start_date": "2026-10-24"
  },
  "flags": [],
  "disqualify_reason": null,
  "review_reasons": [],
  "preference_score": 0
}
```
