# 11_out_of_area_zaragoza: Known city outside the service area, confirmed, then the waitlist

**PASS** · expected `disqualified`, got `disqualified` · 5 candidate messages · 4.0 min · $0.0054

*Wednesday 21 October 2026*

**Alex** · 12:20  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 12:21  
> Hola, sí, empecemos.

**Alex** · 12:21  
Genial, empezamos. ¿Me dices tu nombre y apellido completos?

> **Candidate** · 12:21  
> Pilar Gómez Lázaro

**Alex** · 12:21  
Perfecto, anotado. ¿Tienes carnet de conducir en vigor, sí o no?

> **Candidate** · 12:22  
> Sí, tengo el carnet B desde 1999.

**Alex** · 12:22  
Genial, lo tienes anotado. ¿En qué ciudad vives y en qué barrio?

> **Candidate** · 12:23  
> Zaragoza

**Alex** · 12:23  
Gracias, Pilar. Por ahora no estamos contratando repartidores en Zaragoza, ¿te parece bien que sea en esa ciudad o prefieres indicarme otra?

> **Candidate** · 12:23  
> Vale, pues Zaragoza. Y si no hay vacantes ahora mismo, ¿me podéis apuntar en lista de espera?

**Alex** · 12:23 *(close)*  
Gracias, Pilar. De momento no contratamos en Zaragoza; si abrimos en tu zona, te avisaremos por aquí.

## Final record

```json
{
  "conversation_id": "eval-11_out_of_area_zaragoza",
  "vacancy_id": "driver",
  "status": "disqualified",
  "language": "es",
  "fields": {
    "full_name": "Pilar Gómez Lázaro",
    "has_driver_license": true
  },
  "flags": [],
  "disqualify_reason": "out_of_area",
  "review_reasons": [],
  "summary": "Candidata descalificada por estar fuera de zona: Pilar Gómez Lázaro vive en Zaragoza, donde Grupo Sazón no contrata actualmente repartidores. Solo se recogieron su nombre y que tiene carnet de conducir en vigor (carnet B, según indica); no hay datos de disponibilidad, horario, experiencia ni fecha de incorporación, y no hay extras de preferencia. Conviene saber que preguntó si podía quedar en lista de espera; Alex solo respondió que se le avisará por el chat si se abre en su zona, sin confirmar que quede registrada en una lista.",
  "preference_score": 0
}
```
