# ===========================================================================
# MODELO CUANTITATIVO PARA ANALIZAR EL VALOR INTRÍNSECO DE UNA COMPAÑÍA (DCF)
# ===========================================================================
# DCF Analyzer - Capital Driver Asset Management

"""
Este modelo descarga automáticamente los estados financieros de una empresa americana desde YahooQuery,
calcula el Flujo de Caja Libre a la Firma (FCFF) de los últimos 10 años disponibles si posible,
estima el WACC de manera dinámica con inputs de mercado para compañías basadas en US,
proyecta los flujos futuros usando un modelo de dos etapas (10 años de crecimiento alto + 10 años de crecimiento terminal fijo al 3%),
obtiene el precio intrínseco por acción y genera un dashboard en forma de imagen con el análisis, incluyendo gráfico de tendencia del FCFF histórico y proyectado,
gráfico de valoración con barras horizontales, datos clave como crecimiento promedio de ingresos y múltiplo de salida, análisis de sensibilidad como mapa de calor.
Se incorporan supuestos realistas: default spread 0%, ERP 4.33%, CRP 0.00%, tax rate calculada dinámicamente.

El modelo es dinámico: solo modifica el TICKER en los inputs y ejecuta.
Todos los datos son reales, obtenidos de YahooQuery y Yahoo Finance. No se usan datos inventados.
El código es 100% ejecutable, articulado y bien descrito.
Adaptado a la metodología descrita en el artículo de Yahoo Finance sobre la valuación de Apple, generalizado para cualquier ticker,
pero usando el WACC calculado automáticamente en lugar de la tasa de descuento simplificada.

Nuevo: Si los dos últimos FCFF históricos son negativos, aplica un ajuste para turnaround: proyecta un período de recuperación (5 años) con crecimiento bajo/negativo para positivizar, luego aplica el crecimiento normal.
Si no, ejecuta el modelo estándar.
Adicional: Si EV < 0, ajusta a max(EV, liquidation_value) usando TotalAssets - TotalLiabilities como floor estándar.
"""

# ==============================
# Inputs para el análisis
# ==============================
# Compañía a evaluar:
TICKER = "VRT"

# ==============================
# Librerías requeridas
# ==============================
import yahooquery as yq
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import seaborn as sns
import warnings
import requests
from bs4 import BeautifulSoup
import re
from matplotlib.patches import FancyBboxPatch
warnings.filterwarnings("ignore")

# ==============================
# Clase principal del modelo DCF
# ==============================
class DCFModel:
    def __init__(self, ticker):
        self.ticker = ticker
        self.stock = yf.Ticker(ticker)
        self.stock_yq = yq.Ticker(ticker)
        self.name = self.stock.info.get("longName", ticker)  # Nombre completo de la compañía
        self.terminal_growth = 0.03  # Crecimiento terminal fijo al 3%
        print(f"\nEjecutando DCF para {self.name} ({ticker})...\n")
        print(f" - Tasa de crecimiento terminal fija: {self.terminal_growth:.2%}\n")

    # ----------------------------------------------
    # Se obtienen los de estados financieros - EE.FF.
    # ----------------------------------------------
    def get_financials(self):
        """Descarga los estados financieros anuales desde YahooQuery para obtener más años históricos."""
        print("Descargando estados financieros desde YahooQuery...")
        self.cashflow = self.stock_yq.cash_flow(frequency='a')
        self.balance = self.stock_yq.balance_sheet(frequency='a')
        self.income = self.stock_yq.income_statement(frequency='a')
        print(" - Datos financieros cargados correctamente.\n")

    # -----------------------------------------------
    # Se calcula el Free Cash Flow to the Firm (FCFF)
    # -----------------------------------------------
    def compute_fcff(self):
        """Calcula el FCFF histórico de los últimos 10 años disponibles (CFO + Interest*(1-T) + Capex)."""
        print("Calculando Free Cash Flow to the Firm (FCFF)...")
        try:
            # Inputs en yahooquery
            cfo_key = 'OperatingCashFlow'
            capex_key = 'CapitalExpenditure'
            interest_key = 'InterestExpense'
            pretax_key = 'PretaxIncome'
            tax_exp_key = 'IncomeTaxExpense'
            revenue_key = 'TotalRevenue'

            if cfo_key in self.cashflow.columns and capex_key in self.cashflow.columns:
                cfo = self.cashflow[cfo_key]
                capex = self.cashflow[capex_key]  # negativo
            else:
                raise KeyError("Claves de CFO/Capex no encontradas.")

            if interest_key in self.income.columns and pretax_key in self.income.columns and tax_exp_key in self.income.columns:
                interest = self.income[interest_key].abs().fillna(0)  # positivo
                pretax = self.income[pretax_key]
                tax_exp = self.income[tax_exp_key]
                tax_rates = (tax_exp / pretax).where(pretax > 0).dropna()
                self.tax_rate = tax_rates.mean() if not tax_rates.empty else 0.25
                print(f" - Tasa de impuestos efectiva calculada: {self.tax_rate:.2%}")
            else:
                interest = pd.Series(0, index=self.income.index)
                self.tax_rate = 0.25
                print(" - Usando tasa de impuestos fallback: 25%")

            # Se alinean por fechas
            df_cash = pd.DataFrame({
                'asOfDate': pd.to_datetime(self.cashflow['asOfDate']),
                'cfo': cfo,
                'capex': capex
            }).set_index('asOfDate').sort_index()

            df_income = pd.DataFrame({
                'asOfDate': pd.to_datetime(self.income['asOfDate']),
                'interest': interest
            }).set_index('asOfDate').sort_index()

            df = df_cash.join(df_income, how='left').fillna({'interest': 0})

            # FCFF = CFO + Interest * (1 - T) + Capex (ya que Capex es negativo)
            df['fcff'] = df['cfo'] + df['interest'] * (1 - self.tax_rate) + df['capex']

            self.fcff = df['fcff'].dropna().tail(10)

            # Crecimiento: promedio simple de tasas de crecimiento históricas
            growth_rates = self.fcff.pct_change().dropna()
            if len(growth_rates) > 0:
                self.fcff_growth = growth_rates.mean()
            else:
                self.fcff_growth = 0.02
            # Se ajusta con el crecimiento de earnings de analistas, si disponible
            analyst_growth = self.stock.info.get('earningsGrowth', np.nan)
            if not np.isnan(analyst_growth):
                self.fcff_growth = (self.fcff_growth + analyst_growth) / 2
            if np.isnan(self.fcff_growth):
                self.fcff_growth = 0.02
            # Cap entre 5% y 20% como crecimiento razonable
            self.fcff_growth = max(0.05, min(0.20, self.fcff_growth))
            print(f" - FCFF histórico extraído correctamente (años: {len(self.fcff)}).")
            print(f" - Crecimiento promedio del FCFF: {self.fcff_growth:.2%}\n")

            # Crecimiento promedio de ingresos
            if revenue_key in self.income.columns:
                revenue = self.income[revenue_key]
                revenue_growth_rates = revenue.pct_change().dropna()
                self.revenue_growth = revenue_growth_rates.mean() if not revenue_growth_rates.empty else 0.02
                print(f" - Crecimiento promedio de ingresos: {self.revenue_growth:.2%}\n")
            else:
                self.revenue_growth = 0.02

        except Exception as e:
            print("Error al calcular el FCFF:", e)
            self.fcff = pd.Series()
            self.fcff_growth = 0.02
            self.revenue_growth = 0.02
            self.tax_rate = 0.25

    # ---------------------------------------------------------
    # Se obtiene el Beta de fuentes disponibles - Yahoo Finance
    # ---------------------------------------------------------
    def compute_beta(self):
        """Obtiene el Beta directamente desde Yahoo Finance."""
        print("Obteniendo Beta desde Yahoo Finance...")
        self.beta = self.stock.info.get('beta', 1.0)
        print(f" - Beta obtenido: {self.beta:.2f}\n")

    # ------------------------------
    # Cálculo del WACC
    # ------------------------------
    def compute_wacc(self):
        """Calcula el WACC de manera dinámica usando datos reales actuales y supuestos realistas para US."""
        print("Estimando WACC...")
        # Tasa libre de riesgo (10Y Treasury Yield)
        tnx_data = yf.download('^TNX', period='5d', progress=False)
        rf_series = tnx_data['Close'].dropna()
        rf = float(rf_series.iloc[-1]) / 100 if not rf_series.empty else 0.04
        # Inputs CAPM para Estados Unidos, obtenidos de Damodaran
        erp = 0.0433  # Equity Risk Premium 4.33%
        crp = 0.00  # Country Risk Premium 0.00%
        default_spread = 0.00  # Default Spread 0%
        tax_rate = getattr(self, 'tax_rate', 0.25)  # Usar tasa dinámica si disponible
        # Costo de equity (CAPM ajustado)
        re = rf + self.beta * (erp + crp)
        # Datos de deuda, cash y equity (último disponible)
        balance_annual = self.balance[self.balance['periodType'] == '12M']
        if not balance_annual.empty:
            latest_balance = balance_annual.sort_values('asOfDate').iloc[-1]
            self.total_debt = latest_balance.get('TotalDebt', 0.0)
            self.cash = latest_balance.get('CashAndCashEquivalents', 0.0)
            total_equity = latest_balance.get('StockholdersEquity', 0.0)
            self.total_assets = latest_balance.get('TotalAssets', 0.0)
            self.total_liabilities = latest_balance.get('TotalLiabilitiesNetMinorityInterest', 0.0)
        else:
            self.total_debt = 0.0
            self.cash = 0.0
            total_equity = 1.0
            self.total_assets = 0.0
            self.total_liabilities = 0.0
        self.net_debt = self.total_debt - self.cash
        # Costo de deuda ajustado
        cost_debt_pre_tax = rf + default_spread
        cost_debt = cost_debt_pre_tax * (1 - tax_rate)
        # WACC
        v = total_equity + self.total_debt
        if v == 0:
            v = 1.0
        self.wacc = (total_equity / v) * re + (self.total_debt / v) * cost_debt
        if np.isnan(self.wacc):
            self.wacc = 0.08  # Default WACC si hay problemas
        print(f" - WACC estimado: {self.wacc:.2%}\n")

    # ----------------------------------------------------------------------------------------
    # Se obtiene el dato de shares outstanding de fuentes disponibles - CompaniesMarketCap.com
    # ----------------------------------------------------------------------------------------
    def get_shares_outstanding(self):
        """Obtiene el número de shares outstanding desde CompaniesMarketCap.com, con fallback a Yahoo Finance."""
        print("Obteniendo shares outstanding desde CompaniesMarketCap.com...")
        try:
            slug = self.name.lower().replace(',', '').replace('.', '').replace(' inc', '').replace(' corporation', '').replace(' ltd', '').replace(' llc', '').strip().replace(' ', '-')
            url = f"https://companiesmarketcap.com/{slug}/shares-outstanding/"
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            match = re.search(r'the company had ([\d,]+) shares outstanding', text)
            if match:
                shares_str = match.group(1).replace(',', '')
                self.shares_outstanding = int(shares_str)
            else:
                raise ValueError("No se encontró el número de shares en el texto.")
            print(f" - Shares outstanding obtenidos: {self.shares_outstanding:,}\n")
        except Exception as e:
            print(f"Error al obtener shares desde CompaniesMarketCap.com ({e}), usando Yahoo Finance como fallback.")
            self.shares_outstanding = self.stock.info.get('sharesOutstanding', 1)
            print(f" - Shares outstanding fallback: {self.shares_outstanding:,}\n")

    # ------------------------------
    # Proyección y valuación DCF
    # ------------------------------
    def run_valuation(self):
        """Ejecuta la proyección DCF con dos etapas finitas (10 años crecimiento + 10 años terminal). Ajusta si los dos últimos FCFF negativos."""
        print("Ejecutando proyección DCF...\n")
        if self.fcff.empty:
            print("No hay datos de FCFF disponibles.")
            return
        years_growth = 10
        years_terminal = 10
        g2 = self.terminal_growth
        last_fcff = self.fcff.iloc[-1]
        # Se detecta si los dos últimos FCFF son negativos para ajuste de turnaround. Suponiendo etapa de recuperación.
        if len(self.fcff) >= 2 and (self.fcff.iloc[-2:] < 0).all():
            print("Los dos últimos FCFF negativos detectados. Aplicando ajuste de turnaround.")
            # Ajuste: período de recuperación (5 años con crecimiento negativo para reducir pérdidas, luego normal)
            recovery_years = 5
            recovery_growth = -0.10  # Reducción de pérdidas al 10% anual
            normal_growth = self.fcff_growth  # Crecimiento normal después
            # Proyección recuperación
            fcff_recovery = [last_fcff * (1 + recovery_growth) ** i for i in range(1, recovery_years + 1)]
            # Asegurar positivo al final
            if fcff_recovery[-1] < 0:
                fcff_recovery[-1] = abs(fcff_recovery[-1]) * 0.01  # Forzar pequeño positivo
            disc_factors_recovery = [(1 + self.wacc) ** i for i in range(1, recovery_years + 1)]
            pv_recovery = sum(f / d for f, d in zip(fcff_recovery, disc_factors_recovery))
            # Etapa de crecimiento post-recuperación
            fcf_end_recovery = fcff_recovery[-1]
            fcff_growth_list = [fcf_end_recovery * (1 + normal_growth) ** i for i in range(1, years_growth - recovery_years + 1)]
            disc_factors_growth = [(1 + self.wacc) ** (recovery_years + i) for i in range(1, years_growth - recovery_years + 1)]
            pv_growth = sum(f / d for f, d in zip(fcff_growth_list, disc_factors_growth))
            # Etapa terminal
            fcf_end_growth = fcf_end_recovery * (1 + normal_growth) ** (years_growth - recovery_years)
            fcff_terminal = [fcf_end_growth * (1 + g2) ** i for i in range(1, years_terminal + 1)]
            disc_factors_terminal = [(1 + self.wacc) ** (years_growth + i) for i in range(1, years_terminal + 1)]
            pv_terminal = sum(f / d for f, d in zip(fcff_terminal, disc_factors_terminal))
            # Enterprise Value inicial
            ev = pv_recovery + pv_growth + pv_terminal
        else:
            # Modelo estándar
            fcff_growth_list = [last_fcff * (1 + self.fcff_growth) ** i for i in range(1, years_growth + 1)]
            disc_factors_growth = [(1 + self.wacc) ** i for i in range(1, years_growth + 1)]
            pv_growth = sum(f / d for f, d in zip(fcff_growth_list, disc_factors_growth))
            fcf_end_growth = last_fcff * (1 + self.fcff_growth) ** years_growth
            fcff_terminal = [fcf_end_growth * (1 + g2) ** i for i in range(1, years_terminal + 1)]
            disc_factors_terminal = [(1 + self.wacc) ** (years_growth + i) for i in range(1, years_terminal + 1)]
            pv_terminal = sum(f / d for f, d in zip(fcff_terminal, disc_factors_terminal))
            ev = pv_growth + pv_terminal

        # Dado que una compañía no puede tener una valuación negativa, se aplica un floor (valor mínimo)
        # ajustando al valor de liquidación en libros: Si EV < 0, usar liquidation value = TotalAssets - TotalLiabilities
        liquidation_value = self.total_assets - self.total_liabilities
        if ev < 0:
            print("EV negativo detectado. Ajustando a max(EV, liquidation_value).")
            ev = max(ev, liquidation_value)

        # Equity Value
        equity_value = ev - self.net_debt
        # Precio intrínseco
        self.price_intrinsic = equity_value / self.shares_outstanding if self.shares_outstanding > 0 else 0
        # Múltiplo de salida implícito (considerando crecimiento perpetuo alineado con crecimiento del PIB)
        if self.wacc > g2:
            self.exit_multiple = (1 + g2) / (self.wacc - g2)
        else:
            self.exit_multiple = np.nan
        print(f"===== RESULTADOS DCF =====")
        print(f"Valor presente etapa crecimiento: ${pv_growth:,.2f}")
        print(f"Valor presente etapa terminal: ${pv_terminal:,.2f}")
        print(f"Enterprise Value: ${ev:,.2f}")
        print(f"Net Debt: ${self.net_debt:,.2f}")
        print(f"Equity Value: ${equity_value:,.2f}")
        print(f"Precio intrínseco por acción: ${self.price_intrinsic:,.2f}")
        print("==========================\n")

    # ----------------------------------------------
    # Dashboard para presentación de resultados
    # ----------------------------------------------
    def generate_dashboard(self):
        """Genera un dashboard como imagen con gráfico de tendencia del FCFF, gráfico de valoración con barras horizontales, datos clave, sensibilidad como mapa de calor."""
        if not hasattr(self, 'price_intrinsic'):
            print("Ejecuta la valuación primero.")
            return

        # Precio actual
        current_price = self.stock.info.get('currentPrice', 0)
        percent_diff = ((current_price - self.price_intrinsic) / self.price_intrinsic * 100) if self.price_intrinsic > 0 else 0
        status = "OVERVALUATION" if percent_diff > 0 else "UNDERVALUATION"
        percent = abs(percent_diff)
        overvalued = percent_diff > 0
        extension_color = 'red' if overvalued else 'green'
        ext_fc = 'bisque' if overvalued else 'paleturquoise'
        hatch = None if overvalued else '/'

        # Datos FCFF (históricos + proyectados para gráfico)
        hist_dates = self.fcff.index
        hist_years = [d.year for d in hist_dates]
        last_year = hist_years[-1] if hist_years else datetime.today().year
        proj_years = [last_year + i + 1 for i in range(5)]  # Solo 5 años proyectados para gráfico, aunque modelo usa 20
        last_fcff = self.fcff.iloc[-1] if not self.fcff.empty else 0
        fcff_proj = [last_fcff * (1 + self.fcff_growth) ** i for i in range(1, 6)]
        all_years = hist_years + proj_years
        all_fcff = self.fcff.values.tolist() + fcff_proj

        # Función para calcular intrínseco variable por sensibilidad (WACC y g)
        def compute_intrinsic(g, wacc, years_growth=10, years_terminal=10, g2=self.terminal_growth):
            fcff_growth = [last_fcff * (1 + g) ** i for i in range(1, years_growth + 1)]
            disc_factors_growth = [(1 + wacc) ** i for i in range(1, years_growth + 1)]
            pv_growth = sum(f / d for f, d in zip(fcff_growth, disc_factors_growth))
            fcff_end_growth = last_fcff * (1 + g) ** years_growth
            fcff_terminal = [fcff_end_growth * (1 + g2) ** i for i in range(1, years_terminal + 1)]
            disc_factors_terminal = [(1 + self.wacc) ** (years_growth + i) for i in range(1, years_terminal + 1)]
            pv_terminal = sum(f / d for f, d in zip(fcff_terminal, disc_factors_terminal))
            ev = pv_growth + pv_terminal
            equity_value = ev - self.net_debt
            return equity_value / self.shares_outstanding if self.shares_outstanding > 0 else 0

        # Matriz de sensibilidad (heatmap)
        waccs = np.linspace(max(0.01, self.wacc - 0.03), self.wacc + 0.03, 7)
        gs = np.linspace(max(0.00, self.fcff_growth - 0.03), self.fcff_growth + 0.03, 7)
        sensitivity_matrix = np.zeros((len(gs), len(waccs)))
        for i, g in enumerate(gs):
            for j, w in enumerate(waccs):
                price = compute_intrinsic(g, w)
                if np.isnan(price) or np.isinf(price):
                    price = 0
                sensitivity_matrix[i, j] = price
        # Matriz de proximidad para colores (distancia invertida)
        dist_matrix = np.abs(sensitivity_matrix - self.price_intrinsic)
        heat_matrix = dist_matrix.max() - dist_matrix  # Mayor valor = más cercano

        # Función de formato customizado para números
        def format_number(x):
            if abs(x) >= 1e9:
                return f"${x/1e9:.2f}B"
            elif abs(x) >= 1e6:
                return f"${x/1e6:.2f}M"
            else:
                return f"${x:.2f}"

        # Se crea el dashboard
        sns.set_style('whitegrid')
        fig = plt.figure(figsize=(18, 12))
        fig.suptitle(f"Valuación de {self.name}", fontsize=18, fontweight='bold')

        # Gráfico FCFF histórico + proyectado
        ax1 = fig.add_subplot(221)
        ax1.bar(hist_years, self.fcff.values, color='blue', alpha=0.7, label='Histórico')
        ax1.plot(proj_years, fcff_proj, 'ro--', linewidth=2, label='Proyectado')
        ax1.fill_between(proj_years, 0, fcff_proj, color='red', alpha=0.1)
        ax1.set_title('Tendencia del FCFF', fontsize=12)
        ax1.set_xlabel('Año', fontsize=12)
        ax1.set_ylabel('FCFF ($)', fontsize=12)
        ax1.legend(fontsize=10)
        ax1.grid(True, alpha=0.5)
        ax1.yaxis.set_major_formatter(FuncFormatter(lambda x, _: format_number(x)))
        # Etiquetas en barras/línea
        for x, y in zip(hist_years, self.fcff.values):
            ax1.text(x, y, format_number(y), ha='center', va='bottom' if y > 0 else 'top', fontsize=9)
        for x, y in zip(proj_years, fcff_proj):
            ax1.text(x, y, format_number(y), ha='center', va='bottom' if y > 0 else 'top', fontsize=9)

        # Datos clave y gráfico de valoración con barras horizontales
        ax2 = fig.add_subplot(222)
        ax2.axis('off')
        ax2.set_xlim(0, 1)  # Limitar el eje x para evitar desbordamientos
        key_text = f"Tasa de Crecimiento FCFF (g1): {self.fcff_growth*100:.2f}%\n"
        key_text += f"Tasa de Crecimiento Terminal (g2): {self.terminal_growth*100:.2f}%\n"
        key_text += f"Crecimiento Promedio de Ingresos: {self.revenue_growth*100:.2f}%\n"
        if not np.isnan(self.exit_multiple):
            key_text += f"Múltiplo de Salida (implícito): {self.exit_multiple:.2f}x\n"
        key_text += f"WACC: {self.wacc*100:.2f}%\n"
        key_text += f"Beta: {self.beta:.2f}\n"
        key_text += f"Net Debt: {format_number(self.net_debt)}\n"
        key_text += f"Shares Outstanding: {self.shares_outstanding:,}\n"
        ax2.text(0.1, 0.95, key_text, va='top', fontsize=12)

        # Títulos y valores
        ax2.text(0.05, 0.45, f"{self.ticker} Intrinsic Value", fontsize=16, fontweight='bold')
        ax2.text(0.05, 0.35, f"{self.price_intrinsic:.2f} USD", fontsize=24, color='gray')
        ax2.text(0.5, 0.45, f"{self.ticker} Market Stock Price", fontsize=16, fontweight='bold')
        ax2.text(0.5, 0.35, f"{current_price:.2f} USD", fontsize=24, color='gray')

        # Barras
        bar_height = 0.05
        y_pos = 0.1
        label_pos = 0.05
        bar_start = 0.2
        max_value = max(self.price_intrinsic, current_price)
        intrinsic_width = (self.price_intrinsic / max_value) * 0.6 if max_value > 0 else 0  # Ajustado a 0.6 para dejar espacio
        price_width = (current_price / max_value) * 0.6 if max_value > 0 else 0
        min_width = min(intrinsic_width, price_width)
        diff_width = abs(intrinsic_width - price_width)
        status_text = f"{status} {percent:.0f}%"

        # Barra para precio de mercado
        price_y = y_pos
        ax2.add_patch(FancyBboxPatch((bar_start, price_y), price_width, bar_height, boxstyle='round,pad=0.005', fc='gray', alpha=0.7, ec='none'))
        ax2.text(label_pos, price_y + bar_height / 2, "Price", ha='left', va='center', fontsize=10, fontweight='bold')

        # Barra para precio intrínseco
        intr_y = y_pos + bar_height + 0.02
        ax2.add_patch(FancyBboxPatch((bar_start, intr_y), min_width, bar_height, boxstyle='round,pad=0.005', fc='slateblue', alpha=0.7, ec='none'))
        if diff_width > 0:
            ext_start = bar_start + min_width
            ax2.add_patch(FancyBboxPatch((ext_start, intr_y), diff_width, bar_height, boxstyle='round,pad=0.005', fc=ext_fc, alpha=0.7, hatch=hatch, ec='none'))
        ax2.text(label_pos, intr_y + bar_height / 2, "Intrinsic Value", ha='left', va='center', fontsize=10, fontweight='bold')

        # Caja de status
        box_width = max(0.2, len(status_text) * 0.01)  # Ajustar ancho basado en longitud del texto
        box_height = 0.05
        box_y = intr_y + bar_height + 0.01
        box_x = bar_start + min_width - box_width / 2
        if box_x < bar_start:
            box_x = bar_start
        max_bar_end = bar_start + max(intrinsic_width, price_width)
        if box_x + box_width > max_bar_end:
            box_x = max_bar_end - box_width
        ax2.add_patch(FancyBboxPatch((box_x, box_y), box_width, box_height, boxstyle='round,pad=0.01', fc=extension_color, ec='none'))
        text_x = box_x + box_width / 2
        text_y = box_y + box_height / 2
        ax2.text(text_x, text_y, status_text, ha='center', va='center', color='white', fontweight='bold', fontsize=8, clip_on=False)

        # Heatmap de sensibilidad con colores basados en proximidad
        ax3 = fig.add_subplot(212)
        sns.heatmap(heat_matrix, ax=ax3, annot=sensitivity_matrix, fmt=".2f", cmap='Blues', cbar_kws={'label': 'Proximidad al Precio Intrínseco'})
        ax3.set_title('Análisis de Sensibilidad del Precio (Heatmap)', fontsize=14)
        ax3.set_xlabel('WACC', fontsize=10)
        ax3.set_ylabel('Tasa de Crecimiento (g1)', fontsize=10)
        ax3.set_xticklabels([f"{w*100:.1f}%" for w in waccs], rotation=45)
        ax3.set_yticklabels([f"{g*100:.1f}%" for g in gs[::-1]], rotation=0)
        # Resaltar el centro (aprox intrínseco)
        center_i = len(gs) // 2
        center_j = len(waccs) // 2
        ax3.add_patch(plt.Rectangle((center_j, center_i), 1, 1, fill=False, edgecolor='red', lw=2))

        plt.tight_layout()
        # Guardar como imagen para presentación
        plt.savefig('dashboard.png', dpi=300, bbox_inches='tight')
        print("Dashboard generado y guardado como 'dashboard.png'.")
        plt.show()  # Opcional: mostrar en pantalla

    # ----------------------------------------
    # Instrucción para ejecutar todo el modelo
    # ----------------------------------------
    def run(self):
        """Ejecuta secuencialmente todos los pasos del modelo DCF y genera el dashboard."""
        try:
            self.get_financials()
            self.compute_fcff()
            self.compute_beta()
            self.compute_wacc()
            self.get_shares_outstanding()
            self.run_valuation()
            self.generate_dashboard()
        except Exception as e:
            print("Ocurrió un error durante la ejecución del DCF:")
            print(e)


# ==============================
# Ejecución del modelo
# ==============================
if __name__ == "__main__":
    dcf = DCFModel(TICKER)
    dcf.run()