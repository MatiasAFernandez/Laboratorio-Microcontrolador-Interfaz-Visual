import serial
import serial.tools.list_ports
import matplotlib.pyplot as plt
from collections import deque
import re
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFrame
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QSize
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import numpy as np
import time

# --- Configuración ---
MAX_POINTS = 200 # Para 20 segundos con 100ms de recolección (200 * 0.1s = 20s)
GUI_UPDATE_INTERVAL_MS = 50
DATA_COLLECTION_INTERVAL_MS = 100

# Rangos y umbrales (Se mantienen para las referencias)
P_WARN_HIGH = 380.0
P_EMERG_HIGH = 460.0
P_WARN_LOW = 250.0
P_RECOVERY = 220.0

T_WARN_HIGH = 170.0
T_EMERG_HIGH = 190.0
T_WARN_LOW = 120.0
T_PREHEAT = 110.0

FLOW_A_P_RANGE = [310, 350]
FLOW_A_T_RANGE = [140, 160]
FLOW_B_P_RANGE = [260, 300]
FLOW_B_T_RANGE = [160, 170]

# --- Colores unificados ---
COLOR_FLOW_A = '#4A90E2'  # Azul para Flujo A
COLOR_FLOW_B = '#9013FE'  # Violeta para Flujo B
COLOR_ALERT_LINE = 'red'

# ===============================================
#         LECTURA SERIAL
# ===============================================
class SerialReader(QThread):
    data_received = pyqtSignal(dict)

    def __init__(self, port, parent=None):
        QThread.__init__(self, parent)
        try:
            # Se elimina el código del simulador, se usa serial real
            self.ser = serial.Serial(port, 115200, timeout=1)
            self.running = True
            print(f"Conectado al puerto: {port}")
        except serial.SerialException as e:
            print(f"Error al abrir el puerto serial {port}: {e}")
            self.running = False
        except Exception as e:
            print(f"Error inesperado al conectar: {e}")
            self.running = False


    def run(self):
        if not self.running:
            return

        while self.running:
            try:
                # Se usa ser.read_until para asegurar la lectura de una línea completa si es posible
                line_bytes = self.ser.read_until(b'\n')
                line = line_bytes.decode('utf-8', errors='ignore').strip()
                if line:
                    data = self.parse_data(line)
                    if data:
                        # El lector serial emite los datos recibidos
                        self.data_received.emit(data)

                # [NOTA] No es necesario un time.sleep si el timeout es suficiente o si el microcontrolador
                # envía datos a una cadencia conocida (ej: 100ms)
                # Si el microcontrolador envía cada 100ms, el read_until con timeout=1 es suficiente.

            except serial.SerialException as e:
                print(f"Error de lectura serial: {e}")
                self.running = False
            except Exception as e:
                print(f"Error inesperado en lector serial: {e}")
                continue

    def stop(self):
        self.running = False
        if hasattr(self, 'ser') and self.ser.is_open:
            self.ser.close()

    def parse_data(self, line):
        # Expresión regular corregida para capturar ESTADO con ':' y otros caracteres
        patron = r"P:([\d.-]+),T:([\d.-]+),MV:([\d.-]+),SH:([\d.-]+),F:(\w+),M:(\w+),ESD:(\w+),ESTADO:([\w\s:]+),RELIEF:(\w+),PURGE:(\w+)"
        match = re.search(patron, line)
        if match:
            try:
                return {
                    'P': float(match.group(1)),
                    'T': float(match.group(2)),
                    'MV': float(match.group(3)),
                    'SH': float(match.group(4)),
                    'F': match.group(5),
                    'M': match.group(6),
                    'ESD': match.group(7),
                    'ESTADO': match.group(8),
                    'RELIEF': match.group(9),
                    'PURGE': match.group(10)
                }
            except ValueError as e:
                print(f"Error al convertir datos: {e}")
        return None

# ===============================================
#         INTERFAZ GRÁFICA PyQt5
# ===============================================
class PlotterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('VaporSur S.A. - Monitoreo del Sistema')
        self.resize(1200, 800)
        
        self.layout = QVBoxLayout(self)

        # --- Contenedor de Gráficos y Labels ---
        main_content = QHBoxLayout()
        
        # Contenedor de Gráficos
        self.plot_container = QWidget()
        self.plot_layout = QVBoxLayout(self.plot_container)
        self.plot_container.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, 
            QtWidgets.QSizePolicy.Expanding
        ) # Ajuste de tamaño
        
        # Configuración de Matplotlib
        plt.style.use('fast')
        self.fig = plt.figure(figsize=(10, 8), constrained_layout=False) # Se ajusta figsize por legendas externas
        self.fig.patch.set_facecolor('white')

        # Se usa gridspec para controlar el espaciado y el espacio extra para las leyendas
        gs = gridspec.GridSpec(2, 1, height_ratios=[1, 1], figure=self.fig, 
                               hspace=0.3, wspace=0.0) # Ajuste de espaciado

        self.ax1 = self.fig.add_subplot(gs[0])
        self.ax2 = self.fig.add_subplot(gs[1])

        self.canvas = FigureCanvas(self.fig)
        self.plot_layout.addWidget(self.canvas)
        main_content.addWidget(self.plot_container, stretch=10)
        
        # Contenedor de Labels de Monitoreo
        self.labels_container = QFrame()
        self.labels_container.setFrameShape(QFrame.StyledPanel)
        self.label_layout = QVBoxLayout(self.labels_container)
        self.labels = {}
        self.setup_labels()
        main_content.addWidget(self.labels_container, stretch=1)

        self.layout.addLayout(main_content)

        # Configurar formato de tiempo en ejes
        from matplotlib.ticker import FuncFormatter
        
        def time_formatter(x, pos):
            """Formatea el tiempo en minutos:segundos"""
            total_seconds = int(x)
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes:02d}:{seconds:02d}"
        
        # Aplicar formateador a ambos ejes X
        self.ax1.xaxis.set_major_formatter(FuncFormatter(time_formatter))
        self.ax2.xaxis.set_major_formatter(FuncFormatter(time_formatter))
        
        # Datos optimizados con numpy y tiempo real
        self.start_time = time.time()
        self.first_data_time = None  # Para tiempo relativo en gráficos desde el primer dato
        self.x_data = np.zeros(MAX_POINTS, dtype=np.float32)  # Tiempo relativo al primer dato
        self.y1_data = np.zeros(MAX_POINTS, dtype=np.float32) # Presión
        self.y2_data = np.zeros(MAX_POINTS, dtype=np.float32) # Temperatura
        self.data_index = 0
        
        # Para manejo de dummies
        self.last_p = None
        self.last_t = None
        self.last_update_time = None
        self.plot_dirty = False
        
        # Inicialización de plots optimizada
        self.line1, self.line2 = self.init_plot(self.ax1, self.ax2)
        
        # timer para actualizar el plot
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plots)
        self.update_timer.start(GUI_UPDATE_INTERVAL_MS)

        self.serial_thread = None
        self.start_serial()

    def start_serial(self):
        # Intenta encontrar el puerto
        port = self.find_port()
        if port:
            print(f"Conectado a {port}")
            try:
                self.serial_thread = SerialReader(port)
                self.serial_thread.data_received.connect(self.receive_data)
                self.serial_thread.start()
            except Exception as e:
                print(f"Fallo al iniciar el hilo serial: {e}")
                sys.exit(1)
        else:
            print("No se encontró ningún puerto serial disponible.")
            sys.exit(1)

    def find_port(self):
        ports = serial.tools.list_ports.comports()
        for p in ports:
            # Intenta abrir y cerrar el puerto para verificar si es funcional
            try:
                ser = serial.Serial(p.device, 115200, timeout=1)
                ser.close()
                return p.device
            except (serial.SerialException, OSError):
                continue
        return None

    def receive_data(self, data):
        """Recibe datos y los almacena para actualización posterior (Inmutable ante ESD)"""
        # Actualizar labels inmediatamente (sin tiempo, que se maneja en timer)
        self.update_labels_immediate(data)

        # Calcular tiempo actual absoluto y relativo para el gráfico
        current_real = time.time()
        if self.first_data_time is None:
            self.first_data_time = current_real
        graph_t = current_real - self.first_data_time
        
        # Agregar datos al buffer circular
        p, t = data['P'], data['T']
        
        # Usar indexing circular
        idx = self.data_index % MAX_POINTS
        self.x_data[idx] = graph_t
        self.y1_data[idx] = p
        self.y2_data[idx] = t
        self.data_index += 1

        # Actualizar últimos valores y tiempo de actualización (absoluto)
        self.last_p = p
        self.last_t = t
        self.last_update_time = current_real

        # Marcar como dirty para redraw
        self.plot_dirty = True

    def update_plots(self):
        """Actualización optimizada de gráficos con ventana de 20 segundos y reordenamiento"""
        # Siempre actualizar el tiempo transcurrido
        self.update_time_label()
            
        try:
            # Manejo de puntos dummy si no hay datos nuevos por más de un intervalo
            added_dummy = False
            interval_s = DATA_COLLECTION_INTERVAL_MS / 1000.0
            current_real = time.time()
            if self.first_data_time is not None and self.last_update_time is not None and self.last_p is not None:
                expected_next = self.last_update_time + interval_s
                while expected_next <= current_real:
                    # Agregar punto dummy al tiempo esperado
                    graph_t_dummy = expected_next - self.first_data_time
                    idx = self.data_index % MAX_POINTS
                    self.x_data[idx] = graph_t_dummy
                    self.y1_data[idx] = self.last_p
                    self.y2_data[idx] = self.last_t
                    self.data_index += 1
                    self.last_update_time = expected_next
                    added_dummy = True
                    expected_next += interval_s

            # Solo actualizar gráficos si hay nuevo dato real o dummy agregado
            if self.plot_dirty or added_dummy:
                # Determinar la cantidad de puntos a mostrar
                n_points = min(self.data_index, MAX_POINTS)

                if n_points == 0:
                    return

                if n_points < MAX_POINTS:
                    # Caso inicial: menos datos que el buffer completo
                    x_data = self.x_data[:n_points]
                    y1_data = self.y1_data[:n_points]
                    y2_data = self.y2_data[:n_points]
                else:
                    # Caso normal: buffer lleno, reordenar datos cronológicamente (usando la cola)
                    start_idx = self.data_index % MAX_POINTS

                    # Reordenar datos: [desde_start_idx hasta_fin] + [desde_inicio hasta_start_idx]
                    x_data = np.concatenate([self.x_data[start_idx:], self.x_data[:start_idx]])
                    y1_data = np.concatenate([self.y1_data[start_idx:], self.y1_data[:start_idx]])
                    y2_data = np.concatenate([self.y2_data[start_idx:], self.y2_data[:start_idx]])

                # Actualizar líneas
                self.line1.set_data(x_data, y1_data)
                self.line2.set_data(x_data, y2_data)
                
                # Actualizar ventana de tiempo: Asegurar que la línea toque el extremo izquierdo
                if len(x_data) > 0:
                    xmin = x_data[0]
                    xmax = x_data[-1] + interval_s * 2  # Pequeño margen
                    
                    self.ax1.set_xlim(xmin, xmax)
                    self.ax2.set_xlim(xmin, xmax)
                
                self.canvas.draw_idle()
                self.plot_dirty = False
                
        except Exception as e:
            print(f"Error actualizando gráficos: {e}")

    def update_time_label(self):
        """Actualiza solo la etiqueta de tiempo transcurrido"""
        elapsed = int(time.time() - self.start_time)
        time_str = f"{elapsed//60:02d}:{elapsed%60:02d}"
        self.labels['time'].setText(f"Tiempo Transcurrido: {time_str}")

    def update_labels_immediate(self, data):
        """Actualización inmediata y optimizada de labels (sin tiempo)"""
        try:
            p, t, mv, sh = data['P'], data['T'], data['MV'], data['SH']
            flow, mode, esd, estado = data['F'], data['M'], data['ESD'], data['ESTADO']
            relief, purge = data['RELIEF'], data['PURGE']
            
            # Actualizar solo los valores del data (tiempo se maneja por separado)
            new_values_text = f"P: {p:.1f} kPa | T: {t:.1f} °C | MV: {mv:.1f}% | SH: {sh:.1f}%"
            self.labels['values'].setText(new_values_text)
            self.labels['mode'].setText(f"Modo: {mode}")
            self.labels['flow'].setText(f"Flujo: {flow}")
            self.labels['esd'].setText(f"ESD: {esd}")
            self.labels['relief'].setText(f"Válvula de Alivio: {relief}")
            self.labels['purge'].setText(f"Válvula de Purga: {purge}")
            self.labels['status'].setText(f"Estado del Sistema: {estado}")

            # Actualización optimizada de estilos (Permite observar el monitoreo en ESD)
            self.update_label_styles(esd, estado)
            
        except Exception as e:
            print(f"Error actualizando labels: {e}")

    def update_label_styles(self, esd, estado):
        """Actualización optimizada de estilos de labels"""
        # Estilo base
        base_style = "font-size: 14px; font-weight: bold; padding: 5px; border-radius: 5px;"
        
        # Estilo para ESD
        if esd == 'Activado':
            self.labels['esd'].setStyleSheet(base_style + "background-color: red; color: white;")
        else:
            self.labels['esd'].setStyleSheet(base_style + "background-color: green; color: white;")

        # Estilo para Estado
        if any(word in estado for word in ["Alivio", "Purga", "Emergencia"]):
            self.labels['status'].setStyleSheet(base_style + "background-color: red; color: white;")
        elif any(word in estado for word in ["Advertencia", "Recuperación", "Precalentamiento"]):
            self.labels['status'].setStyleSheet(base_style + "background-color: orange; color: black;")
        else:
            self.labels['status'].setStyleSheet(base_style + "background-color: lightgreen; color: black;")
        
        # Otros labels con estilo base
        for key in ['mode', 'flow', 'values', 'relief', 'purge']:
            self.labels[key].setStyleSheet("font-size: 14px; font-weight: normal; color: #333333; padding: 5px;")

    def setup_labels(self):
        """Setup optimizado de labels con el layout vertical en el QFrame"""
        label_style = "font-size: 14px; font-weight: normal; color: #333333; padding: 5px;"
        labels_config = [
            ('status', "Estado del Sistema: Iniciando..."),
            ('esd', "ESD: --"),
            ('mode', "Modo: --"),
            ('flow', "Flujo: --"),
            ('relief', "Válvula de Alivio: --"),
            ('purge', "Válvula de Purga: --"),
            ('values', "P: -- kPa | T: -- °C | MV: --% | SH: --%"),
            ('time', "Tiempo Transcurrido: 00:00")
        ]
        
        for key, text in labels_config:
            self.labels[key] = QLabel(text)
            self.labels[key].setStyleSheet(label_style)
            self.label_layout.addWidget(self.labels[key])
        
        # Espaciador para empujar los labels hacia arriba
        self.label_layout.addStretch(1)

    def init_plot(self, ax1, ax2):
        """Inicialización de plots con leyendas externas y padding de títulos"""
        
        # --- Configuración Ejes Presión ---
        # El xlim se establece inicialmente a un rango pequeño hasta que lleguen datos
        initial_xlim = 1.0  # Pequeño rango inicial
        ax1.set_xlim(0, initial_xlim)
        ax1.set_ylim(150, 500)
        ax1.set_title('Presión (kPa) vs Tiempo', fontsize=12, pad=15) # Más padding
        ax1.set_xlabel('Tiempo (mm:ss)', fontsize=10)
        ax1.set_ylabel('Presión (kPa)', fontsize=10)
        ax1.grid(True, alpha=0.3)

        # --- Configuración Ejes Temperatura ---
        ax2.set_xlim(0, initial_xlim)
        ax2.set_ylim(80, 220)
        ax2.set_title('Temperatura (°C) vs Tiempo', fontsize=12, pad=15) # Más padding
        ax2.set_xlabel('Tiempo (mm:ss)', fontsize=10)
        ax2.set_ylabel('Temperatura (°C)', fontsize=10)
        ax2.grid(True, alpha=0.3)

        line1, = ax1.plot([], [], lw=2, color='#2E86AB', alpha=0.8, label='Presión Actual')
        line2, = ax2.plot([], [], lw=2, color='#F24236', alpha=0.8, label='Temperatura Actual')

        # --- Áreas de Flujo y Referencias de Alarma ---
        # Presión
        ax1.axhspan(FLOW_A_P_RANGE[0], FLOW_A_P_RANGE[1], facecolor=COLOR_FLOW_A, alpha=0.2, label='Rango Flujo A')
        ax1.axhspan(FLOW_B_P_RANGE[0], FLOW_B_P_RANGE[1], facecolor=COLOR_FLOW_B, alpha=0.2, label='Rango Flujo B')
        ax1.axhline(P_EMERG_HIGH, color=COLOR_ALERT_LINE, linestyle='-', lw=2, alpha=0.9, label='Emergencia P')
        ax1.axhline(P_WARN_HIGH, color='orange', linestyle='--', lw=1.5, alpha=0.7, label='Advertencia P')
        ax1.axhline(P_RECOVERY, color='blue', linestyle=':', lw=1.5, alpha=0.7, label='Recuperación P')

        # Temperatura
        ax2.axhspan(FLOW_A_T_RANGE[0], FLOW_A_T_RANGE[1], facecolor=COLOR_FLOW_A, alpha=0.2, label='Rango Flujo A')
        ax2.axhspan(FLOW_B_T_RANGE[0], FLOW_B_T_RANGE[1], facecolor=COLOR_FLOW_B, alpha=0.2, label='Rango Flujo B')
        ax2.axhline(T_EMERG_HIGH, color=COLOR_ALERT_LINE, linestyle='-', lw=2, alpha=0.9, label='Emergencia T')
        ax2.axhline(T_WARN_HIGH, color='orange', linestyle='--', lw=1.5, alpha=0.7, label='Advertencia T')
        ax2.axhline(T_PREHEAT, color='blue', linestyle=':', lw=1.5, alpha=0.7, label='Precalentamiento T')

        # --- Leyendas Externas ---
        # Ajustar la figura para hacer espacio a la derecha
        self.fig.subplots_adjust(right=0.75, top=0.9, bottom=0.1) 
        
        # Mover leyendas fuera de los gráficos
        ax1.legend(loc='center left', bbox_to_anchor=(1.05, 0.5), fontsize=8, framealpha=0.8)
        ax2.legend(loc='center left', bbox_to_anchor=(1.05, 0.5), fontsize=8, framealpha=0.8)

        return line1, line2

    def closeEvent(self, event):
        """Cierre"""
        print("Cerrando aplicación...")
        if self.update_timer:
            self.update_timer.stop()
        if self.serial_thread:
            self.serial_thread.stop()
            self.serial_thread.wait(3000)
        event.accept()

# Se necesita importar QtWidgets
from PyQt5 import QtWidgets

def main():
    print("=== VAPORSUR S.A. - MONITOR DE SISTEMA EN TIEMPO REAL ===")
    print("Buscando puerto serial para iniciar la comunicación...")
    print("Configuración:")
    print(f"  - Actualización GUI: {GUI_UPDATE_INTERVAL_MS}ms")
    print(f"  - Recolección datos: {DATA_COLLECTION_INTERVAL_MS}ms")
    print(f"  - Ventana de tiempo: {MAX_POINTS * (DATA_COLLECTION_INTERVAL_MS / 1000.0)} segundos")
    print("=" * 50)


    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = PlotterApp()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()