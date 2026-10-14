# 10_no_license_puebla: Candidate without a license is disqualified politely and early

**PASS** · expected `disqualified`, got `disqualified` · 3 candidate messages · 3.1 min · $0.0041

*Tuesday 20 October 2026*

**Alex** · 10:30  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 10:31  
> Orale, sí, empecemos

**Alex** · 10:31  
¡Qué bien! Para empezar, ¿me dices tu nombre y apellido completos?

> **Candidate** · 10:32  
> Luis Ángel Morales Cruz

**Alex** · 10:32  
Gracias, Luis, anotado. ¿Tienes licencia de manejo vigente?

> **Candidate** · 10:33  
> No tengo licencia, nunca la saqué. Pero manejo desde chavo, ya se me hace fácil la moto.

**Alex** · 10:33 *(close)*  
Gracias, Luis. Para este puesto es indispensable tener licencia de manejo, así que ahora no podemos seguir con tu solicitud; si más adelante cumples este requisito, ¡nos encantará saber de ti!

## Final record

```json
{
  "conversation_id": "eval-10_no_license_puebla",
  "vacancy_id": "driver",
  "status": "disqualified",
  "language": "es",
  "fields": {
    "full_name": "Luis Ángel Morales Cruz",
    "has_driver_license": false
  },
  "flags": [],
  "disqualify_reason": "no_license",
  "review_reasons": [],
  "summary": "Candidato descalificado para el puesto de repartidor (driver): Luis Ángel Morales Cruz no tiene licencia de manejo vigente, requisito indispensable. La conversación terminó tras esa pregunta, así que no hay datos de disponibilidad, horario, experiencia laboral ni fecha de inicio. Como dato a tener en cuenta, comentó que maneja moto desde joven, pero que nunca sacó la licencia; no hay campos marcados ni preguntas pendientes.",
  "preference_score": 0
}
```
