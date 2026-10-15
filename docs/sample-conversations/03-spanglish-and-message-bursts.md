# Mexico: Spanglish, a side question and a burst of messages

*Mexico · outcome `qualified` · 9 candidate messages · eval scenario `04_code_switch_monterrey`*

A Monterrey candidate who mixes Spanish and English and sends three messages in a row before Alex can answer. Brandon also asks mid-flow whether the job is by motorbike or car, and answers the license question with where it's from ("sí, de NL").

**What to notice**

- The side question is answered from the FAQ's `vehicle` entry, so Alex promises nothing the client hasn't approved, then re-asks the pending question. One stumble, though. The answer says "permiso de conducir", Spain's wording, in the middle of a Mexican conversation.
- "sí, de NL" is a yes to the license question, not a location: Nuevo León is where the license was issued.
- "full time bro" / "y el horario me da igual" / "flexible pues" arrive within a minute. Every message updates the record, but only the last one gets a reply. The two replies marked *not delivered* were dropped, so the next question Brandon actually sees is the experience one, asked once. Because "whatever works" was the latest message, that one question comes out in English.
- A second stumble, left visible. "2 years on uber eats en houston" is stored as `other` instead of `uber_eats` (the read-back says "otra plataforma"). The years are right and the summary still names Uber Eats. In the V9 full run the same scenario stored `uber_eats`.
- Otherwise Mexican vocabulary ("licencia de manejo", "colonia", "tiempo completo").

## Conversation

*Friday 23 October 2026*

**Alex** · 13:20  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 13:21  
> simón dale

**Alex** · 13:21  
Genial, gracias. ¿Me podrías compartir tu nombre y apellido completos?

> **Candidate** · 13:22  
> brandon garza treviño

**Alex** · 13:22  
Gracias, Brandon Garza Treviño, anotado. ¿Cuentas con licencia de manejo vigente, sí o no?

> **Candidate** · 13:23  
> oye y es de moto o de carro el reparto?

**Alex** · 13:23  
Lo que sí necesitas es permiso de conducir en vigor; el reclutador te confirmará lo del vehículo. ¿Tienes licencia de manejo vigente, sí o no?

> **Candidate** · 13:24  
> sí, de NL

**Alex** · 13:24  
¡Buenísimo, Brandon, anotado! ¿En qué ciudad vives y en qué colonia o barrio?

> **Candidate** · 13:25  
> vivo en monterrey en la colonia mitras

**Alex** · 13:25  
Perfecto, anotado Monterrey. ¿Buscas tiempo completo, medio tiempo, fines de semana o una combinación?

> **Candidate** · 13:25  
> full time bro

**Alex** · 13:25 *(not delivered: a newer message was waiting)*  
Genial, anotado que buscas tiempo completo. ¿Qué turnos te acomodan mejor: mañanas, tardes, noches o horario flexible?

> **Candidate** · 13:25  
> y el horario me da igual

**Alex** · 13:25 *(not delivered: a newer message was waiting)*  
Anotado, horario flexible. ¿Has trabajado antes de repartidor con alguna app como Uber Eats, Rappi o DiDi Food, y por cuánto tiempo?

> **Candidate** · 13:26  
> flexible pues, whatever works

**Alex** · 13:26  
Have you done delivery work before, with apps like Uber Eats, Rappi or DiDi Food, and for how long?

> **Candidate** · 13:26  
> yeah 2 years on uber eats en houston

**Alex** · 13:26  
Genial, anotado: dos años con Uber Eats en Houston. ¿Desde cuándo podrías empezar?

> **Candidate** · 13:27  
> el lunes que viene bro

**Alex** · 13:27  
¡Gracias, Brandon! Repasemos: Brandon Garza Treviño, licencia de manejo: sí, Monterrey, tiempo completo, horario flexible, otra plataforma 2 años, empiezas el lunes 26 de octubre. ¿Está todo bien?

> **Candidate** · 13:28  
> simon todo bien 👍

**Alex** · 13:28 *(close)*  
¡Listo, Brandon! Un reclutador de Grupo Sazón te escribirá en los próximos días para concertar una entrevista. ¡Gracias por tu tiempo!

## What the recruiter gets

> Brandon Garza Treviño queda como calificado para el puesto de Repartidor, sin motivos de revisión ni banderas. Vive en Monterrey, tiene licencia de manejo, busca tiempo completo con horario flexible, y puede empezar el lunes 26 de octubre de 2026. Tiene 2 años de experiencia repartiendo con Uber Eats en Houston, que el registro guarda como "otra plataforma". Como la licencia es un requisito del puesto, no cuenta como extra (preference_score 0). Conviene confirmar en la llamada la fecha de inicio, que dio como "el lunes que viene", y que su experiencia fue en Estados Unidos. La conversación mezcló español e inglés, y él confirmó el resumen sin correcciones.

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
        "platform": "other",
        "years": 2.0
      }
    ],
    "start_date": "2026-10-26"
  },
  "flags": [],
  "disqualify_reason": null,
  "review_reasons": [],
  "preference_score": 0.0
}
```
