# 11_out_of_area_zaragoza: Known city outside the service area, confirmed, then the waitlist

**PASS** · expected `disqualified`, got `disqualified` · 4 candidate messages · 3.5 min · $0.0192

*Wednesday 21 October 2026*

**Alex** · 12:20  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 12:21  
> sí, vale. ya tengo el carnet B desde 1999

**Alex** · 12:21  
¡Genial, anotado! ¿Me dices tu nombre y apellidos?

> **Candidate** · 12:21  
> Pilar Gómez Lázaro

**Alex** · 12:21  
Perfecto, anotado. ¿En qué ciudad vives y en qué barrio?

> **Candidate** · 12:22  
> zaragoza ciudad. el barrio no sé muy bien cómo decirlo

**Alex** · 12:22  
Ahora mismo no estamos contratando en Zaragoza. ¿Es ahí donde querrías trabajar, o puedes decirme otra ciudad?

> **Candidate** · 12:23  
> sí, en zaragoza. no puedo mudarme

**Alex** · 12:23 *(close)*  
Gracias, Pilar. De momento no contratamos repartidores en zaragoza ciudad; si abrimos en tu zona, te avisaremos por aquí.

## Final record

```json
{
  "conversation_id": "eval-11_out_of_area_zaragoza",
  "status": "disqualified",
  "language": "es",
  "full_name": "Pilar Gómez Lázaro",
  "has_driver_license": true,
  "country": null,
  "city": null,
  "availability": null,
  "preferred_schedule": null,
  "delivery_experience": null,
  "start_date": null,
  "flags": [],
  "disqualify_reason": "out_of_area",
  "review_reasons": [],
  "summary": "Candidata descartada por estar fuera de zona: vive en Zaragoza capital, donde Grupo Sazón no contrata repartidores ahora mismo, y confirmó que quiere trabajar allí y que no puede mudarse. Tiene carnet B desde 1999; no se recogieron disponibilidad, horario, experiencia ni fecha de incorporación porque la conversación terminó al detectar la zona. Alex le dijo que se le avisará si se abre contratación en su zona, así que conviene saber si eso está previsto antes de contactarla; no hay flags ni motivos de revisión."
}
```
