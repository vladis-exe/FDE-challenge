# 06_correction_at_confirm_guadalajara: Candidate corrects two fields in one message at the read-back

**PASS** · expected `qualified`, got `qualified` · 10 candidate messages · 6.8 min · $0.0487

*Tuesday 20 October 2026*

**Alex** · 12:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 12:00  
> oki, dale

**Alex** · 12:00  
¡Va, empezamos! ¿Me dices tu nombre completo, con nombre y apellido?

> **Candidate** · 12:01  
> María Guadalupe Torres Ríos

**Alex** · 12:01  
Listo, anotado. ¿Tienes licencia de manejo vigente?

> **Candidate** · 12:02  
> si, si tengo mi licencia de manejo

**Alex** · 12:02  
¡Genial, anotado! ¿En qué ciudad vives y en qué colonia?

> **Candidate** · 12:02  
> vivo en guadalajara, colonia providencia

**Alex** · 12:02  
Va, Guadalajara anotado. ¿Buscas jornada completa, media jornada, fines de semana o una combinación?

> **Candidate** · 12:03  
> media jornada por ahora

**Alex** · 12:03  
Anotado, media jornada. ¿Qué turnos te acomodan más: mañanas, tardes, noches o eres flexible?

> **Candidate** · 12:04  
> mañanas

**Alex** · 12:04  
Anotado, mañanas. ¿Has hecho reparto antes (Rappi, Uber Eats, DiDi Food) y por cuánto tiempo, o sería tu primera vez?

> **Candidate** · 12:05  
> no nunca he repartido

**Alex** · 12:05  
Sin problema, para empezar no hace falta experiencia. ¿Cuándo podrías empezar?

> **Candidate** · 12:05  
> el 2 de noviembre

**Alex** · 12:05  
¡Gracias, María! Repasemos: María Guadalupe Torres Ríos, licencia de manejo: sí, Guadalajara, medio tiempo, mañanas, sin experiencia en reparto, empiezas el lunes 2 de noviembre. ¿Está todo bien?

> **Candidate** · 12:06  
> ah espérate jaja ya no, mejor tiempo completo porque ya me salgo de la tienda, y entonces puedo empezar desde el lunes 26

**Alex** · 12:06  
¡Gracias, María! Repasemos: María Guadalupe Torres Ríos, licencia de manejo: sí, Guadalajara, tiempo completo, mañanas, sin experiencia en reparto, empiezas el lunes 26 de octubre. ¿Está todo bien?

> **Candidate** · 12:06  
> si, todo bien 👍

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
  "summary": "Resultado: calificada, sin motivos de descarte ni banderas de revisión. Cuenta con licencia de manejo, vive en Guadalajara, y su disponibilidad es de tiempo completo en turno de mañana, sin experiencia previa en reparto; puede empezar el lunes 26 de octubre de 2026. Conviene tener presente que al confirmar el resumen corrigió sus datos: primero dijo media jornada con inicio el 2 de noviembre, y luego cambió a tiempo completo con inicio el 26 de octubre, y confirmó esta última versión."
}
```
