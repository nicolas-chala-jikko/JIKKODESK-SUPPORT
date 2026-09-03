# JikkoOps — Design System & Arquitectura

## Identidad
Enterprise SaaS inspirado en Zendesk/Linear/Notion, minimalismo, alta densidad sin saturación, glassmorphism sutil, transiciones 120ms.

## Tokens (styles/tokens.css)
--bg #FAFAFA, --surface #FFFFFF, --fg #111111, --muted #6B6B6B, --border #E5E5E5, --accent #0A60C2, --copper #B8946A, --success #17A34A, --warning #EAB308, --danger #DC2626
Tipografía: sans Inter/Roboto, mono JetBrains Mono para TK/métricas, display Newsreader para títulos.
Radio: botones 8px, cards 12px, inputs 8px. Bordes 1px. Sombras 0 1px 2px rgba(0,0,0,.06).

## Equipos (exactos §6)
soporte_po_dev, soporte_dev_dev, soporte_dev_dba, tributaria, tributaria_ot, soporte_gz — color oklch, disponibilidad, ticketsAsignados, slaEnRiesgo.

## Productos §7
SILIN, SOCIA, SUBSY, DOCIA, IAM, CRM
Tributos §8: TESCC, IAP, IPU, ICA — solo si SILIN
Módulos §9 dinámicos por producto (ver utils.jsx)

## Estados §11
Nuevo, Escalado, Pdte Información, En desarrollo, Resuelto — color solo badge/punto/texto, nunca fondo.

## Persistencia
localStorage jikkoops:tickets, :tabs, :filters, :theme, :fullscreen — preparado para API.

## Checklist §37
- Carga sin errores
- TK-XXXX
- 6 equipos
- Tributo condicional
- Módulo dinámico
- Filtros ALL ... en inglés
- Tabs multiticket
- Modal amplio + Esc
- PDF iframe + download
- Unificación con validación
- Fullscreen toggle
- Gráfica días/meses/años + abiertos/resueltos/ambos con total negrilla fondo gris claro
- Dashboard 2 tabs: Métricas de soporte / Experiencia de usuario
- CSAT/NPS desde datos reales, 6 productos siempre
- Export preview + individual/concatenado
- Responsive 360-1920 sin scroll-x, 44px touch
- Dark mode nativo
