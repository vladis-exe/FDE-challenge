# 06_correction_at_confirm_guadalajara: Candidate corrects two fields in one message at the read-back

**PASS** · expected `qualified`, got `qualified` · 10 candidate messages · 6.8 min · $0.0066

*Tuesday 20 October 2026*

**Alex** · 12:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 12:00  
> jaja hola! sí, va

**Alex** · 12:00  
¡Genial! Para seguir, ¿me compartes tu nombre y apellido completos?

> **Candidate** · 12:01  
> María Guadalupe Torres Ríos

**Alex** · 12:01  
Perfecto, anotado, María Guadalupe Torres Ríos. ¿Tienes licencia de manejo vigente?

> **Candidate** · 12:02  
> si, tengo licencia de manejo

**Alex** · 12:02  
Anotado, gracias por confirmarlo. ¿En qué ciudad vives y en qué colonia o barrio?

> **Candidate** · 12:02  
> vivo en guadalajara, colonia providencia

**Alex** · 12:02  
Anotado, Guadalajara. ¿Buscas jornada completa, media jornada, fines de semana o una combinación de esos?

> **Candidate** · 12:03  
> media jornada

**Alex** · 12:03  
Anotado, media jornada. ¿Qué turnos te funcionan mejor: mañanas, tardes, noches o algo flexible?

> **Candidate** · 12:04  
> mañanas

**Alex** · 12:04  
Anotado, turno de mañanas. ¿Has trabajado antes en reparto, con apps como Uber Eats, Rappi o DiDi Food, o es tu primera vez?

> **Candidate** · 12:05  
> no nunca he repartido es mi primera vez jaja

**Alex** · 12:05  
Anotado, primera vez en reparto no hay problema. ¿Desde cuándo podrías empezar?

> **Candidate** · 12:05  
> el 2 de noviembre podría empezar

**Alex** · 12:05  
¡Gracias, María! Repasemos: María Guadalupe Torres Ríos, licencia de manejo: sí, Guadalajara, medio tiempo, mañanas, sin experiencia en reparto, empiezas el lunes 2 de noviembre. ¿Está todo bien?

> **Candidate** · 12:06  
> ah espérate jaja ya no, mejor tiempo completo porque ya me salgo de la tienda, y entonces puedo empezar desde el lunes 26

**Alex** · 12:06  
¡Gracias, María! Repasemos: María Guadalupe Torres Ríos, licencia de manejo: sí, Guadalajara, tiempo completo, mañanas, sin experiencia en reparto, empiezas el lunes 26 de octubre. ¿Está todo bien?

> **Candidate** · 12:06  
> sí, todo bien jaja gracias

**Alex** · 12:06 *(close)*  
¡Listo, María! Un reclutador de Grupo Sazón te escribirá en los próximos días para concertar una entrevista. ¡Gracias por tu tiempo!

## Final record

```json
{
  "conversation_id": "eval-06_correction_at_confirm_guadalajara",
  "vacancy_id": "driver",
  "status": "qualified",
  "language": "es",
  "fields": {
    "full_name": "María Guadalupe Torres Ríos",
    "has_driver_license": true,
    "location": {
      "country": "MX",
      "city": "guadalajara"
    },
    "availability": [
      "full_time"
    ],
    "schedule": [
      "morning"
    ],
    "experience": [],
    "start_date": "2026-10-26"
  },
  "flags": [],
  "disqualify_reason": null,
  "review_reasons": [],
  "summary": "María Guadalupe Torres Ríos quedó calificada para la vacante de repartidor (driver), sin banderas ni motivos de revisión. Tiene licencia de manejo, vive en Guadalajara, y su disponibilidad final es tiempo completo en turno de mañana, con inicio el 26 de octubre de 2026; no tiene experiencia previa en reparto. Durante la confirmación corrigió sus datos: había dicho media jornada y empezar el 2 de noviembre, pero cambió a tiempo completo y al 26 de octubre porque dejaría su empleo actual, y confirmó el resumen final.",
  "preference_score": 0
}
```
