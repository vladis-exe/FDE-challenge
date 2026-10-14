# 17_unresolved_location_madrid: Candidate won't name a city; flagged after two re-asks and the flow moves on

**PASS** · expected `needs_review`, got `needs_review` · 11 candidate messages · 6.9 min · $0.0072

*Monday 19 October 2026*

**Alex** · 13:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 13:00  
> vale empecemos

**Alex** · 13:00  
¡Genial, vamos allá! ¿Me dices tu nombre y tus apellidos?

> **Candidate** · 13:01  
> Javier Moreno Gil

**Alex** · 13:01  
Perfecto, anotado. ¿Tienes el carnet de conducir en vigor?

> **Candidate** · 13:02  
> sí, carnet B

**Alex** · 13:02  
Genial, carnet B anotado. ¿En qué ciudad vives y en qué barrio?

> **Candidate** · 13:02  
> por la zona sur

**Alex** · 13:02  
Entiendo, la zona sur. ¿Me dices en qué ciudad vives exactamente y el barrio, por ejemplo "Madrid, Vallecas"?

> **Candidate** · 13:03  
> eso da igual no? prefiero no decirlo

**Alex** · 13:03  
Para asignarte una zona necesito la ciudad y el barrio, por ejemplo "Madrid, Vallecas". ¿En qué ciudad vives?

> **Candidate** · 13:04  
> por ahi, de verdad q da igual. sigue con lo demas

**Alex** · 13:04  
Vale, sin problema. ¿Buscas jornada completa, media jornada, fines de semana o una combinación?

> **Candidate** · 13:04  
> jornada completa

**Alex** · 13:04  
Perfecto, jornada completa anotada. ¿Qué turnos te encajan: mañanas, tardes, noches o flexible?

> **Candidate** · 13:05  
> tardes

**Alex** · 13:05  
Genial, tardes anotadas. ¿Has hecho reparto antes con Glovo, Uber Eats, Just Eat, Rappi o DiDi Food, y cuánto tiempo?

> **Candidate** · 13:06  
> sí, 1 año en glovo

**Alex** · 13:06  
Genial, un año en Glovo es buena base para el reparto. ¿Desde cuándo podrías empezar?

> **Candidate** · 13:06  
> el lunes que viene

**Alex** · 13:06  
¡Gracias, Javier! Repasemos: Javier Moreno Gil, carnet de conducir: sí, jornada completa, tardes, Glovo 1 año, empiezas el lunes 26 de octubre. ¿Está todo bien?

> **Candidate** · 13:06  
> sí, todo bien

**Alex** · 13:06 *(close)*  
¡Listo, Javier! Un reclutador de Grupo Sazón te escribirá en los próximos días para concertar una entrevista. ¡Gracias por tu tiempo!

## Final record

```json
{
  "conversation_id": "eval-17_unresolved_location_madrid",
  "status": "needs_review",
  "language": "es",
  "full_name": "Javier Moreno Gil",
  "has_driver_license": true,
  "country": null,
  "city": null,
  "availability": [
    "full_time"
  ],
  "preferred_schedule": [
    "afternoon"
  ],
  "delivery_experience": [
    {
      "platform": "glovo",
      "years": 1.0
    }
  ],
  "start_date": "2026-10-26",
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
  "summary": "Javier Moreno Gil queda en revisión porque no se pudo determinar su ubicación (país y ciudad vacíos): tras dos repreguntas respondió con evasivas (\"por ahí, da igual\"). Tiene carnet de conducir, busca jornada completa en turno de tardes, cuenta con 1 año de experiencia en Glovo y puede empezar el 26 de octubre de 2026 (\"el lunes que viene\"). Antes de llamar, conviene confirmar dónde reside o dónde quiere trabajar; el resto de datos los confirmó en el resumen sin objeciones."
}
```
