# 10_no_license_puebla: Candidate without a license is disqualified politely and early

**PASS** · expected `disqualified`, got `disqualified` · 3 candidate messages · 3.1 min · $0.0042

*Tuesday 20 October 2026*

**Alex** · 10:30  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 10:31  
> orale si, vamos 👍

**Alex** · 10:31  
¡Qué bien! Para empezar, ¿me compartes tu nombre y apellido?

> **Candidate** · 10:32  
> Luis Ángel Morales Cruz

**Alex** · 10:32  
Gracias, Luis Ángel, anotado. ¿Cuentas con licencia de manejo vigente?

> **Candidate** · 10:33  
> la verdad no tengo licencia, nunca la saqué. pero si se manejar desde morro

**Alex** · 10:33 *(close)*  
Gracias, Luis. Para este puesto es indispensable tener licencia de manejo, así que ahora no podemos seguir con tu solicitud; si la consigues, ¡nos encantará saber de ti!

## Final record

```json
{
  "conversation_id": "eval-10_no_license_puebla",
  "status": "disqualified",
  "language": "es",
  "full_name": "Luis Ángel Morales Cruz",
  "has_driver_license": false,
  "country": null,
  "city": null,
  "availability": null,
  "preferred_schedule": null,
  "delivery_experience": null,
  "start_date": null,
  "flags": [],
  "disqualify_reason": "no_license",
  "review_reasons": [],
  "summary": "Luis Ángel Morales Cruz quedó descalificado porque no tiene licencia de manejo, requisito indispensable para el puesto; el candidato indicó que nunca la ha sacado, aunque dice saber manejar desde joven. La conversación terminó en esa pregunta, así que no hay datos de ciudad, disponibilidad, horario, experiencia en reparto ni fecha de inicio. No hay campos marcados para revisión, y Alex le comentó que podría volver a postularse si consigue la licencia."
}
```
