# 24_kitchen_out_of_area_merida: A required city still knocks out under the generic vacancy code path

**PASS** · expected `disqualified`, got `disqualified` · 4 candidate messages · 2.6 min · $0.0054

*Thursday 22 October 2026*

**Alex** · 16:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de ayudante de cocina, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 16:01  
> ¡Hola! Sí, empecemos

**Alex** · 16:01  
Genial, para empezar, ¿me dices tu nombre y apellido completos?

> **Candidate** · 16:01  
> Rodrigo Canul Pech

**Alex** · 16:01  
Gracias, Rodrigo, anotado. ¿En qué ciudad vives y en qué colonia o barrio?

> **Candidate** · 16:02  
> Mérida, Yucatán

**Alex** · 16:02  
Rodrigo, por ahora no estamos contratando en Mérida. ¿Confirmas que trabajarías en esa ciudad o me dices otra donde podrías trabajar?

> **Candidate** · 16:02  
> Sí, confirmo, Mérida. No me muevo de aquí, aquí vivo y aquí quiero trabajar. Si no hay lugar ahorita, ¿me pueden anotar en lista de espera?

**Alex** · 16:02 *(close)*  
Gracias, Rodrigo. De momento no contratamos en Mérida, Yucatán; si abrimos en tu zona, te avisaremos por aquí.

## Final record

```json
{
  "conversation_id": "eval-24_kitchen_out_of_area_merida",
  "vacancy_id": "kitchen_prep",
  "status": "disqualified",
  "language": "es",
  "fields": {
    "full_name": "Rodrigo Canul Pech"
  },
  "flags": [],
  "disqualify_reason": "out_of_area",
  "review_reasons": [],
  "summary": "Rodrigo Canul Pech quedó descartado para el puesto de Ayudante de cocina por estar fuera de zona: vive en Mérida, Yucatán, donde por ahora no se contrata, y confirmó que no cambiaría de ciudad. No se recabó disponibilidad, horario, experiencia ni fecha de inicio, porque la conversación terminó tras la pregunta de ubicación. Antes de cualquier contacto, conviene saber que el candidato pidió que lo anotaran en una lista de espera; Alex no respondió esa solicitud directamente y solo le dijo que se le avisaría por el chat si se abre una vacante en su zona.",
  "preference_score": 0.0
}
```
