# 17_unresolved_location_madrid: Candidate won't name a city; flagged after two re-asks and the flow moves on

**FAIL** · expected `needs_review`, got `opted_out` · 5 candidate messages · 3.5 min · $0.0010

- availability: expected ['full_time'], got None
- preferred_schedule: expected ['afternoon'], got None
- delivery_experience: expected [{'platform': 'glovo', 'years': 1.0}], got None
- start_date: expected '2026-10-26', got None

*Monday 19 October 2026*

**Alex** · 13:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 13:00  
> vale empezamos

**Alex** · 13:00  
¡Genial, vamos allá! ¿Me dices tu nombre y tus apellidos?

> **Candidate** · 13:01  
> Javier Moreno Gil

**Alex** · 13:01  
Perfecto, anotado. ¿Tienes el carnet de conducir en vigor?

> **Candidate** · 13:02  
> sí, carnet B

**Alex** · 13:02  
Genial, con carnet B vas bien. ¿En qué ciudad vives y en qué barrio?

> **Candidate** · 13:02  
> por la zona sur

**Alex** · 13:02  
¿En qué ciudad vives y en qué barrio exactamente?

> **Candidate** · 13:03  
> eso da igual no? prefiero no decirlo

**Alex** · 13:03 *(close)*  
Entendido, no te escribiré más. ¡Mucha suerte!

## Final record

```json
{
  "conversation_id": "eval-17_unresolved_location_madrid",
  "status": "opted_out",
  "language": "es",
  "full_name": "Javier Moreno Gil",
  "has_driver_license": true,
  "country": null,
  "city": null,
  "availability": null,
  "preferred_schedule": null,
  "delivery_experience": null,
  "start_date": null,
  "flags": [],
  "disqualify_reason": null,
  "review_reasons": [],
  "summary": "Opted out at stage done."
}
```
