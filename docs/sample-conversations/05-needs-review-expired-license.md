# Needs review: an expired license

*Spain · outcome `needs_review` · 10 candidate messages · eval scenario `13_expired_license_bilbao`*

A candidate whose license expired in August, with a renewal appointment in two weeks. Not a yes and not a no: the spec says code must not decide this alone.

**What to notice**

- Alex doesn't judge the license. It says a recruiter will look at it and carries on, so the recruiter gets a complete profile, not a half-finished one.
- The pay question is answered from the FAQ without a figure ("the recruiter will give you the exact amount"), since the client's FAQ doesn't commit to one.
- The read-back shows the candidate's own words for the license ("caducó en agosto, cita para renovar en 2 semanas (lo revisará un reclutador)") instead of a yes or no, so he can see it was understood and confirms at once.
- The record leaves `has_driver_license` empty and flags it with the candidate's detail ("caducó en agosto, cita para renovarlo en 2 semanas"), with the review reason `license_unclear`. The summary tells the recruiter what to confirm first.

## Conversation

*Tuesday 20 October 2026*

**Alex** · 16:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 16:00  
> aupa, vale, empezamos

**Alex** · 16:00  
¡Genial, empezamos! ¿Me dices tu nombre y apellidos completos?

> **Candidate** · 16:01  
> iker etxeberria goñi

**Alex** · 16:01  
Gracias, Iker, anotado. ¿Tienes carnet de conducir en vigor, sí o no?

> **Candidate** · 16:01  
> tengo el carnet pero me caducó en agosto, tengo cita para renovarlo en 2 semanas

**Alex** · 16:01  
Anotado, Iker, lo revisará un reclutador. ¿En qué ciudad vives y en qué barrio?

> **Candidate** · 16:02  
> vale, y el sueldo cuanto es más o menos?

**Alex** · 16:02  
Sobre el sueldo, depende de la ciudad y de las horas, y el reclutador te dará la cifra exacta en la entrevista. ¿En qué ciudad vives y en qué barrio?

> **Candidate** · 16:02  
> en bilbao, en deusto

**Alex** · 16:02  
Genial, Bilbao, anotado. ¿Buscas jornada completa, media jornada, fines de semana o una combinación?

> **Candidate** · 16:03  
> jornada completa

**Alex** · 16:03  
Vale, jornada completa anotada. ¿Qué turnos te van bien: mañanas, tardes, noches o horario flexible?

> **Candidate** · 16:04  
> cualquier horario, soy flexible

**Alex** · 16:04  
Vale, horario flexible anotado. ¿Has trabajado antes en reparto, por ejemplo con Glovo, Uber Eats o Just Eat, y cuánto tiempo?

> **Candidate** · 16:05  
> 3 años en glovo

**Alex** · 16:05  
Vale, 3 años en Glovo anotados. ¿Cuándo podrías empezar si te damos el puesto?

> **Candidate** · 16:05  
> el 1 de diciembre

**Alex** · 16:05  
¡Gracias, Iker! Repasemos: Iker Etxeberria Goñi, carnet de conducir: caducó en agosto, cita para renovar en 2 semanas (lo revisará un reclutador), Bilbao, jornada completa, horario flexible, Glovo 3 años, empiezas el martes 1 de diciembre. ¿Está todo bien?

> **Candidate** · 16:05  
> sí, todo bien

**Alex** · 16:05 *(close)*  
¡Listo, Iker! Un reclutador de Grupo Sazón te escribirá en los próximos días para concertar una entrevista. ¡Gracias por tu tiempo!

## What the recruiter gets

> La candidatura de Iker Etxeberria Goñi para Repartidor queda en revisión porque el estado de su carnet de conducir no está claro: según el registro, caducó en agosto y tiene cita para renovarlo dentro de dos semanas. Vive en Bilbao (Deusto), busca jornada completa con horario flexible, tiene 3 años de experiencia en Glovo y puede empezar el 1 de diciembre de 2026. Conviene confirmar antes de llamar si la renovación se ha hecho y desde qué fecha el carnet estará vigente. En la conversación no hubo silencios ni correcciones, y el candidato confirmó que el resumen era correcto.

```json
{
  "conversation_id": "eval-13_expired_license_bilbao",
  "vacancy_id": "driver",
  "status": "needs_review",
  "language": "es",
  "fields": {
    "full_name": "iker etxeberria goñi",
    "location": {
      "country": "ES",
      "city": "bilbao"
    },
    "availability": [
      "full_time"
    ],
    "schedule": [
      "flexible"
    ],
    "experience": [
      {
        "platform": "glovo",
        "years": 3.0
      }
    ],
    "start_date": "2026-12-01"
  },
  "flags": [
    {
      "field": "has_driver_license",
      "note": "license expired: caducó en agosto, cita para renovar en 2 semanas"
    }
  ],
  "disqualify_reason": null,
  "review_reasons": [
    "license_unclear"
  ],
  "preference_score": 0.0
}
```
