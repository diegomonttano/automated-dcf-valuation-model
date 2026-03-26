# DCF Analyzer - Modelo Cuantitativo de Valuación Intrínseca

**Modelo Automatizado de Valuación DCF**  
**Desarrollado por Diego Montano**  
**Buy Side Investment Analyst (Market Strategy) — Capital Driver Asset Management**

---

## Descripción del Proyecto

Este repositorio contiene el **Modelo Automatizado de Valuación DCF** que desarrollé en Python durante mi rol actual como Buy Side Investment Analyst en **Capital Driver Asset Management** (Lima, Perú — junio 2025 a la fecha).

---

## Características Principales

- **Datos 100 % reales y actualizados** (no se inventan números)
- Cálculo automático de FCFF histórico (hasta 10 años)
- Detección inteligente de **turnaround** si los últimos dos FCFF son negativos
- WACC dinámico (beta real + Rf 10Y Treasury + ERP Damodaran 4.33 %)
- Modelo de dos etapas (10 años crecimiento alto + 10 años terminal al 3 %)
- Floor de liquidación (EV nunca negativo)
- **Dashboard visual completo** guardado como `dashboard.png`:
  - Tendencia histórica y proyectada del FCFF
  - Barras comparativas Intrínseco vs. Precio de Mercado
  - Heatmap de sensibilidad (WACC × g)
  - KPIs clave (crecimiento ingresos, múltiplo de salida implícito, etc.)
- Totalmente parametrizable (solo modifica `TICKER`)

---

## Tecnologías y Habilidades Aplicadas

- **Python** (core del modelo)
- `yahooquery`, `yfinance`, `pandas`, `numpy`, `matplotlib`, `seaborn`
- `requests` + `BeautifulSoup` (scraping inteligente de shares outstanding)
- Habilidades desarrolladas: **Python**, **Modelado Financiero (DCF)**, **Análisis Cuantitativo**, **Finanzas Cuantitativas**

---

## Instalación y Uso

### 1. Clonar el repositorio
```bash
git clone https://github.com/diegomontano/dcf-analyzer.git
cd dcf-analyzer
```

### 2. Instalar dependencias
```bash
pip install yahooquery yfinance pandas numpy matplotlib seaborn requests beautifulsoup4
```

### 3. Ejecutar el modelo
```bash
python dcf-alternative.py
```

> Solo cambia la variable `TICKER = "VRT"` (línea 45) por el ticker que desees analizar.

---

## Ejemplo de Salida

Al ejecutar con `TICKER = "VRT"` (Vertiv Holdings Co.) se genera automáticamente:

- Console con todos los cálculos paso a paso
- Archivo **`dashboard.png`** (imagen de alta resolución lista para pitch books o investment memos)
- Resultados clave:
  - Precio intrínseco por acción
  - Enterprise Value
  - Equity Value
  - % de sobre/subrevaloración vs. precio de mercado
  - Análisis de sensibilidad

---

## Estructura del Proyecto

```
dcf-analyzer/
├── dcf-alternative.py          # Script principal (100% autónomo)
├── dashboard.png               # Dashboard generado (ejemplo)
├── README.md                   # Este archivo
└── requirements.txt            # (opcional)
```

---

## Contexto Profesional

Este proyecto forma parte de mi contribución actual en **Capital Driver Asset Management**, donde veo la estrategia de inversiones en mercados globales y soluciones de cartera multiactivos (cross-assets). El modelo ha sido utilizado internamente para:

- Mejorar la selección de equities
- Apoyar la construcción de pitch books y investment memos
- Generar alpha consistente vs. S&P 500

---

## Autor

**Diego Montano**  
Economista | Inversiones y Mercados Globales  
- LinkedIn: [linkedin.com/in/diego-montano](https://www.linkedin.com/in/diego-montano/)  
- Email: montano.d@pucp.edu.pe  
- Teléfono: (+51) 998 720 030  

---

## Licencia

Este proyecto es de uso privado/académico y profesional. Si deseas utilizarlo en producción o adaptarlo, por favor contáctame.

---

**¡Gracias por visitar el repositorio!**  
Si te sirve para tu propio análisis o fondo, no dudes en dar una estrella y contactarme. Estoy abierto a colaboraciones en proyectos de finanzas cuantitativas y asset management.

*Diego Montano — Marzo 2026*
```
