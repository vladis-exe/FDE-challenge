# 06_correction_at_confirm_guadalajara: Candidate corrects two fields in one message at the read-back

**PASS** · expected `qualified`, got `qualified` · 10 candidate messages · 6.8 min · $0.0069

*Tuesday 20 October 2026*

**Alex** · 12:00  
¡Hola! Soy Alex, el asistente virtual (IA) de Grupo Sazón 👋 Son 7 preguntas rápidas sobre el puesto de repartidor, unos 3 minutos. Tus datos solo se usan para esta candidatura: https://gruposazon.example/privacidad. ¿Empezamos?

> **Candidate** · 12:00  
> jaja hola! si, empecemos

**Alex** · 12:00  
¡Genial! Para empezar, ¿me das tu nombre y apellido?

> **Candidate** · 12:01  
> María Guadalupe Torres Ríos

**Alex** · 12:01  
¡Gracias, María Guadalupe! ¿Cuentas con licencia de manejo vigente?

> **Candidate** · 12:02  
> si tengo licencia de manejo, vigente jaja

**Alex** · 12:02  
Perfecto, anotado. ¿En qué ciudad vives y en qué colonia?

> **Candidate** · 12:02  
> vivo en colonia providencia, guadalajara

**Alex** · 12:02  
¡Genial, Guadalajara! ¿Buscas tiempo completo, medio tiempo, fines de semana o una combinación?

> **Candidate** · 12:03  
> medio tiempo jaja

**Alex** · 12:03  
Perfecto, medio tiempo anotado. ¿Qué turno te funciona mejor: mañanas, tardes, noches u horario flexible?

> **Candidate** · 12:04  
> mañanas oki

**Alex** · 12:04  
¡Genial, turno de mañana anotado! ¿Has trabajado en reparto antes, con Uber Eats, Rappi o DiDi Food, y cuánto tiempo?

> **Candidate** · 12:05  
> no nunca he repartido jaja

**Alex** · 12:05  
Anotado, no hay problema con que sea tu primera vez. ¿Para cuándo podrías empezar?

> **Candidate** · 12:05  
> jaja pues el 2 de noviembre

**Alex** · 12:05  
¡Gracias, María! Repasemos: María Guadalupe Torres Ríos, licencia de manejo: sí, Guadalajara, medio tiempo, mañanas, sin experiencia en reparto, empiezas el lunes 2 de noviembre. ¿Está todo bien?

> **Candidate** · 12:06  
> ah espérate jaja ya no, mejor tiempo completo porque ya me salgo de la tienda, y entonces puedo empezar desde el lunes 26

**Alex** · 12:06  
¡Gracias, María! Repasemos: María Guadalupe Torres Ríos, licencia de manejo: sí, Guadalajara, tiempo completo, mañanas, sin experiencia en reparto, empiezas el lunes 26 de octubre. ¿Está todo bien?

> **Candidate** · 12:06  
> si, todo bien jaja

**Alex** · 12:06 *(close)*  
¡Listo, María! Un reclutador de Grupo Sazón te escribirá en los próximos días para agendar una entrevista. ¡Gracias por tu tiempo!

## Final record

```json
{
  "conversation_id": "eval-06_correction_at_confirm_guadalajara",
  "vacancy_id": "driver",
  "status": "qualified",
  "language": "es",
  "fields": {
    "full_name": "María Guadalupe Torres Ríos",
    "has_driver_license": true,
    "location": {
      "country": "MX",
      "city": "guadalajara"
    },
    "availability": [
      "full_time"
    ],
    "schedule": [
      "morning"
    ],
    "experience": [],
    "start_date": "2026-10-26"
  },
  "flags": [],
  "disqualify_reason": null,
  "review_reasons": [],
  "summary": "María Guadalupe Torres Ríos califica para el puesto de Repartidor, sin motivos de revisión ni banderas en el registro. Vive en Guadalajara, tiene licencia de manejo, disponibilidad de tiempo completo en turno de mañana, no tiene experiencia previa en reparto y puede empezar el 26 de octubre de 2026. Conviene saber que al confirmar corrigió sus datos: primero dijo medio tiempo y empezar el 2 de noviembre, y luego cambió a tiempo completo y al 26 de octubre porque dejaría su empleo actual; la versión final fue confirmada por ella.",
  "preference_score": 0.0
}
```
