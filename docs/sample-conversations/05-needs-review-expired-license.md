# Needs review: an expired license

*Spain · outcome `needs_review` · 10 candidate messages · eval scenario `13_expired_license_bilbao`*

A candidate whose license expired in August, with a renewal appointment in two weeks. Not a yes and not a no: the spec says code must not decide this alone.

**What to notice**

- Alex doesn't judge the license. It says a recruiter will look at it and carries on, so the recruiter gets a complete profile, not a half-finished one.
- The read-back says "lo revisará un reclutador" for the license instead of a yes or no.
- The record leaves `has_driver_license` empty and flags it with the candidate's detail ("caducó en agosto, cita para renovarlo en 2 semanas"), with the review reason `license_unclear`. The summary tells the recruiter what to confirm first.

## Conversation

*Tuesday 20 October 2026*

**Alex** · 16:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 16:00  
> aupa, vale, empezamos

**Alex** · 16:00  
Genial, vamos allá. ¿Me dices tu nombre y apellido completos?

> **Candidate** · 16:01  
> iker etxeberria goñi

**Alex** · 16:01  
Gracias, Iker, apuntado. ¿Tienes carnet de conducir en vigor, sí o no?

> **Candidate** · 16:01  
> tengo el carnet pero me caducó en agosto, tengo cita para renovarlo en 2 semanas

**Alex** · 16:01  
Vale, lo tengo anotado; un reclutador lo revisará. ¿En qué ciudad vives y en qué barrio?

> **Candidate** · 16:02  
> vale, una duda: el curro es con moto o con coche?

**Alex** · 16:02  
Lo que sí necesitas es el permiso de conducir en vigor; el reclutador te confirmará lo del vehículo. ¿En qué ciudad vives y en qué barrio?

> **Candidate** · 16:02  
> bilbao, en deusto

**Alex** · 16:02  
Perfecto, anotado: Bilbao. ¿Qué disponibilidad tienes, buscas jornada completa, media jornada, fines de semana o una combinación?

> **Candidate** · 16:03  
> jornada completa

**Alex** · 16:03  
Anotado, jornada completa. ¿Qué turnos te van mejor, mañanas, tardes, noches o algo flexible?

> **Candidate** · 16:04  
> flexible, cualquier horario me va bien

**Alex** · 16:04  
¿Has trabajado antes en reparto, con Glovo, Uber Eats o Just Eat, y durante cuánto tiempo?

> **Candidate** · 16:05  
> 3 años en glovo

**Alex** · 16:05  
Vale, lo tengo anotado. ¿Cuándo podrías empezar?

> **Candidate** · 16:05  
> el 1 de diciembre

**Alex** · 16:05  
¡Gracias, Iker! Repasemos: Iker Etxeberria Goñi, carnet de conducir: lo revisará un reclutador, Bilbao, jornada completa, horario flexible, Glovo 3 años, empiezas el martes 1 de diciembre. ¿Está todo bien?

> **Candidate** · 16:05  
> si, todo bien

**Alex** · 16:05 *(close)*  
¡Listo, Iker! Un reclutador de Grupo Sazón te escribirá en los próximos días para concertar una entrevista. ¡Gracias por tu tiempo!

## What the recruiter gets

> El caso queda en revisión porque el estado del carnet de conducir no está claro: según el registro, caducó en agosto y el candidato tiene cita para renovarlo en dos semanas. Iker Etxeberria Goñi, de Bilbao (Deusto), busca jornada completa con horario flexible, tiene 3 años de experiencia en Glovo y podría empezar el 1 de diciembre de 2026. Conviene confirmar con él si la renovación se hizo y la fecha de vigencia del nuevo carnet, ya que el puesto de conductor lo requiere. La conversación transcurrió sin incidencias y el candidato confirmó el resumen sin preguntas pendientes.

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
      "note": "license expired: caducó en agosto, cita para renovarlo en 2 semanas"
    }
  ],
  "disqualify_reason": null,
  "review_reasons": [
    "license_unclear"
  ],
  "preference_score": 0
}
```
