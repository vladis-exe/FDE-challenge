# 19_opt_out_madrid: Candidate stops mid-flow; one confirmation, then silence

**PASS** · expected `opted_out`, got `opted_out` · 4 candidate messages · 3.4 min · $0.0006

*Tuesday 20 October 2026*

**Alex** · 19:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 19:01  
> Vale, empecemos

**Alex** · 19:01  
¡Genial, empezamos! ¿Me dices tu nombre y apellido?

> **Candidate** · 19:01  
> Alba Castro Prieto

**Alex** · 19:01  
¡Gracias, Alba Castro! ¿Tienes carnet de conducir en vigor, sí o no?

> **Candidate** · 19:02  
> Sí, carnet B

**Alex** · 19:02  
Perfecto, anotado el carnet B. ¿En qué ciudad vives y en qué barrio?

> **Candidate** · 19:03  
> sabes qué, déjalo, ya encontré otro curro. no me escribas más porfa

**Alex** · 19:03 *(close)*  
Entendido, no te escribiré más. ¡Mucha suerte!

## Final record

```json
{
  "conversation_id": "eval-19_opt_out_madrid",
  "vacancy_id": "driver",
  "status": "opted_out",
  "language": "es",
  "fields": {
    "full_name": "Alba Castro Prieto",
    "has_driver_license": true
  },
  "flags": [],
  "disqualify_reason": null,
  "review_reasons": [],
  "summary": "Opted out at stage done.",
  "preference_score": 0.0
}
```
