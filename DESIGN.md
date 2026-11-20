---
name: Premier Automotriz - Capital Humano
description: Sistema corporativo de atracción de talento, seguimiento operativo y BI de reclutamiento basado en SAP Fiori / Horizon.
colors:
  primary: "#0070f2"
  primary-hover: "#0057b8"
  primary-active: "#00418a"
  shell-bg: "#1d2d3e"
  shell-hover: "#26384c"
  surface: "#ffffff"
  bg-canvas: "#f5f6f8"
  border: "#d9dde3"
  border-subtle: "#e5e8ec"
  border-hover: "#b9bec5"
  text-primary: "#1d2d3e"
  text-secondary: "#475569"
  text-dark: "#374151"
  text-muted: "#59697a"
  text-separator: "#a0aec0"
  black: "#000000"
  success-text: "#0e6231"
  success-bg: "#e7f6ec"
  success-border: "#bfe7ce"
  warning-text: "#8a3c00"
  warning-bg: "#fff4e5"
  warning-border: "#feddb0"
  error-text: "#b91c1c"
  error-bg: "#ffeef0"
  error-border: "#fcced3"
  info-text: "#0057b8"
  info-bg: "#e8f3ff"
  info-border: "#b6d8ff"
typography:
  display:
    fontFamily: "'72', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "'72', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "-0.01em"
  title:
    fontFamily: "'72', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  subheadline:
    fontFamily: "'72', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1.15rem"
    fontWeight: 600
    lineHeight: 1.35
  title-sm:
    fontFamily: "'72', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 600
    lineHeight: 1.35
  body:
    fontFamily: "'72', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  body-sm:
    fontFamily: "'72', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.45
  caption:
    fontFamily: "'72', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.785rem"
    fontWeight: 500
    lineHeight: 1.4
  label:
    fontFamily: "'72', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "0.04em"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "0.04em"
rounded:
  sm: "4px"
  md: "6px"
  lg: "10px"
  pill: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "6px 14px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: "16px 20px"
---

# Sistema de Diseño: Premier Automotriz & Capital Humano

## Overview
El Sistema de Gestión de Capital Humano de Premier Automotriz adopta la filosofía visual y de interacción **SAP Fiori / Horizon**, adaptada a la dinámica operativa de agencias automotrices multimarca. El sistema prioriza alta densidad informacional legible, control de estados de SLA y procesos, accesibilidad estricta WCAG AA y ausencia total de ruido gráfico o elementos decorativos artificiales.

## Colors
* **Primario Institucional:** `#0070f2` (Azul SAP Fiori), interactivo en `#0057b8` y `#00418a`.
* **Superficies y Fondos:** Lienzo base `#f5f6f8`, tarjetas en `#ffffff`, bordes estructurados en `#d9dde3` y divisores sutiles en `#e5e8ec`.
* **Semántica de Alertas (WCAG AA $\ge 4.5:1$):**
  * *Éxito / En Tiempo:* Texto `#0e6231`, fondo `#e7f6ec`, borde `#bfe7ce`.
  * *Atención / Advertencia:* Texto `#8a3c00`, fondo `#fff4e5`, borde `#feddb0`.
  * *Crítico / Error / Vencido:* Texto `#b91c1c`, fondo `#ffeef0`, borde `#fcced3`.
  * *Informativo / Foco:* Texto `#0057b8`, fondo `#e8f3ff`, borde `#b6d8ff`.

## Typography
* **Familia Tipográfica:** `'72', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`.
* **Piso de Tamaño:** `12px` (`0.75rem`) para etiquetas secundarias, chips y metadatos. El texto principal de cuerpo se sitúa entre `14px` (`0.875rem`) y `16px`.
* **Alineación Numérica:** `font-variant-numeric: tabular-nums` es obligatorio en todas las métricas, contadores, IDs de requisición, días transcurridos y columnas monetarias.

## Layout
* **Contenedor Principal:** Ancho máximo de `1440px` centrado con padding horizontal de `1.5rem`.
* **Estructura Operativa:** Modo **Operate** con barra superior fija de `48px` (`.sap-shellbar`), sub-barra de navegación y migajas (`.sap-subbar`), y grillas adaptativas (`auto-fit, minmax(...)`).

## Elevation & Depth
* **Tarjetas:** Elevación mínima de 1px (`box-shadow: 0 1px 2px rgba(0,0,0,0.04)`) combinada con borde perimetral de 1px.
* **Menús Flotantes & Popovers:** `box-shadow: 0 4px 12px rgba(29, 45, 62, 0.12)`.
* **Prohibición:** Se rechazan sombras pesadas o halos de color difusos sin desenfoque suave.

## Shapes
* **Radios de Borde:** `4px` para controles y botones pequeños (`--sap-radius-sm`), `6px` para tarjetas y tablas (`--sap-radius-md`), `9999px` exclusivamente para badges circulares y contadores.

## Components
* **ShellBar:** Barra superior azul marino `#1d2d3e` fija con accesos principales, interruptor de densidad y campana de alertas en tiempo real.
* **Badges Semánticos:** Etiquetas rectangulares compactas de 1px sin emojis, complementadas con un micro-punto indicador (`.sap-badge-dot`).
* **Botones:** Botones sobrios con estados `:hover`, `:active` y `:focus-visible` explícitos.
* **Tablas de Datos:** Encabezados azul marino (`#1d2d3e`) o gris técnico (`#f8fafc`) con ordenamiento y paginación sincronizada.

## Do's and Don'ts
* **DO:** Emplear iconografía vectorial SVG monocromática de peso consistente.
* **DO:** Utilizar persistencia de estado en parámetros de URL (`&tab=...`) y almacenamiento local para configuraciones de usuario.
* **DON'T:** No usar emojis como sustituto de iconos corporativos.
* **DON'T:** No usar bordes laterales gruesos (`border-left: 4px`) en tarjetas o alertas (`side-tab`).
* **DON'T:** No permitir contrastes inferiores a 4.5:1 en ningún estado de texto interactivo o de advertencia.
