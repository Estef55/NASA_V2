"""Structured, verified catalog of the five official NASA/CSA sources and public NASA Open Data APIs."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .nasa_models import (
    AccessType,
    DataClassification,
    ResourceType,
    VerificationStatus,
    validate_source_entry,
)

# ---------------------------------------------------------------------------
# NASA Source 1: Five Hazards of Human Spaceflight
# ---------------------------------------------------------------------------
FIVE_HAZARDS: list[dict[str, Any]] = [
    {
        "id": "space_radiation",
        "name_en": "Space Radiation",
        "name_es": "Radiación espacial",
        "description_en": (
            "Invisible ionizing radiation in space (galactic cosmic rays, solar particle events, trapped radiation) "
            "posing long-term risks including carcinogenesis, central nervous system effects, and tissue damage."
        ),
        "description_es": (
            "Radiación ionizante invisible en el espacio (rayos cósmicos galácticos, eventos de partículas solares y radiación atrapada) "
            "con riesgos a largo plazo como carcinogénesis, efectos en el sistema nervioso central y daño tisular."
        ),
        "official_url": "https://www.nasa.gov/hrp/hazards/",
        "official_source_name": "NASA Human Research Program (HRP) — Five Hazards",
        "measured_by_latira": False,
        "related_latira_indicators": [],
        "latira_note_en": "Relevant to long-term astronaut health surveillance; LÁTIRA does not currently measure personal radiation dose.",
        "latira_note_es": "Relevante para la vigilancia de salud a largo plazo; LÁTIRA no mide actualmente dosis personal de radiación.",
    },
    {
        "id": "isolation_confinement",
        "name_en": "Isolation and Confinement",
        "name_es": "Aislamiento y confinamiento",
        "description_en": (
            "Extended stays in small, enclosed habitats with the same crew can trigger behavioral responses, "
            "sleep loss, circadian desynchronization, mood shifts, and interpersonal fatigue."
        ),
        "description_es": (
            "Estancias prolongadas en hábitats pequeños y cerrados con la misma tripulación pueden generar respuestas conductuales, "
            "pérdida de sueño, desincronización circadiana, cambios de ánimo y fatiga interpersonal."
        ),
        "official_url": "https://www.nasa.gov/hrp/hazards/",
        "official_source_name": "NASA Human Research Program (HRP) — Five Hazards",
        "measured_by_latira": False,
        "related_latira_indicators": ["sleep", "fatigue", "mood"],
        "latira_note_en": "Guides crew wellbeing monitoring; LÁTIRA tracks crew-reported sleep duration, fatigue, and mood against personal baselines.",
        "latira_note_es": "Orienta el seguimiento de bienestar; LÁTIRA registra duración del sueño, fatiga y ánimo autorreportados frente a la línea base personal.",
    },
    {
        "id": "distance_from_earth",
        "name_en": "Distance from Earth",
        "name_es": "Distancia de la Tierra",
        "description_en": (
            "As missions travel beyond low Earth orbit toward the Moon and Mars, communication delays, "
            "limited resupply, and delayed evacuation require higher crew medical autonomy."
        ),
        "description_es": (
            "Conforme las misiones se alejan hacia la Luna y Marte, los retrasos en comunicaciones, "
            "el reabastecimiento limitado y la imposibilidad de evacuación inmediata exigen mayor autonomía médica."
        ),
        "official_url": "https://www.nasa.gov/hrp/hazards/",
        "official_source_name": "NASA Human Research Program (HRP) — Five Hazards",
        "measured_by_latira": False,
        "related_latira_indicators": [],
        "latira_note_en": "Operational mission context motivating local-first health monitoring, local baseline alerts, and offline-capable LÁTI guidance.",
        "latira_note_es": "Contexto operativo que motiva el monitoreo local autónomo, alertas por línea base individual y orientación local de LÁTI.",
    },
    {
        "id": "gravity_fields",
        "name_en": "Gravity Fields (Microgravity & Partial Gravity)",
        "name_es": "Campos gravitacionales (microgravedad y gravedad parcial)",
        "description_en": (
            "Transitions between Earth gravity, weightlessness, lunar (1/6 g), and Martian (3/8 g) gravity affect "
            "muscles, bones, fluid distribution, cardiovascular conditioning, and inner-ear balance."
        ),
        "description_es": (
            "Las transiciones entre gravedad terrestre, ingravidez, gravedad lunar (1/6 g) y marciana (3/8 g) afectan "
            "músculos, huesos, distribución de fluidos, acondicionamiento cardiovascular y equilibrio vestibular."
        ),
        "official_url": "https://www.nasa.gov/hrp/hazards/",
        "official_source_name": "NASA Human Research Program (HRP) — Five Hazards",
        "measured_by_latira": False,
        "related_latira_indicators": ["heart_rate", "pose_geometric_keypoints"],
        "latira_note_en": "Contextualizes cardiovascular and movement-tracking observations; LÁTIRA monitors resting heart rate and geometric pose keypoints.",
        "latira_note_es": "Contextualiza observaciones cardiovasculares y motoras; LÁTIRA registra frecuencia cardíaca en reposo y keypoints geométricos de movimiento.",
    },
    {
        "id": "hostile_closed_environments",
        "name_en": "Hostile / Closed Environments",
        "name_es": "Entornos hostiles y cerrados",
        "description_en": (
            "Spacecraft function as closed artificial ecosystems where temperature, pressure, lighting, "
            "noise, air quality, and microbial dynamics impact immune status and crew wellbeing."
        ),
        "description_es": (
            "Las naves actúan como ecosistemas artificiales cerrados donde temperatura, presión, iluminación, "
            "ruido, calidad del aire y dinámica microbiana influyen en el sistema inmunitario y el bienestar."
        ),
        "official_url": "https://www.nasa.gov/hrp/hazards/",
        "official_source_name": "NASA Human Research Program (HRP) — Five Hazards",
        "measured_by_latira": False,
        "related_latira_indicators": [],
        "latira_note_en": "Environmental hazard context for closed-habitat wellbeing; LÁTIRA does not ingest spacecraft ECLSS telemetry.",
        "latira_note_es": "Contexto ambiental de hábitats cerrados; LÁTIRA no ingiere telemetría ambiental ECLSS de la nave.",
    },
]

# ---------------------------------------------------------------------------
# NASA Source 2: Risks of Human Spaceflight — Domain Classification
# ---------------------------------------------------------------------------
LATIRA_INDICATOR_LABELS: dict[str, dict[str, str]] = {
    "heart_rate": {
        "en": "Resting heart rate (bpm)",
        "es": "Frecuencia cardíaca en reposo (lpm)",
    },
    "sleep": {
        "en": "Sleep duration (h)",
        "es": "Duración del sueño (h)",
    },
    "fatigue": {
        "en": "Fatigue level (1–5)",
        "es": "Nivel de fatiga (1–5)",
    },
    "mood": {
        "en": "Mood score (1–5)",
        "es": "Puntuación de ánimo (1–5)",
    },
    "pose_geometric_keypoints": {
        "en": "Geometric movement keypoints (YOLO Pose)",
        "es": "Keypoints geométricos de movimiento (YOLO Pose)",
    },
}

HRP_RISK_DOMAINS: list[dict[str, Any]] = [
    {
        "id": "cardiovascular",
        "domain_en": "Cardiovascular System",
        "domain_es": "Sistema cardiovascular",
        "nasa_risk_titles": [
            "Risk of Cardiovascular Adaptations",
            "Risk of Reduced Cardiorespiratory and Musculoskeletal Fitness",
        ],
        "summary_en": "Weightlessness alters blood circulation, vascular tone, and cardiac workload.",
        "summary_es": "La ingravidez altera la circulación sanguínea, el tono vascular y la carga cardíaca.",
        "relevance_explanation_en": "The cardiovascular domain is directly relevant to physiological monitoring during spaceflight; LÁTIRA tracks resting heart rate against the astronaut's personal baseline.",
        "relevance_explanation_es": "El dominio cardiovascular es relevante para el seguimiento fisiológico durante misiones espaciales; LÁTIRA registra la frecuencia cardíaca en reposo frente a la línea base individual.",
        "official_url": "https://www.nasa.gov/hrp/risks/",
        "related_latira_indicators": ["heart_rate"],
        "contextual_only": True,
    },
    {
        "id": "sleep_circadian",
        "domain_en": "Sleep & Circadian Rhythms",
        "domain_es": "Sueño y ritmos circadianos",
        "nasa_risk_titles": [
            "Risk of Inadequate Sleep and Irregular Schedules",
        ],
        "summary_en": "Altered light/dark cycles, workload, and confinement disrupt sleep quality and circadian alignment.",
        "summary_es": "Los ciclos alterados de luz/oscuridad, la carga operativa y el confinamiento afectan el sueño y el ritmo circadiano.",
        "relevance_explanation_en": "Sleep disruption affects alertness and recovery; LÁTIRA monitors sleep duration and self-reported fatigue without altering clinical thresholds.",
        "relevance_explanation_es": "La alteración del sueño impacta la vigilia y recuperación; LÁTIRA registra duración del sueño y fatiga autorreportada sin modificar umbrales clínicos.",
        "official_url": "https://www.nasa.gov/hrp/risks/",
        "related_latira_indicators": ["sleep", "fatigue"],
        "contextual_only": True,
    },
    {
        "id": "behavioral_health",
        "domain_en": "Behavioral Health & Human Factors",
        "domain_es": "Salud conductual y factores humanos",
        "nasa_risk_titles": [
            "Risk of Behavioral Changes and Psychiatric Disorders",
            "Risk of Inadequate Teamwork",
            "Risk of Inadequate Systems Operations Support",
        ],
        "summary_en": "Prolonged isolation, workload, and communication delays affect mood, fatigue, and team cohesion.",
        "summary_es": "El aislamiento prolongado, la carga de trabajo y los retrasos de comunicación afectan ánimo, fatiga y cohesión.",
        "relevance_explanation_en": "Behavioral readiness depends on tracking emotional strain early; LÁTIRA collects daily mood and fatigue check-ins as wellbeing self-reports.",
        "relevance_explanation_es": "La estabilidad conductual requiere observar cambios tempranos; LÁTIRA recoge autorreportes diarios de ánimo y fatiga como señales de bienestar.",
        "official_url": "https://www.nasa.gov/hrp/risks/",
        "related_latira_indicators": ["mood", "fatigue"],
        "contextual_only": True,
    },
    {
        "id": "immune",
        "domain_en": "Immune System & Host-Microbe Interactions",
        "domain_es": "Sistema inmunológico e interacciones huésped-microorganismo",
        "nasa_risk_titles": [
            "Risk of Altered Immune System Responses",
            "Risk of Host-Microorganism Interactions",
        ],
        "summary_en": "Spaceflight stressors can alter immune markers and reactivate latent viruses; skin/gut microbiomes shift.",
        "summary_es": "El estrés del vuelo espacial puede alterar marcadores inmunes y reactivar virus latentes; cambian microbiomas.",
        "relevance_explanation_en": "Important scientific context for mission medicine, though LÁTIRA does not measure blood, saliva, or immunological biomarkers.",
        "relevance_explanation_es": "Contexto científico relevante para medicina espacial, aunque LÁTIRA no mide biomarcadores inmunológicos en sangre o saliva.",
        "official_url": "https://www.nasa.gov/hrp/risks/",
        "related_latira_indicators": [],
        "contextual_only": True,
    },
    {
        "id": "musculoskeletal",
        "domain_en": "Musculoskeletal System",
        "domain_es": "Sistema musculoesquelético",
        "nasa_risk_titles": [
            "Risk of Spaceflight-Induced Bone Changes",
            "Risk of Reduced Cardiorespiratory and Musculoskeletal Fitness",
            "Risk of Injury from Dynamic Loads",
        ],
        "summary_en": "Microgravity accelerates bone mineral loss and muscle deconditioning; landing loads pose injury risk.",
        "summary_es": "La microgravedad acelera pérdida ósea y desacondicionamiento muscular; las cargas de aterrizaje generan riesgo físico.",
        "relevance_explanation_en": "Relevant to posture and motor conditioning; LÁTIRA provides optional geometric movement keypoints via YOLO Pose (not bone density scans).",
        "relevance_explanation_es": "Relevante para postura y condición motora; LÁTIRA ofrece keypoints geométricos de movimiento con YOLO Pose (sin medir densidad ósea).",
        "official_url": "https://www.nasa.gov/hrp/risks/",
        "related_latira_indicators": ["pose_geometric_keypoints"],
        "contextual_only": True,
    },
    {
        "id": "vestibular_sensorimotor",
        "domain_en": "Vestibular & Sensorimotor Function",
        "domain_es": "Sistema vestibular y sensoriomotor",
        "nasa_risk_titles": [
            "Risk of Altered Sensorimotor and Vestibular Function",
        ],
        "summary_en": "Gravity transitions induce motion sickness, disorientation, and gait/hand-eye coordination deficits.",
        "summary_es": "Las transiciones gravitacionales causan cinetosis, desorientación y déficits de marcha o coordinación.",
        "relevance_explanation_en": "Postural alignment and trunk tilt observations help contextualize movement coordination; LÁTIRA captures geometric pose keypoints only.",
        "relevance_explanation_es": "La observación de inclinación y alineación postural contextualiza la coordinación motora; LÁTIRA solo registra keypoints geométricos de pose.",
        "official_url": "https://www.nasa.gov/hrp/risks/",
        "related_latira_indicators": ["pose_geometric_keypoints"],
        "contextual_only": True,
    },
    {
        "id": "nutrition",
        "domain_en": "Nutrition & Space Food Systems",
        "domain_es": "Nutrición y sistemas alimentarios",
        "nasa_risk_titles": [
            "Risk of Inadequate Food and Nutrition",
        ],
        "summary_en": "Long-duration missions require nutrient-stable diets to prevent deficiencies and support physiology.",
        "summary_es": "Las misiones largas requieren dietas estables en nutrientes para evitar deficiencias y sostener la fisiología.",
        "relevance_explanation_en": "Scientific reference domain only; LÁTIRA does not currently record dietary intake or nutritional biomarkers.",
        "relevance_explanation_es": "Dominio de referencia científica únicamente; LÁTIRA no registra ingesta alimentaria ni biomarcadores nutricionales.",
        "official_url": "https://www.nasa.gov/hrp/risks/",
        "related_latira_indicators": [],
        "contextual_only": True,
    },
    {
        "id": "space_radiation",
        "domain_en": "Space Radiation Risks",
        "domain_es": "Riesgos por radiación espacial",
        "nasa_risk_titles": [
            "Risk of Radiation-Induced Cancers",
        ],
        "summary_en": "Cumulative ionizing radiation exposure increases long-term carcinogenesis and tissue risks.",
        "summary_es": "La exposición acumulada a radiación ionizante incrementa riesgos de cáncer a largo plazo y daño tisular.",
        "relevance_explanation_en": "Reference risk taxonomy only; LÁTIRA has no dosimeter integration and does not estimate radiation dose.",
        "relevance_explanation_es": "Taxonomía de riesgo de referencia únicamente; LÁTIRA no integra dosímetros ni estima dosis de radiación.",
        "official_url": "https://www.nasa.gov/hrp/risks/",
        "related_latira_indicators": [],
        "contextual_only": True,
    },
    {
        "id": "other_spaceflight_risks",
        "domain_en": "Neuro-Ocular (SANS) & EVA Atmosphere Risks",
        "domain_es": "Síndrome neuro-ocular (SANS) y riesgos EVA",
        "nasa_risk_titles": [
            "Risk of Spaceflight Associated Neuro-ocular Syndrome (SANS)",
            "Risk of Decompression Sickness",
            "Risk of Hypoxia",
            "Risk of Injury and Compromised Performance from Spacewalks",
        ],
        "summary_en": "Includes fluid-shift ocular/brain changes (SANS) and spacesuit pressure/oxygen/CO2 hazards.",
        "summary_es": "Incluye cambios oculares/cerebrales por desplazamiento de fluidos (SANS) y riesgos de presión/O2/CO2 en trajes EVA.",
        "relevance_explanation_en": "Critical mission-level medical reference; LÁTIRA does not measure intraocular pressure, ocular imaging, or EVA suit gases.",
        "relevance_explanation_es": "Referencia médica crítica de misión; LÁTIRA no mide presión intraocular, imagen ocular ni gases de traje EVA.",
        "official_url": "https://www.nasa.gov/hrp/risks/",
        "related_latira_indicators": [],
        "contextual_only": True,
    },
]

# ---------------------------------------------------------------------------
# NASA Source 3: Ongoing HRP Research Programs
# ---------------------------------------------------------------------------
HRP_ONGOING_PROGRAMS: list[dict[str, Any]] = [
    {
        "id": "archer",
        "name": "ARCHeR (Artemis Research for Crew Health and Readiness)",
        "responsible_institution": "NASA Human Research Program (HRP)",
        "description_en": (
            "Deep-space behavioral and performance investigation monitoring crew well-being, daily activity, "
            "sleep patterns (via wrist actigraphy), and teamwork during the Artemis campaign."
        ),
        "description_es": (
            "Estudio conductual y de desempeño en espacio profundo que monitorea bienestar, actividad diaria, "
            "patrones de sueño (actigrafía de muñeca) y trabajo en equipo durante la campaña Artemis."
        ),
        "scientific_domain": "Behavioral Health, Sleep & Human Factors",
        "research_objective_en": "Evaluate combined effects of deep-space hazards on well-being, sleep, and crew performance.",
        "research_objective_es": "Evaluar el efecto combinado de los peligros del espacio profundo en bienestar, sueño y desempeño.",
        "study_population_or_context": "Participating NASA Artemis crew members (pre-flight, in-flight Orion deep space, post-flight).",
        "official_url": "https://www.nasa.gov/reference/archer/",
        "resource_type": ResourceType.RESEARCH_CATALOG.value,
        "data_availability_en": "Restricted / controlled astronaut research data; no public telemetry feed.",
        "data_availability_es": "Datos restringidos/controlados de investigación con astronautas; sin feed público de telemetría.",
        "access_limitations_en": "Requires formal NASA HRP/LSDA research data request; LÁTIRA has no access to crew data.",
        "access_limitations_es": "Requiere solicitud formal ante NASA HRP/LSDA; LÁTIRA no tiene acceso a datos de la tripulación.",
    },
    {
        "id": "immune_biomarkers",
        "name": "Immune Biomarkers",
        "responsible_institution": "NASA Human Research Program (HRP)",
        "description_en": (
            "Flight investigation analyzing astronaut blood and dry-saliva samples to characterize immune system "
            "alterations and latent virus reactivation (such as herpesviruses/shingles) during deep-space flight."
        ),
        "description_es": (
            "Investigación en vuelo que analiza muestras de sangre y saliva seca para caracterizar cambios inmunológicos "
            "y reactivación de virus latentes durante misiones de espacio profundo."
        ),
        "scientific_domain": "Immune System & Host-Microorganism Interactions",
        "research_objective_en": "Identify immune biomarkers and countermeasure targets for deep-space crew health.",
        "research_objective_es": "Identificar biomarcadores inmunológicos y medidas de mitigación para tripulaciones.",
        "study_population_or_context": "Participating Artemis II / deep-space crew members.",
        "official_url": "https://www.nasa.gov/reference/immune-biomarkers/",
        "resource_type": ResourceType.RESEARCH_CATALOG.value,
        "data_availability_en": "Controlled biomedical study data; not exposed via open clinical API.",
        "data_availability_es": "Datos biomédicos controlados; no expuestos mediante API clínica abierta.",
        "access_limitations_en": "Protected human subjects data; accessible only under approved NASA data sharing agreements.",
        "access_limitations_es": "Datos protegidos de participantes humanos; acceso únicamente bajo acuerdos aprobados por NASA.",
    },
    {
        "id": "standard_measures",
        "name": "Spaceflight Standard Measures",
        "responsible_institution": "NASA Human Research Program (HRP)",
        "description_en": (
            "Core multidisciplinary protocol collecting standardized physiological, behavioral, cognitive, "
            "sensorimotor, immune, nutrition, and sleep measurements before, during, and after missions."
        ),
        "description_es": (
            "Protocolo multidisciplinario base que recopila mediciones estandarizadas fisiológicas, conductuales, cognitivas, "
            "sensoriomotoras, inmunológicas, nutricionales y de sueño antes, durante y después del vuelo."
        ),
        "scientific_domain": "Multi-system Physiological & Psychological Baseline",
        "research_objective_en": "Build a standardized cross-mission repository characterizing human adaptation to spaceflight.",
        "research_objective_es": "Construir un repositorio estandarizado entre misiones sobre la adaptación humana al vuelo espacial.",
        "study_population_or_context": "Participating ISS and Artemis astronauts across pre-, in-, and post-flight timelines.",
        "official_url": "https://www.nasa.gov/reference/standard-measures/",
        "resource_type": ResourceType.RESEARCH_CATALOG.value,
        "data_availability_en": "Investigator repository via NASA LSDA / HRP; no unauthenticated public individual API.",
        "data_availability_es": "Repositorio para investigadores vía NASA LSDA / HRP; sin API pública individual sin autenticación.",
        "access_limitations_en": "Individual astronaut measures are privacy-controlled; LÁTIRA does not import crew baselines.",
        "access_limitations_es": "Las medidas individuales están protegidas por privacidad; LÁTIRA no importa líneas base de tripulantes.",
    },
    {
        "id": "cipher",
        "name": "CIPHER (Complement of Integrated Protocols for Human Exploration Research)",
        "responsible_institution": "NASA Human Research Program (HRP) & International Partners",
        "description_en": (
            "Umbrella suite of 14 integrated studies examining cardiovascular, bone, musculoskeletal, brain, vision (SANS), "
            "and sensorimotor adaptations across short-, standard-, and extended-duration missions."
        ),
        "description_es": (
            "Programa integral de 14 estudios que examina adaptaciones cardiovasculares, óseas, musculoesqueléticas, cerebrales, "
            "oculares (SANS) y sensoriomotoras en misiones de duración corta, estándar y extendida."
        ),
        "scientific_domain": "Integrated Multi-System Spaceflight Physiology",
        "research_objective_en": "Assess whole-body human response to spaceflight duration to project Moon/Mars mission risks.",
        "research_objective_es": "Evaluar la respuesta integral del cuerpo humano según la duración del vuelo para proyectar riesgos Luna/Marte.",
        "study_population_or_context": "Participating ISS astronauts across multi-duration cohorts (months to ~1 year).",
        "official_url": "https://www.nasa.gov/reference/cipher/",
        "resource_type": ResourceType.RESEARCH_CATALOG.value,
        "data_availability_en": "Controlled investigator data bank; descriptive protocol catalog is public.",
        "data_availability_es": "Banco de datos controlado para investigadores; el catálogo descriptivo es público.",
        "access_limitations_en": "No public endpoint with participant values; LÁTIRA links only official descriptive reference.",
        "access_limitations_es": "Sin endpoint público con valores de participantes; LÁTIRA enlaza solo la referencia descriptiva oficial.",
    },
    {
        "id": "spinal_health",
        "name": "Spinal Health",
        "responsible_institution": "NASA Human Research Program (HRP)",
        "description_en": (
            "Pre- and post-flight imaging and spine analysis studying microgravity-induced spinal unloading, "
            "disc/muscle changes, back pain, and post-flight injury countermeasures."
        ),
        "description_es": (
            "Análisis e imagenología espinal pre y postvuelo que estudia descarga vertebral por microgravedad, "
            "cambios musculares/discales, dolor lumbar y contramedidas frente a lesiones."
        ),
        "scientific_domain": "Musculoskeletal & Spine Health",
        "research_objective_en": "Quantify spinal structural changes in microgravity to inform exercise and injury mitigation.",
        "research_objective_es": "Cuantificar cambios estructurales de la columna en microgravedad para orientar mitigación de lesiones.",
        "study_population_or_context": "Participating ISS astronauts examined pre-flight and post-flight.",
        "official_url": "https://www.nasa.gov/missions/station/astronauts-spines-under-scrutiny/",
        "resource_type": ResourceType.RESEARCH_CATALOG.value,
        "data_availability_en": "Public descriptive NASA article/summary; imaging/clinical data is restricted.",
        "data_availability_es": "Resumen/artículo descriptivo público de NASA; datos clínicos e imágenes restringidos.",
        "access_limitations_en": "Note: legacy /reference/spinal-health/ returns HTTP 404; official ongoing-research link points to NASA station feature.",
        "access_limitations_es": "Nota: la ruta /reference/spinal-health/ devuelve HTTP 404; el enlace oficial apunta al reporte de estación NASA.",
    },
    {
        "id": "tempus_pro",
        "name": "Tempus Pro (Autonomous Telemedicine Evaluation)",
        "responsible_institution": "NASA Human Research Program (HRP)",
        "description_en": (
            "Flight evaluation of a commercial compact multi-parameter telemedicine device (vital signs, ECG, imaging) "
            "supporting crew medical officer training and near-real-time remote diagnostic workflows."
        ),
        "description_es": (
            "Evaluación en vuelo de un dispositivo comercial compacto de telemedicina multiparámetro (signos vitales, ECG, imagen) "
            "para apoyar al oficial médico de tripulación y flujos de diagnóstico remoto."
        ),
        "scientific_domain": "Exploration Medical Capability & Autonomous Telemedicine",
        "research_objective_en": "Assess diagnostic integration and footprint reduction for deep-space medical care.",
        "research_objective_es": "Evaluar integración diagnóstica y reducción de equipo para atención médica en espacio profundo.",
        "study_population_or_context": "Participating flight crews comparing Tempus Pro readings against periodic health exams.",
        "official_url": "https://www.nasa.gov/reference/tempus-pro/",
        "resource_type": ResourceType.RESEARCH_CATALOG.value,
        "data_availability_en": "Descriptive reference only; LÁTIRA has no connection to Tempus Pro hardware or NASA flight systems.",
        "data_availability_es": "Solo referencia descriptiva; LÁTIRA no tiene conexión con hardware Tempus Pro ni sistemas de vuelo NASA.",
        "access_limitations_en": "Proprietary/operational flight hardware evaluation; no public telemetry API.",
        "access_limitations_es": "Evaluación de hardware operativo de vuelo; sin API pública de telemetría.",
    },
]

# ---------------------------------------------------------------------------
# CSA Source 4: CANS Radiation Monitoring Context
# ---------------------------------------------------------------------------
CSA_CANS_PROFILE: dict[str, Any] = {
    "system_name": "CANS (Canadian Active Neutron Spectrometer)",
    "organization": "Canadian Space Agency (CSA) & Bubble Technology Industries (BTI)",
    "article_date": "2026-02-26",
    "official_url": "https://www.asc-csa.gc.ca/eng/news/articles/2026/2026-02-26-monitoring-radiation-astronaut-health.asp",
    "radiation_type_monitored": "Space neutron radiation (~30% of total ISS radiation environment)",
    "predecessor_experiments": ["MOSFET", "EVARM", "Radi-N", "Radi-N2"],
    "operational_advancement": "Autonomous continuous measurement with time-stamped telemetry to Earth researchers, unlike passive bubble detectors.",
    "units_specified_in_source": False,
    "units_note_en": "The official 2026-02-26 CSA article does not publish quantitative measurement units or numerical dose datasets.",
    "units_note_es": "El artículo oficial de la CSA (2026-02-26) no publica unidades cuantitativas ni conjuntos de datos numéricos.",
    "public_dataset_available": False,
    "public_api_available": False,
    "connected": False,
    "limitations_en": (
        "Official CSA news announcement only. LÁTIRA does NOT connect to CANS and does NOT receive personal astronaut radiation measurements."
    ),
    "limitations_es": (
        "Únicamente comunicado científico oficial de la CSA. LÁTIRA NO está conectado a CANS y NO recibe mediciones personales de radiación."
    ),
}

# ---------------------------------------------------------------------------
# CSA Source 5: Why Conduct Science Experiments in Space
# ---------------------------------------------------------------------------
CSA_ISS_SCIENCE_CONTEXT: dict[str, Any] = {
    "organization": "Canadian Space Agency (CSA)",
    "official_url": "https://www.asc-csa.gc.ca/eng/iss/science/why-do-we-conduct-science-experiments-in-space.asp",
    "iss_scale": "Average ~200 active international experiments aboard the ISS at any given time.",
    "pillars": [
        {
            "id": "deep_space_preparation",
            "title_en": "Preparing for deep-space destinations",
            "title_es": "Preparación para destinos de espacio profundo",
            "summary_en": "Studying prolonged weightlessness, higher radiation, isolation, communication delays, and reduced Earth resupply.",
            "summary_es": "Estudio de ingravidez prolongada, mayor radiación, aislamiento, retrasos de comunicación y menor soporte desde la Tierra.",
        },
        {
            "id": "terrestrial_health_insights",
            "title_en": "Improving quality of life on Earth",
            "title_es": "Mejora de la calidad de vida en la Tierra",
            "summary_en": (
                "Six months in space triggers accelerated physiological changes akin to aging or sedentary lifestyle "
                "(bone density, cardiovascular, balance, Type-2 diabetes research)."
            ),
            "summary_es": (
                "Seis meses en el espacio producen cambios acelerados similares al envejecimiento o sedentarismo "
                "(salud ósea, cardiovascular, equilibrio y diabetes tipo 2)."
            ),
        },
    ],
}

# ---------------------------------------------------------------------------
# Master Source Registry (5 Official Challenge Sources + 1 Verified Public NASA API)
# ---------------------------------------------------------------------------
_STATIC_SOURCES: list[dict[str, Any]] = [
    {
        "id": "nasa-hrp-hazards",
        "name": "NASA HRP — Five Hazards of Human Spaceflight",
        "organization": "NASA Human Research Program (HRP)",
        "category": "spaceflight_hazards",
        "challenge_official_source": True,
        "description": (
            "Official NASA HRP taxonomy of the five interconnected hazards of human spaceflight: "
            "space radiation, isolation and confinement, distance from Earth, gravity fields, and hostile/closed environments."
        ),
        "description_es": (
            "Taxonomía oficial de NASA HRP sobre los cinco peligros interconectados del vuelo espacial tripulado: "
            "radiación espacial, aislamiento y confinamiento, distancia de la Tierra, campos gravitacionales y entornos hostiles/cerrados."
        ),
        "official_url": "https://www.nasa.gov/hrp/hazards/",
        "resource_type": ResourceType.SCIENTIFIC_DOCUMENTATION.value,
        "access_type": AccessType.PUBLIC_WEBPAGE.value,
        "endpoint": None,
        "data_format": "HTML / WordPress page metadata",
        "variables": [
            "space_radiation",
            "isolation_and_confinement",
            "distance_from_earth",
            "gravity_fields",
            "hostile_closed_environments",
        ],
        "units": "categorical_taxonomy_no_numeric_units",
        "population": "Human spaceflight crews (ISS, Artemis/Moon, projected Mars missions)",
        "coverage": "Ongoing NASA HRP scientific framework",
        "license_or_terms": "NASA Media Usage Guidelines (public government scientific reference)",
        "limitations": (
            "Scientific documentation only; does not expose downloadable astronaut measurements or a clinical telemetry API. "
            "Cannot be treated as individual astronaut observations."
        ),
        "limitations_es": (
            "Únicamente documentación científica; no expone mediciones descargables de astronautas ni API de telemetría clínica. "
            "No debe tratarse como mediciones individuales del tripulante."
        ),
        "verification_status": VerificationStatus.REFERENCE_ONLY.value,
        "last_checked": "2026-11-13T21:25:00+00:00",
    },
    {
        "id": "nasa-hrp-risks",
        "name": "NASA HRP — Risks of Human Spaceflight",
        "organization": "NASA Human Research Program (HRP)",
        "category": "health_risk_classification",
        "challenge_official_source": True,
        "description": (
            "Official classification of human health and performance risks across physiology, behavioral performance, "
            "and space radiation (cardiovascular, immune, sleep/circadian, nutrition, musculoskeletal, vestibular, SANS, radiation)."
        ),
        "description_es": (
            "Clasificación oficial de riesgos de salud y desempeño humano en fisiología, conducta y radiación espacial "
            "(cardiovascular, inmunológico, sueño/circadiano, nutrición, musculoesquelético, vestibular, SANS, radiación)."
        ),
        "official_url": "https://www.nasa.gov/hrp/risks/",
        "resource_type": ResourceType.SCIENTIFIC_DOCUMENTATION.value,
        "access_type": AccessType.PUBLIC_WEBPAGE.value,
        "endpoint": None,
        "data_format": "HTML / WordPress page metadata",
        "variables": [
            "cardiovascular",
            "sleep_circadian",
            "behavioral_health",
            "immune",
            "musculoskeletal",
            "vestibular_sensorimotor",
            "nutrition",
            "space_radiation",
            "neuro_ocular_sans",
        ],
        "units": "categorical_risk_taxonomy_no_clinical_thresholds",
        "population": "Human spaceflight astronauts across LEO, lunar, and Mars mission profiles",
        "coverage": "Active NASA Human Research Roadmap (HRR) risk taxonomy",
        "license_or_terms": "NASA Media Usage Guidelines (public government scientific reference)",
        "limitations": (
            "Qualitative risk classification only; contains no personal baseline thresholds, individual clinical units, or open telemetry API."
        ),
        "limitations_es": (
            "Clasificación cualitativa de riesgos únicamente; no contiene umbrales clínicos individuales, unidades clínicas ni API abierta de telemetría."
        ),
        "verification_status": VerificationStatus.CATALOGUED.value,
        "last_checked": "2026-11-13T21:25:00+00:00",
    },
    {
        "id": "nasa-hrp-ongoing-research",
        "name": "NASA HRP — Ongoing Human Research Program Research",
        "organization": "NASA Human Research Program (HRP)",
        "category": "research_programs_catalog",
        "challenge_official_source": True,
        "description": (
            "Official catalog of active and past NASA HRP human investigations including ARCHeR, Immune Biomarkers, "
            "Standard Measures, CIPHER, Spinal Health, and Tempus Pro."
        ),
        "description_es": (
            "Catálogo oficial de investigaciones humanas en curso y pasadas de NASA HRP, incluyendo ARCHeR, Immune Biomarkers, "
            "Standard Measures, CIPHER, Spinal Health y Tempus Pro."
        ),
        "official_url": "https://www.nasa.gov/hrp/ongoing-hrp-research/",
        "resource_type": ResourceType.RESEARCH_CATALOG.value,
        "access_type": AccessType.RESTRICTED_DATA_REQUEST.value,
        "endpoint": None,
        "data_format": "HTML program summaries (underlying investigator datasets controlled via NASA LSDA/HRP)",
        "variables": [
            "ARCHeR",
            "Immune Biomarkers",
            "Standard Measures",
            "CIPHER",
            "Spinal Health",
            "Tempus Pro",
        ],
        "units": "study_protocol_descriptors_only",
        "population": "Participating ISS and Artemis astronauts (pre-flight, in-flight, post-flight)",
        "coverage": "Current ISS, Artemis II, and recent HRP human flight studies",
        "license_or_terms": "Public descriptive summaries; participant biomedical datasets governed by NASA IRB/LSDA access agreements",
        "limitations": (
            "LÁTIRA does NOT have access to private participant datasets, Tempus Pro devices, or NASA operational systems. "
            "Note: legacy /reference/spinal-health/ returns 404; verified link is NASA's station Spinal Health article."
        ),
        "limitations_es": (
            "LÁTIRA NO tiene acceso a conjuntos de datos privados de participantes, dispositivos Tempus Pro ni sistemas operativos de NASA. "
            "Nota: /reference/spinal-health/ devuelve 404; el enlace verificado apunta al artículo oficial de estación."
        ),
        "verification_status": VerificationStatus.CATALOGUED.value,
        "last_checked": "2026-11-13T21:25:00+00:00",
    },
    {
        "id": "csa-cans-radiation",
        "name": "CSA — Monitoring Radiation for Astronaut Health (CANS)",
        "organization": "Canadian Space Agency (CSA)",
        "category": "radiation_monitoring_reference",
        "challenge_official_source": True,
        "description": (
            "Official CSA article (2026-02-26) documenting the Canadian Active Neutron Spectrometer (CANS) contract "
            "with Bubble Technology Industries to monitor neutron radiation (~30% of ISS total radiation) autonomously."
        ),
        "description_es": (
            "Artículo oficial de la CSA (2026-02-26) sobre el contrato del Espectrómetro Activo de Neutrones Canadiense (CANS) "
            "con Bubble Technology Industries para monitorear de forma autónoma radiación neutrónica (~30% de la radiación en la EEI)."
        ),
        "official_url": "https://www.asc-csa.gc.ca/eng/news/articles/2026/2026-02-26-monitoring-radiation-astronaut-health.asp",
        "resource_type": ResourceType.NEWS_ARTICLE.value,
        "access_type": AccessType.PUBLIC_WEBPAGE.value,
        "endpoint": None,
        "data_format": "HTML news article",
        "variables": ["neutron_radiation_context", "iss_radiation_fraction_30_percent_contextual"],
        "units": "not_specified_in_source_article",
        "population": "ISS and future Moon/Mars astronauts (instrument context)",
        "coverage": "Published 2026-02-26; references >25 years of ISS radiation experiments (MOSFET, EVARM, Radi-N, Radi-N2)",
        "license_or_terms": "Government of Canada / CSA Terms and Conditions (non-commercial reference)",
        "limitations": (
            "No public dataset, API, or measurement units are published in this article. "
            "LÁTIRA is NOT connected to CANS and does NOT simulate personal radiation readings."
        ),
        "limitations_es": (
            "Este artículo no publica conjunto de datos público, API ni unidades de medición. "
            "LÁTIRA NO está conectado a CANS y NO simula lecturas personales de radiación."
        ),
        "verification_status": VerificationStatus.REFERENCE_ONLY.value,
        "last_checked": "2026-11-13T21:25:00+00:00",
    },
    {
        "id": "csa-iss-science",
        "name": "CSA — Why Do We Conduct Science Experiments in Space?",
        "organization": "Canadian Space Agency (CSA)",
        "category": "microgravity_scientific_context",
        "challenge_official_source": True,
        "description": (
            "Official CSA scientific overview explaining microgravity and ISS research (~200 active experiments), "
            "supporting deep-space crew protection and Earth medical breakthroughs (aging/sedentary analogs)."
        ),
        "description_es": (
            "Resumen científico oficial de la CSA que explica la investigación en microgravedad y la EEI (~200 experimentos activos), "
            "apoyando la protección en espacio profundo y avances médicos en la Tierra."
        ),
        "official_url": "https://www.asc-csa.gc.ca/eng/iss/science/why-do-we-conduct-science-experiments-in-space.asp",
        "resource_type": ResourceType.EDUCATIONAL_CONTEXT.value,
        "access_type": AccessType.PUBLIC_WEBPAGE.value,
        "endpoint": None,
        "data_format": "HTML scientific context page",
        "variables": ["microgravity_adaptation_context", "deep_space_preparation", "terrestrial_health_analogs"],
        "units": "qualitative_scientific_context_only",
        "population": "ISS astronauts and terrestrial analog populations (older adults, sedentary/bedridden analogs)",
        "coverage": "Ongoing CSA ISS Science overview",
        "license_or_terms": "Government of Canada / CSA Terms and Conditions",
        "limitations": (
            "Conceptual and educational scientific context only; not a health dataset or clinical telemetry source."
        ),
        "limitations_es": (
            "Únicamente contexto científico y educativo; no constituye un conjunto de datos de salud ni telemetría clínica."
        ),
        "verification_status": VerificationStatus.REFERENCE_ONLY.value,
        "last_checked": "2026-11-13T21:25:00+00:00",
    },
    {
        "id": "nasa-osdr-studies",
        "name": "NASA OSDR — Open Science Data Repository (Human Spaceflight Studies API)",
        "organization": "NASA Open Science Data Repository (OSDR)",
        "category": "open_space_biology_metadata",
        "challenge_official_source": False,
        "description": (
            "Additional verified public NASA REST JSON API providing open metadata for spaceflight and analog "
            "biomedical studies (including Homo sapiens astronaut studies such as AX-1, ISS, and Inspiration4)."
        ),
        "description_es": (
            "API JSON REST pública oficial adicional de NASA (OSDR) que provee metadatos abiertos de estudios biomédicos "
            "espaciales y análogos (incluidos estudios en Homo sapiens como AX-1, EEI e Inspiration4)."
        ),
        "official_url": "https://osdr.nasa.gov/bio/repo/",
        "resource_type": ResourceType.PUBLIC_API_DATASET.value,
        "access_type": AccessType.PUBLIC_REST_API.value,
        "endpoint": "https://osdr.nasa.gov/osdr/data/search?term=spaceflight&ffield=organism&fvalue=Homo%20sapiens&size=5",
        "data_format": "application/json (REST search index)",
        "variables": [
            "study_accession",
            "study_title",
            "organism",
            "mission_name",
            "mission_dates",
            "flight_program",
            "material_type",
            "assay_technology",
        ],
        "units": "study_metadata_categorical_and_iso_dates",
        "population": "Homo sapiens participants in published spaceflight and analog research cohorts",
        "coverage": "Published NASA OSDR spaceflight studies (e.g., 2013–2024+ missions)",
        "license_or_terms": "NASA Open Data Policy / CC0 1.0 Public Domain Dedication (no credentials required)",
        "limitations": (
            "Exposes study-level metadata and public repository accessions, NOT real-time individual astronaut vital signs. "
            "Requires live network reachability to osdr.nasa.gov to transition from 'available' to 'connected'."
        ),
        "limitations_es": (
            "Expone metadatos públicos a nivel de estudio y accesiones de repositorio, NO signos vitales individuales en tiempo real. "
            "Requiere conectividad real con osdr.nasa.gov para pasar de 'available' a 'connected'."
        ),
        "verification_status": VerificationStatus.AVAILABLE.value,
        "last_checked": None,
    },
]


def get_static_sources(include_additional_public: bool = True) -> list[dict[str, Any]]:
    sources = [validate_source_entry(s) for s in _STATIC_SOURCES]
    if not include_additional_public:
        sources = [s for s in sources if s.get("challenge_official_source")]
    return deepcopy(sources)


def get_domain_catalog() -> dict[str, Any]:
    return {
        "five_hazards": deepcopy(FIVE_HAZARDS),
        "risk_domains": deepcopy(HRP_RISK_DOMAINS),
        "latira_indicator_labels": deepcopy(LATIRA_INDICATOR_LABELS),
        "ongoing_programs": deepcopy(HRP_ONGOING_PROGRAMS),
        "csa_cans": deepcopy(CSA_CANS_PROFILE),
        "csa_iss_science": deepcopy(CSA_ISS_SCIENCE_CONTEXT),
        "default_data_classification": DataClassification.SCIENTIFIC_REFERENCE.value,
    }
