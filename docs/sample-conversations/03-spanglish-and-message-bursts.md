# Mexico: Spanglish, a side question and a burst of messages

*Mexico · outcome `qualified` · 9 candidate messages · eval scenario `04_code_switch_monterrey`*

A Monterrey candidate who mixes Spanish and English and sends three messages in a row before Alex can answer. Brandon also asks about the hours mid-flow, and answers the license question with where it's from ("sí, de NL").

**What to notice**

- The side question is answered from the FAQ's `hours` entry, so Alex says nothing the client hasn't approved. Then it re-asks the pending question.
- "sí, de NL" is a yes to the license question, not a location: Nuevo León is where the license was issued.
- "full time bro" / "y el horario me da igual" / "flexible pues" arrive within a minute. Every message updates the record, but only the last one gets a reply. The two replies marked *not delivered* were dropped, so the next question Brandon actually sees is the experience one, asked once.
- Mexican vocabulary throughout ("licencia de manejo", "colonia", "tiempo completo").

## Conversation

*Friday 23 October 2026*

**Alex** · 13:20  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 13:21  
> simón vamos

**Alex** · 13:21  
Genial, vamos entonces. ¿Me compartes tu nombre y apellido completos?

> **Candidate** · 13:22  
> brandon garza treviño

**Alex** · 13:22  
Gracias, Brandon Garza Treviño, anotado. ¿Tienes licencia de manejo vigente, sí o no?

> **Candidate** · 13:23  
> oye y es de tiempo completo la chamba?

**Alex** · 13:23  
Sí, hay turnos de mañana, tarde y noche, en tiempo completo, medio tiempo o solo fines de semana. ¿Tienes licencia de manejo vigente, sí o no?

> **Candidate** · 13:24  
> sí, de NL

**Alex** · 13:24  
Anotado, gracias por confirmarlo. ¿En qué ciudad vives y en qué colonia o barrio?

> **Candidate** · 13:25  
> monterrey colonia mitras

**Alex** · 13:25  
Anotado, Monterrey. ¿Buscas tiempo completo, medio tiempo, fines de semana o una combinación?

> **Candidate** · 13:25  
> full time bro

**Alex** · 13:25 *(not delivered: a newer message was waiting)*  
Anotado, tiempo completo. ¿Qué turnos te acomodan: mañanas, tardes, noches o flexible?

> **Candidate** · 13:25  
> y el horario me da igual

**Alex** · 13:25 *(not delivered: a newer message was waiting)*  
Anotado, horario flexible. ¿Has trabajado antes en reparto con apps como Uber Eats, Rappi o DiDi Food, y por cuánto tiempo?

> **Candidate** · 13:26  
> flexible pues, whatever works

**Alex** · 13:26  
¿Has hecho entregas antes con apps como Uber Eats, Rappi o DiDi Food, y por cuánto tiempo?

> **Candidate** · 13:26  
> simón, 2 años en Uber Eats en Houston

**Alex** · 13:26  
Anotado, dos años en Uber Eats. ¿Desde cuándo podrías empezar?

> **Candidate** · 13:27  
> el lunes que entra bro

**Alex** · 13:27  
¡Gracias, Brandon! Repasemos: Brandon Garza Treviño, licencia de manejo: sí, Monterrey, tiempo completo, horario flexible, Uber Eats 2 años, empiezas el lunes 26 de octubre. ¿Está todo bien?

> **Candidate** · 13:28  
> simon todo bien 👍

**Alex** · 13:28 *(close)*  
¡Listo, Brandon! Un reclutador de Grupo Sazón te escribirá en los próximos días para concertar una entrevista. ¡Gracias por tu tiempo!

## What the recruiter gets

> Brandon Garza Treviño queda como calificado para la vacante de repartidor (driver); no hay motivos de descalificación ni de revisión. Cuenta con licencia de manejo, vive en Monterrey, tiene disponibilidad de tiempo completo con horario flexible y 2 años de experiencia en Uber Eats, y puede empezar el 26 de octubre de 2026. Conviene confirmar que su experiencia fue en Houston, no en México, y que Alex tuvo que repetir la pregunta de experiencia porque el candidato respondió primero sobre el horario; al final confirmó todos sus datos.

```json
{
  "conversation_id": "eval-04_code_switch_monterrey",
  "vacancy_id": "driver",
  "status": "qualified",
  "language": "es",
  "fields": {
    "full_name": "brandon garza treviño",
    "has_driver_license": true,
    "location": {
      "country": "MX",
      "city": "monterrey"
    },
    "availability": [
      "full_time"
    ],
    "schedule": [
      "flexible"
    ],
    "experience": [
      {
        "platform": "uber_eats",
        "years": 2.0
      }
    ],
    "start_date": "2026-10-26"
  },
  "flags": [],
  "disqualify_reason": null,
  "review_reasons": [],
  "preference_score": 0
}
```
