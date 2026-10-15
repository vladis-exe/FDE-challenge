# 10_no_license_puebla: Candidate without a license is disqualified politely and early

**FAIL** · expected `disqualified`, got `disqualified` · 2 candidate messages · 2.2 min · $0.0038

- full_name: expected 'Luis Ángel Morales Cruz', got 'Luis Ángel'

*Tuesday 20 October 2026*

**Alex** · 10:30  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 10:31  
> Orale, sí, va. Soy Luis Ángel

**Alex** · 10:31  
Genial, Luis Ángel, anotado. ¿Tienes licencia de manejo vigente, sí o no?

> **Candidate** · 10:32  
> No, no tengo licencia, nunca la saqué. Pero manejo desde chavo, sé manejar bien.

**Alex** · 10:32 *(close)*  
Gracias, Luis. Para este puesto es indispensable tener licencia de manejo, así que ahora no podemos seguir con tu solicitud; si más adelante cumples este requisito, ¡nos encantará saber de ti!

## Final record

```json
{
  "conversation_id": "eval-10_no_license_puebla",
  "vacancy_id": "driver",
  "status": "disqualified",
  "language": "es",
  "fields": {
    "full_name": "Luis Ángel",
    "has_driver_license": false
  },
  "flags": [],
  "disqualify_reason": "no_license",
  "review_reasons": [],
  "summary": "Luis Ángel quedó descalificado para el puesto de Repartidor porque no cuenta con licencia de manejo vigente, requisito indispensable. Dijo que nunca la sacó, aunque afirma que maneja desde joven y lo hace bien. La conversación terminó en esa pregunta, así que no hay datos de disponibilidad, horario, experiencia ni fecha de inicio. No hay campos marcados para revisar ni preguntas pendientes del candidato.",
  "preference_score": 0.0
}
```
