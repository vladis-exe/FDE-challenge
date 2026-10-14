# 19_opt_out_madrid: Candidate stops mid-flow; one confirmation, then silence

**FAIL** · expected `opted_out`, got `opted_out` · 5 candidate messages · 4.5 min · $0.0009

- availability: expected None, got ['weekends']
- schedule: expected None, got ['afternoon']

*Tuesday 20 October 2026*

**Alex** · 19:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 19:01  
> Vale, empezamos

**Alex** · 19:01  
Genial, empezamos. ¿Me dices tu nombre y apellido completos?

> **Candidate** · 19:01  
> Alba Castro Prieto

**Alex** · 19:01  
Perfecto, anotado. ¿Tienes el carnet de conducir en vigor?

> **Candidate** · 19:02  
> Vale, ¿y cuántas horas serían a la semana?

**Alex** · 19:02  
Hay turnos de mañana, tarde y noche, en jornada completa, parcial o solo fines de semana. Y, volviendo a lo del carnet, ¿tienes el carnet de conducir en vigor, sí o no?

> **Candidate** · 19:03  
> Sí, tengo el carnet B en vigor. Y ya que preguntas, de momento solo me va bien tarde y fines de semana, que entre semana curro por las mañanas.

**Alex** · 19:03  
Anotado, carnet B y disponibilidad de tardes y fines de semana. ¿En qué ciudad vives y en qué barrio?

> **Candidate** · 19:04  
> sabes qué, déjalo, ya encontré otro curro. no me escribas más porfa

**Alex** · 19:04 *(close)*  
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
    "has_driver_license": true,
    "availability": [
      "weekends"
    ],
    "schedule": [
      "afternoon"
    ]
  },
  "flags": [],
  "disqualify_reason": null,
  "review_reasons": [],
  "summary": "Opted out at stage done.",
  "preference_score": 0
}
```
