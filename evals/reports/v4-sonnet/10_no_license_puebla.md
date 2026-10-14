# 10_no_license_puebla: Candidate without a license is disqualified politely and early

**PASS** · expected `disqualified`, got `disqualified` · 3 candidate messages · 3.1 min · $0.0137

*Tuesday 20 October 2026*

**Alex** · 10:30  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 10:31  
> orale, si claro, empecemos

**Alex** · 10:31  
¡Va, empecemos! ¿Me dices tu nombre y apellido?

> **Candidate** · 10:32  
> luis ángel morales cruz

**Alex** · 10:32  
Perfecto, anotado. ¿Tienes licencia de manejo vigente?

> **Candidate** · 10:33  
> no, licencia no tengo, nunca saqué. pero si se manejar desde morro

**Alex** · 10:33 *(close)*  
Gracias, luis. Para este puesto es indispensable tener licencia de manejo, así que ahora no podemos seguir con tu solicitud; si la consigues, ¡nos encantará saber de ti!

## Final record

```json
{
  "conversation_id": "eval-10_no_license_puebla",
  "status": "disqualified",
  "language": "es",
  "full_name": "luis ángel morales cruz",
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
  "summary": "Candidato descalificado por no contar con licencia de manejo: Luis Ángel Morales Cruz indicó que nunca la ha tramitado, aunque dice saber manejar desde joven. La conversación se cortó en esa pregunta, así que no hay datos de ciudad, disponibilidad, horario, experiencia en reparto ni fecha de inicio. No hay campos marcados ni preguntas pendientes del candidato; Alex le comunicó que podría volver a postularse si obtiene la licencia."
}
```
