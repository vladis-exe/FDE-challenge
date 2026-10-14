# 18_human_request_puebla: Candidate asks for a person mid-flow and is handed off

**FAIL** · expected `needs_review`, got `needs_review` · 4 candidate messages · 3.0 min · $0.0055

- full_name: expected 'Fernanda Reyes Aguilar', got None
- has_driver_license: expected True, got None
- location: expected {'country': 'MX', 'city': 'puebla'}, got None

*Thursday 22 October 2026*

**Alex** · 11:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 11:00  
> Oiga, y ¿cuánto pagan por hora? 🙏

**Alex** · 11:00  
El pago depende de la ciudad y las horas, así que el reclutador te dará la cifra exacta en la entrevista. ¿Te gustaría empezar con las 7 preguntas rápidas?

> **Candidate** · 11:01  
> Mmm, pues quiero saber antes cuánto es más o menos. Si no, no sé si me conviene 🙏

**Alex** · 11:01  
El pago depende de la ciudad y las horas, y el reclutador te dará la cifra exacta en la entrevista. ¿Te animas a empezar con las 7 preguntas rápidas?

> **Candidate** · 11:02  
> Ay no, pero es que necesito saber si me alcanza 🙏 ¿de perdida un rango?

**Alex** · 11:02  
El pago depende de la ciudad y las horas; el reclutador te dará la cifra exacta en la entrevista. ¿Te animas a empezar con las 7 preguntas rápidas?

> **Candidate** · 11:02  
> Oiga, ¿y si me pasa con el reclutador mejor? 🙏

**Alex** · 11:02 *(close)*  
Claro, le paso tu conversación a un reclutador de Grupo Sazón, que te escribirá pronto.

## Final record

```json
{
  "conversation_id": "eval-18_human_request_puebla",
  "vacancy_id": "driver",
  "status": "needs_review",
  "language": "es",
  "fields": {},
  "flags": [],
  "disqualify_reason": null,
  "review_reasons": [
    "human_requested"
  ],
  "summary": "La candidata o candidato quedó en revisión para el puesto de repartidor porque pidió hablar con una persona (human_requested); no llegó a responder ninguna de las 7 preguntas, así que no hay datos de disponibilidad, horario, experiencia ni fecha de inicio. Preguntó tres veces cuánto pagan por hora, pidiendo al menos un rango, y Alex solo respondió que el reclutador daría la cifra en la entrevista, sin darle un monto. Conviene tener lista esa información al contactarle, ya que dijo que la necesita para decidir si le conviene el puesto, y se notaba cierta insistencia por la falta de respuesta.",
  "preference_score": 0
}
```
