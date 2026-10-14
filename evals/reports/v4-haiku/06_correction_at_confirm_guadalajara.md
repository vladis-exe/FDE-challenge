# 06_correction_at_confirm_guadalajara: Candidate corrects two fields in one message at the read-back

**PASS** · expected `qualified`, got `qualified` · 10 candidate messages · 6.8 min · $0.0067

*Tuesday 20 October 2026*

**Alex** · 12:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 12:00  
> oki, dale

**Alex** · 12:00  
¡Genial, vamos! ¿Me dices tu nombre y apellido, por favor?

> **Candidate** · 12:01  
> María Guadalupe Torres Ríos

**Alex** · 12:01  
Gracias, María Guadalupe, anotado. ¿Tienes licencia de manejo vigente?

> **Candidate** · 12:02  
> si, si tengo mi licencia de manejo

**Alex** · 12:02  
¡Qué bien, gracias! ¿En qué ciudad vives y en qué colonia?

> **Candidate** · 12:02  
> guadalajara, colonia providencia

**Alex** · 12:02  
¡Buenísimo, Guadalajara y Providencia anotados! ¿Buscas jornada completa, media jornada, fines de semana o una combinación?

> **Candidate** · 12:03  
> media jornada, part time

**Alex** · 12:03  
Perfecto, media jornada anotada. ¿Qué turnos te acomodan mejor: mañanas, tardes, noches o flexible?

> **Candidate** · 12:04  
> mañanas

**Alex** · 12:04  
Perfecto, turno de mañanas anotado. ¿Has hecho trabajo de reparto antes, con Uber Eats, Rappi o DiDi Food, y por cuánto tiempo?

> **Candidate** · 12:05  
> no nunca he repartido

**Alex** · 12:05  
Sin problema, no hace falta experiencia previa para empezar. ¿Desde cuándo podrías comenzar?

> **Candidate** · 12:05  
> el 2 de noviembre

**Alex** · 12:05  
¡Gracias, María! Repasemos: María Guadalupe Torres Ríos, licencia de manejo: sí, Guadalajara, medio tiempo, mañanas, sin experiencia en reparto, empiezas el lunes 2 de noviembre. ¿Está todo bien?

> **Candidate** · 12:06  
> ah espérate jaja ya no, mejor tiempo completo porque ya me salgo de la tienda, y entonces puedo empezar desde el lunes 26

**Alex** · 12:06  
¡Gracias, María! Repasemos: María Guadalupe Torres Ríos, licencia de manejo: sí, Guadalajara, tiempo completo, mañanas, sin experiencia en reparto, empiezas el lunes 26 de octubre. ¿Está todo bien?

> **Candidate** · 12:06  
> sí, todo bien 👍

**Alex** · 12:06 *(close)*  
¡Listo, María! Un reclutador de Grupo Sazón te escribirá en los próximos días para concertar una entrevista. ¡Gracias por tu tiempo!

## Final record

```json
{
  "conversation_id": "eval-06_correction_at_confirm_guadalajara",
  "status": "qualified",
  "language": "es",
  "full_name": "María Guadalupe Torres Ríos",
  "has_driver_license": true,
  "country": "MX",
  "city": "guadalajara",
  "availability": [
    "full_time"
  ],
  "preferred_schedule": [
    "morning"
  ],
  "delivery_experience": [],
  "start_date": "2026-10-26",
  "flags": [],
  "disqualify_reason": null,
  "review_reasons": [],
  "summary": "María Guadalupe Torres Ríos quedó como calificada, sin banderas ni motivos de revisión. Tiene licencia de manejo, está en Guadalajara, y su disponibilidad final es tiempo completo, turno de mañanas, con inicio el lunes 26 de octubre de 2026; no tiene experiencia previa en reparto. Ten en cuenta que al confirmar corrigió sus datos: primero dijo medio tiempo y arranque el 2 de noviembre, y luego cambió a tiempo completo y al 26 de octubre, que confirmó en el resumen final."
}
```
