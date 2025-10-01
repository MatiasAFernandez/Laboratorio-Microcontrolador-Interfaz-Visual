# Interfaz de Monitoreo - Planta de Vapor - VaporSur S.A.

## Descripción del Sistema

La **Interfaz de Monitoreo** es una aplicación gráfica desarrollada en Python utilizando PyQt5 y Matplotlib, diseñada para simular y visualizar en tiempo real el funcionamiento de una planta industrial que produce y distribuye vapor. El sistema integra un microcontrolador (basado en CircuitPython) que simula variables clave como presión y temperatura, junto con controles de válvulas y modos de emergencia.

### ¿Qué muestra la interfaz?
- **Gráficos en tiempo real**: Dos subgráficos principales que representan la evolución de la **presión (kPa)** y la **temperatura (°C)** a lo largo del tiempo (ventana deslizante de 20 segundos).
- **Panel de monitoreo**: Etiquetas informativas que muestran:
  - Valores actuales de presión, temperatura, válvula modulante (MV) y superheater (SH).
  - Modo de operación (Presión o Temperatura).
  - Estado del flujo (A, B o None).
  - Estado del modo de emergencia (ESD: Activado/Desactivado).
  - Estados de válvulas de alivio y purga.
  - Estado general del sistema (Normal, Advertencia, Emergencia, Recuperación, etc.).
  - Tiempo transcurrido desde el inicio de la simulación.
- **Referencias visuales en los gráficos**: Áreas sombreadas para rangos de flujo A y B, líneas de umbrales para advertencias, emergencias y recuperación.
- **Funcionalidades clave**:
  - Conexión serial automática al microcontrolador para recepción de datos en tiempo real.
  - Actualizaciones optimizadas para un rendimiento fluido (50 ms para GUI, 100 ms para datos).

## Instalación

Para ejecutar la interfaz, sigue estos pasos en un entorno Linux, macOS o Windows con Python 3.8+ instalado. Asegúrate de tener permisos para acceder a puertos seriales (en Linux, podría requerir `sudo` o configuración de udev).

### Requisitos previos
- Python 3.8 o superior.
- Acceso a un puerto serial (conecta el microcontrolador vía USB).
- Archivo `requirements.txt` en la raíz del repositorio con las dependencias: `PyQt5`, `matplotlib`, `pyserial`, `numpy`.

### Pasos de instalación
1. **Clona el repositorio**:
   Abre una terminal y ejecuta:
   ```
   git clone <URL_DEL_REPOSITORIO>
   cd <NOMBRE_DEL_REPOSITORIO>
   ```

2. **Crea un entorno virtual**:
   Crea y activa un entorno virtual para aislar las dependencias:
   ```
   python -m venv venv
   ```
   - En Windows: `venv\Scripts\activate`
   - En macOS/Linux: `source venv/bin/activate`

3. **Instala las dependencias**:
   Ejecuta el siguiente comando para instalar las librerías listadas en `requirements.txt`:
   ```
   pip install -r requirements.txt
   ```

4. **Ejecuta la aplicación**:
   Una vez instaladas las dependencias, lanza la interfaz:
   ```
   python pc_plotter.py  # Se encuentra en la carpeta UI
   ```
   La aplicación detectará automáticamente el puerto serial disponible y se conectará. Si no se encuentra un puerto, mostrará un error.

### Notas adicionales
- **Problemas con puertos seriales**: En Windows, verifica el puerto en el Administrador de Dispositivos. En Linux, asegúrate de que el usuario pertenezca al grupo `dialout`.
- **Simulación sin hardware**: Si no tienes el microcontrolador, puedes modificar el código para simular datos (ver comentarios en `SerialReader`).
- **Desactivar entorno virtual**: Al finalizar, ejecuta `deactivate`.

## Créditos

Desarrollada por el **Grupo N° 6 "Autómatas"** como proyecto de laboratorio para la materia Tecnologias para la Automatización.
