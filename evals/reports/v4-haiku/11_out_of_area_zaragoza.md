# 11_out_of_area_zaragoza: Known city outside the service area, confirmed, then the waitlist

**PASS** · expected `disqualified`, got `disqualified` · 4 candidate messages · 3.5 min · $0.0047

*Wednesday 21 October 2026*

**Alex** · 12:20  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 12:21  
> hola, sí, empezamos. Tengo el carnet B desde 1999

**Alex** · 12:21  
Genial, gracias por el dato del carnet B. ¿Me dices tu nombre y apellidos, por favor?

> **Candidate** · 12:21  
> Pilar Gómez Lázaro

**Alex** · 12:21  
Gracias, Pilar Gómez Lázaro, anotado. ¿En qué ciudad vives y en qué barrio?

> **Candidate** · 12:22  
> Vivo en Zaragoza capital. El barrio no sé si hace falta ponerlo, la verdad

**Alex** · 12:22  
Gracias por decirlo, Pilar. Ahora mismo no estamos contratando en Zaragoza, así que ¿confirmas que sería ahí donde trabajarías o me dices otra ciudad?

> **Candidate** · 12:23  
> Sí, Zaragoza. No me puedo mudar

**Alex** · 12:23 *(close)*  
Gracias, Pilar. De momento no contratamos repartidores en Zaragoza capital; si abrimos en tu zona, te avisaremos por aquí.

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
  "summary": "Candidatura descartada por estar fuera de zona: Pilar Gómez Lázaro vive en Zaragoza capital, donde Grupo Sazón no contrata repartidores ahora, y confirmó que trabajaría allí y que no puede mudarse. Indicó tener carnet B desde 1999; no se llegó a recoger disponibilidad, horario, experiencia ni fecha de incorporación. No hay campos marcados para revisar, y Alex le comunicó que se le avisará si se abre la zona."
}
```
