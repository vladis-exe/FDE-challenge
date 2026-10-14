# 19_opt_out_madrid: Candidate stops mid-flow; one confirmation, then silence

**FAIL** · expected `opted_out`, got `opted_out` · 3 candidate messages · 2.4 min · $0.0125

- full_name: expected 'Alba Castro Prieto', got 'castro prieto'

*Tuesday 20 October 2026*

**Alex** · 19:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 19:01  
> dale, soy Alba, tengo el carnet B por si acaso

**Alex** · 19:01  
Genial, anotado lo del carnet. Solo me falta tu apellido, ¿me lo dices para completar tu nombre?

> **Candidate** · 19:01  
> castro prieto

**Alex** · 19:01  
Perfecto, anotado. ¿En qué ciudad vives y en qué barrio?

> **Candidate** · 19:02  
> sabes qué, déjalo, ya encontré otro curro. no me escribas más porfa

**Alex** · 19:02 *(close)*  
Entendido, no te escribiré más. ¡Mucha suerte!

## Final record

```json
{
  "conversation_id": "eval-19_opt_out_madrid",
  "status": "opted_out",
  "language": "es",
  "full_name": "castro prieto",
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
