# Post-Production Modular Directory Structure Specification

> **Estandar Modular de Carpetas para Postproduccion (VFX, 3D DCC, Unreal Engine, Compo e IA)**  
> **Version:** 1.0.0  
> **Autor:** Cristian Fieiras  
> **Estado:** Documento de Especificacion y Trabajo  

---

## 1. Principios y Reglas de Diseno

1. **Nomenclatura Estandar en Ingles:** Todas las carpetas se escriben en ingles, minusculas y snake_case (`incoming/`, `editorial/`, `sequences/`, `assets/`, `unreal_projects/`, `ai_lab/`). Se eliminan los prefijos numericos para mantener nombres limpios y consistentes.
2. **Arquitectura Modular:** El proyecto arranca con un **Core Base** minimo y ligero. Los departamentos especializados (Compo, 3D tradicional, Unreal Engine, IA) se suman como modulos independientes solo cuando el proyecto lo requiere.
3. **Inmutabilidad de Ingest (`incoming/`):** Todo lo que entra a `incoming/` es estrictamente de solo lectura. Nunca se trabaja, renombra ni modifica el material original recibido del cliente o del set.
4. **Versionado de Plates:** Los plates pueden cambiar durante la produccion (re-conforms de editorial, cambios de corte, nuevo debayer o correccion de color). Por tanto, `plates/` contempla versionado estricto (`v001/`, `v002/`).
5. **Revision y Delivery por Shot:** Cada plano gestiona sus renders en alta (`renders/hires/`) y revision ligera (`renders/review/`). Los renders aprobados para cliente se sincronizan a una carpeta externa (Google Drive / Frame.io / Servidor compartido). El cliente nunca accede a las carpetas internas de trabajo.
6. **Aislamiento de Unreal Engine (`unreal_projects/`):** Unreal Engine es un proyecto monolitico (`.uproject`) que compila shaders a nivel global. Para evitar duplicar gigabytes por shot, se ubica en la raiz bajo `unreal_projects/` con *Level Sequences* por shot, enviando sus renders al shot correspondiente via *Movie Render Queue (MRQ)*.

---

## 2. Core Pipeline (Comun a Todo Proyecto)

Todo proyecto nuevo inicializa con esta estructura minima:

```text
[PROJECT_CODE]/
├── incoming/                  # Ingesta cruda de clientes/rodaje (Solo Lectura)
├── editorial/                 # Montaje, conforms, offline y guias de edicion
├── sequences/                 # Desglose por secuencias y planos (Shots)
└── assets/                    # Assets globales compartidos (logos, fuentes, color/LUTs)
```

### Desglose de Carpetas Base:

#### A. `incoming/`
Organizado por fecha de recepcion y procedencia.
```text
incoming/
├── 2026-11-20_client_brief/
├── 2026-11-21_set_cam_a/
└── 2026-11-22_audio_stems/
```

#### B. `editorial/`
El centro de operaciones de montaje:
```text
editorial/
├── project_files/             # Premiere (.prproj), Resolve (.drp), Final Cut
├── conforms/                  # XML, EDL, AAF
├── offline_refs/              # Videos de corte con Burn-In de Timecode y Shot ID
└── audio/                     # Mezclas, scratch tracks, locucion, musica
```

#### C. `assets/`
Recursos globales no ligados a un shot particular:
```text
assets/
├── color/                     # Configs OCIO, CDLs, LUTs (.cube)
├── fonts/                     # Tipografias aprobadas del proyecto
├── graphics/                  # Logos, elementos de motion design, graficas vectoriales
└── references/                # Moodboards de direccion de arte, referencias de estilo
```

#### D. `sequences/` (Anatomia Base del Shot con Versionado de Plates)
Jerarquia secuencial dividida en secuencia (`sq###`) y plano (`sh###`).  
> **Nota sobre Plates:** Como los plates pueden sufrir re-conforms de editorial (cambio de cabezas/colas, nuevo debayer o ajuste de color), se versionan (`v001`, `v002`) manteniendo cada version con su respectivo proxy.

```text
sequences/
└── sq010/
    ├── _shared/               # Elementos compartidos entre planos de la misma secuencia
    └── sq010_sh010/
        ├── plates/
        │   ├── v001/          # Plate original recortado con handles (entrega inicial)
        │   │   └── proxies/   # Proxy ligero de v001 para playback rapido
        │   └── v002/          # Nueva version enviada por editorial (re-conform / cambio de corte)
        │       └── proxies/   # Proxy ligero de v002
        └── renders/
            ├── hires/         # Renders maestros en alta (EXR, ProRes 4444)
            │   ├── v001/
            │   └── v002/
            └── review/        # Videos ligeros MP4 H.264 para revision interna
                ├── sq010_sh010_v001.mp4
                └── sq010_sh010_v002.mp4
```

---

## 3. Modulos Opcionales (Se agregan a demanda)

### Modulo A: Composicion (Nuke, After Effects, Fusion)
Se activa cuando hay trabajo de 2D, limpieza, integracion o roto. Agrega dentro de cada shot:
```text
sequences/sq010/sq010_sh010/
└── comp/
    ├── scripts/               # Scripts de trabajo (.nk, .aep, .comp) versionados (v001, v002)
    └── precomps/              # Renders intermedios, caches de rotoscopia y cleanplates
```

---

### Modulo B: Inteligencia Artificial (Plataformas Web y Locales)
Para proyectos que utilizan Runway, Midjourney, Kling, Fal, Luma o ComfyUI.

> **¿Que es Inpaint?**  
> *Inpainting* es la tecnica de IA para **reemplazar, regenerar o limpiar una zona especifica** de una imagen o video a partir de una mascara (blanco y negro / roto) y un prompt. Se usa en postproduccion para borrar elementos no deseados (micros, cables, logos), cambiar ropa, regenerar fondos danados o agregar objetos manteniendo el resto del encuadre 100% original.

#### 1. A nivel raiz (global del proyecto):
```text
ai_lab/
├── prompts/                   # Hojas de prompts maestros, negative prompts y seeds
├── references/                # Moodboards para style transfer, consistencia de personajes
└── models/                    # Modelos custom, LoRAs o embeddings entrenados
```

#### 2. A nivel de cada shot:
```text
sequences/sq010/sq010_sh010/
└── ai/
    ├── references/            # Prompts especificos del shot, imagenes input, mascaras de inpaint
    └── outputs/               # Generaciones crudas descargadas de las plataformas
        ├── v001/              # Iteracion 1 (lote de variaciones o generaciones crudas)
        └── v002/              # Iteracion 2 (upscales, selecciones refinadas)
```

---

### Modulo C: 3D Tradicional DCC (Blender, Maya, Houdini, Cinema 4D)

#### 1. A nivel raiz (Assets 3D globales):
```text
assets/
└── 3d/
    ├── models/                # Personajes, vehiculos, props y entornos (.blend, .fbx, .usd)
    ├── textures/              # Sets de texturas UDIM y mapas PBR
    └── hdri/                  # Mapas de iluminacion ambiental (.exr, .hdr)
```

#### 2. A nivel de cada shot:
```text
sequences/sq010/sq010_sh010/
└── 3d/
    ├── scenes/                # Escenas de trabajo (.blend, .ma, .hip, .c4d) versionadas
    ├── tracking/              # Camaras de matchmove y puntos de tracking (.abc, .fbx)
    └── caches/                # Caches locales Alembic, USD o VDB del shot
```

---

### Modulo D: Unreal Engine (Real-Time / Virtual Production)
Nombrado directamente **`unreal_projects/`** en la raiz para total claridad.

Unreal Engine es un proyecto monolitico (`.uproject`) que compila shaders a nivel global. Se ubica en la raiz y envia sus renders al shot correspondiente:

```text
unreal_projects/
└── [PROJECT_CODE]_unreal/
    ├── Config/
    ├── Content/
    │   ├── environments/      # Niveles maestros y geometria de escenarios
    │   ├── characters/        # Skeletal meshes, animaciones y rigs
    │   ├── fx/                # Sistemas Niagara y materiales de postproceso
    │   └── cinematics/        # Level Sequences mapeadas a las secuencias de post
    │       └── sq010/
    │           ├── sq010_master_seq
    │           ├── sq010_sh010_seq
    │           └── sq010_sh020_seq
    └── [PROJECT_CODE]_unreal.uproject
```

* **Pipeline Bridge (Render):**  
  Desde Movie Render Queue (MRQ) se apunta el render directo a la carpeta del plano:  
  `sequences/sq010/sq010_sh010/renders/hires/v001/sq010_sh010_unreal_v001.####.exr`

---

## 4. Estandar de Nomenclatura de Archivos

Todos los archivos de trabajo y renders finales deben seguir la siguiente estructura de tokens:

```text
[project]_[seq]_[shot]_[depto]_[descripcion]_v[version].[ext]
```

### Ejemplos:
- **Plate con handles:** `prj_sq010_sh010_plate_v001.1001.exr`
- **Script de Comp:** `prj_sq010_sh010_comp_v002.nk`
- **Render de Unreal MRQ:** `prj_sq010_sh010_unreal_beauty_v001.1001.exr`
- **Generacion IA seleccionada:** `prj_sq010_sh010_ai_upscale_v001.png`
- **Proxy de revision interna:** `prj_sq010_sh010_comp_v002.mp4`

---

## 5. Flujo de Renders y Entrega a Cliente

1. **Trabajo en el Shot:** El artista trabaja en `comp/`, `3d/` o `ai/`.
2. **Render en Alta:** Se renderiza a `renders/hires/v001/` (secuencia EXR o ProRes).
3. **Proxy de Revision:** Se genera automaticamente un MP4 H.264 ligero con burn-in en `renders/review/sq010_sh010_v001.mp4`.
4. **Control Interno / Supervisor:** Se revisan los planos internamente.
5. **Aprobacion y Sincronizacion:** Cuando una version esta marcada como OK para cliente, ese archivo especifico se copia a la carpeta en la nube (Google Drive / Frame.io / Carpeta compartida). **El cliente jamas accede a la estructura interna de trabajo.**

---

## 6. Matriz de Combinaciones Modulares

| Carpeta / Ruta | Core | Solo Comp | 3D + Comp | Unreal + Comp | AI + Comp | Full Hybrid |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `incoming/` | SI | SI | SI | SI | SI | SI |
| `editorial/` | SI | SI | SI | SI | SI | SI |
| `assets/` | SI | SI | SI | SI | SI | SI |
| `sequences/.../plates/v###/` | SI | SI | SI | SI | SI | SI |
| `sequences/.../renders/` | SI | SI | SI | SI | SI | SI |
| `sequences/.../comp/` | NO | SI | SI | SI | SI | SI |
| `assets/3d/` & `shot/3d/` | NO | NO | SI | NO | NO | SI |
| `unreal_projects/` | NO | NO | NO | SI | NO | SI |
| `ai_lab/` & `shot/ai/` | NO | NO | NO | NO | SI | SI |

---

## 7. Estructura Maestra Completa (Full Hybrid Project Tree)

A continuacion se muestra la estructura completa con **todos los modulos activados** simultaneamente (Core + Comp + 3D + Unreal + AI):

```text
[PROJECT_CODE]/
│
├── incoming/                                  # Material crudo entrante (Read-Only)
│   ├── 2026-11-20_client_brief/
│   ├── 2026-11-21_set_cam_a/
│   └── 2026-11-22_audio_stems/
│
├── editorial/                                 # Departamento de montaje
│   ├── project_files/                         # .prproj, .drp, .fcpx
│   ├── conforms/                              # XML, EDL, AAF
│   ├── offline_refs/                          # Cortes guia con Timecode y Shot ID burn-in
│   └── audio/                                 # Mezclas, scratch, locucion, musica
│
├── assets/                                    # Recursos globales compartidos
│   ├── color/                                 # Configs OCIO, CDLs, LUTs (.cube)
│   ├── fonts/                                 # Tipografias del proyecto
│   ├── graphics/                              # Logos y disenos 2D
│   ├── references/                            # Moodboards y guias de estilo
│   └── 3d/                                    # Assets 3D globales (Modulo 3D)
│       ├── models/                            # Props, personajes, vehiculos
│       ├── textures/                          # UDIMs, mapas PBR
│       └── hdri/                              # Mapas HDR de iluminacion
│
├── unreal_projects/                           # Proyectos centralizados Unreal (Modulo Unreal)
│   └── [PROJECT_CODE]_unreal/
│       ├── Config/
│       ├── Content/
│       │   ├── environments/                  # Niveles y escenarios
│       │   ├── characters/                    # Skeletal meshes, rigs
│       │   ├── fx/                            # Niagara y postproceso
│       │   └── cinematics/                    # Level Sequences por cada plano
│       │       └── sq010/
│       │           ├── sq010_master_seq
│       │           ├── sq010_sh010_seq
│       │           └── sq010_sh020_seq
│       └── [PROJECT_CODE]_unreal.uproject
│
├── ai_lab/                                    # Laboratorio central de IA (Modulo AI)
│   ├── prompts/                               # Hojas de prompts maestros y seeds
│   ├── references/                            # Estilos consistentes, personajes
│   └── models/                                # Modelos entrenados, LoRAs, embeddings
│
└── sequences/                                 # Produccion por secuencias y planos
    └── sq010/
        ├── _shared/                           # Recursos compartidos dentro de sq010
        └── sq010_sh010/
            ├── plates/                        # Plates con versionado
            │   ├── v001/                      # Version inicial con handles
            │   │   └── proxies/               # Proxy para playback
            │   └── v002/                      # Re-conform / nuevo grado de color
            │       └── proxies/
            │
            ├── comp/                          # Composicion (Modulo Comp)
            │   ├── scripts/                   # .nk, .aep, .comp (v001, v002...)
            │   └── precomps/                  # Caches, rotos, cleanplates
            │
            ├── 3d/                            # 3D por plano (Modulo 3D)
            │   ├── scenes/                    # .blend, .ma, .hip (v001, v002...)
            │   ├── tracking/                  # Camaras matchmove (.abc, .fbx)
            │   └── caches/                    # Alembic, USD, VDB locales
            │
            ├── ai/                            # Inteligencia Artificial (Modulo AI)
            │   ├── references/                # Prompts del shot, inputs, mascaras inpaint
            │   └── outputs/                   # Descargas de plataformas (v001, v002...)
            │       ├── v001/                  # Variaciones iniciales
            │       └── v002/                  # Selecciones y upscales
            │
            └── renders/                       # Salidas finales del plano
                ├── hires/                     # Renders de alta para comp/finish
                │   ├── v001/                  # Secuencias EXR / ProRes
                │   └── v002/
                └── review/                    # Proxies livianos para revision interna
                    ├── sq010_sh010_v001.mp4
                    └── sq010_sh010_v002.mp4
```
