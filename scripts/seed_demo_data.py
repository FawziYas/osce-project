"""
seed_demo_data.py
─────────────────────────────────────────────────────────────────────
OSCE Demo Data Seeder — Year-6 Clinical Exams
Creates 4 exams (IM, Pediatrics, Surgery, OB/GY) each with:
  • 2 sessions (morning + afternoon)
  • 10 paths total (5 per session)
  • 4 stations per path (same station names & checklist across all paths)
  • 14 checklist items per station (total 10 marks/station)
  • 10 students per path (100 students per exam, Arabic names)

DOES NOT modify any existing code/model/route — only inserts data
via the existing Django ORM models.

Usage:
  cd osce_project
  python scripts/seed_demo_data.py
─────────────────────────────────────────────────────────────────────
"""
import os, sys, uuid, random
from datetime import date, time, timezone, datetime

# Django bootstrap
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'osce_project.settings')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import django
django.setup()

from core.models import (
    Course, ILO, Exam, ExamSession, Path, Station, ChecklistItem,
    SessionStudent,
)

# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────
EXAM_DATE = date(2026, 3, 15)
STATION_DURATION = 7          # 7 min per station (1/3 format)
ROTATION_MINUTES = 7
NUM_PATHS_PER_SESSION = 5     # 5 morning + 5 afternoon = 10 total
NUM_STUDENTS_PER_PATH = 10    # 10 students × 10 paths = 100 per exam
NOW_TS = int(datetime.now(timezone.utc).timestamp())

# ─────────────────────────────────────────────────────────────────────
# COURSE / ILO MAPPING  (existing DB records)
# ─────────────────────────────────────────────────────────────────────
# course_id → { theme_id → ilo_id }
# Theme mapping:
#   1 = Medical Knowledge
#   2 = Patient Care: Diagnosis
#   3 = Patient Care: Management
#   4 = Systems-Based Practice
#   5 = Communication
#   6 = Ethics/Professionalism
#   7 = Patient Care: Prevention (OBGYN only at #4)

COURSE_ILO_MAP = {
    # INTMED-SR (course 10)
    10: {1: 7, 2: 8, 3: 9, 4: 10, 5: 11, 6: 12},
    # OBGYN-SR (course 12)
    12: {1: 20, 2: 21, 3: 22, 7: 23, 5: 24, 6: 25},
    # PED-SR (course 14)
    14: {1: 32, 2: 33, 3: 34, 4: 35, 5: 36, 6: 37},
    # SURG-SR (course 16)
    16: {1: 44, 2: 45, 3: 46, 4: 47, 5: 48, 6: 49},
}

# Helper: get ILO by theme for a course (fallback to theme 1)
def ilo_id_for(course_id, theme_id):
    mapping = COURSE_ILO_MAP[course_id]
    return mapping.get(theme_id, list(mapping.values())[0])

# ─────────────────────────────────────────────────────────────────────
# EXAM DEFINITIONS (4 specialties)
# ─────────────────────────────────────────────────────────────────────
# Each station: { name, scenario, instructions, items: [{ desc, pts, critical, rubric, category, interaction, theme }] }
# Total marks per station: 10.0   |   14 items per station

EXAM_DEFS = {
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # EXAM 1: INTERNAL MEDICINE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'Internal Medicine OSCE': {
        'course_id': 10,
        'department': 'Internal Medicine',
        'stations': [
            {
                'name': 'History Taking — Chest Pain',
                'scenario': 'A 55-year-old male presents to the Emergency Department with acute onset chest pain radiating to the left arm for the past 2 hours. He is diaphoretic and anxious. Take a focused history from the patient.',
                'instructions': 'You have 7 minutes to take a focused history from the standardized patient. Cover all relevant aspects of the presenting complaint.',
                'items': [
                    {'desc': 'Introduces self and confirms patient identity', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                    {'desc': 'Establishes rapport and explains purpose of interview', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                    {'desc': 'Asks about onset, duration, and character of chest pain', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Asks about radiation of pain (arm, jaw, back)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Asks about aggravating and relieving factors', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Asks about associated symptoms (dyspnea, nausea, diaphoresis)', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Asks about previous cardiac history and risk factors', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Asks about medications and drug allergies', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'History', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Asks about family history of cardiovascular disease', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'History', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Asks about social history (smoking, alcohol, occupation)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'History', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Explores red flags for aortic dissection and PE', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Summarizes findings back to the patient', 'pts': 0.75, 'critical': False, 'rubric': 'binary', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                    {'desc': 'Provides appropriate differential diagnoses', 'pts': 1.0, 'critical': False, 'rubric': 'partial', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Maintains professional and empathetic demeanor throughout', 'pts': 0.75, 'critical': False, 'rubric': 'binary', 'cat': 'Professionalism', 'interact': 'passive', 'theme': 6},
                ],
            },
            {
                'name': 'Clinical Examination — Cardiovascular System',
                'scenario': 'A 62-year-old female is referred for evaluation of a cardiac murmur detected during a routine check-up. Perform a complete cardiovascular examination.',
                'instructions': 'Perform a systematic cardiovascular examination on the standardized patient. Narrate your findings as you examine.',
                'items': [
                    {'desc': 'Introduces self and obtains consent for examination', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                    {'desc': 'Washes hands / uses alcohol preparation', 'pts': 0.75, 'critical': False, 'rubric': 'binary', 'cat': 'Professionalism', 'interact': 'passive', 'theme': 6},
                    {'desc': 'Positions patient correctly at 45 degrees', 'pts': 0.75, 'critical': False, 'rubric': 'binary', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Inspects hands: clubbing, splinter hemorrhages, peripheral cyanosis', 'pts': 0.5, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Assesses radial and carotid pulses (rate, rhythm, character)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Measures JVP correctly', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Inspects precordium for scars, visible pulsations, deformities', 'pts': 0.5, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Palpates apex beat and assesses character and displacement', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Checks for parasternal heave and thrills', 'pts': 0.5, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Auscultates all four cardiac areas systematically', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Identifies and describes heart sounds (S1, S2, added sounds)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Checks radiation to carotids and axilla', 'pts': 0.5, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Examines for peripheral edema and lung bases', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Presents findings in a structured and confident manner', 'pts': 1.0, 'critical': False, 'rubric': 'partial', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                ],
            },
            {
                'name': 'ECG Interpretation',
                'scenario': 'You are given a 12-lead ECG of a 68-year-old patient who presented with palpitations and dizziness. Interpret the ECG systematically and provide your diagnosis.',
                'instructions': 'Interpret the ECG provided. State your approach, identify abnormalities, and provide a clinical correlation.',
                'items': [
                    {'desc': 'Confirms patient demographics and clinical indication on ECG', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Approach', 'interact': 'passive', 'theme': 4},
                    {'desc': 'Determines heart rate correctly', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Determines rhythm (regular/irregular, sinus/non-sinus)', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Assesses P-wave morphology and PR interval', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Evaluates QRS complex: axis, duration, morphology', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Assesses ST segment for elevation or depression', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Evaluates T-wave morphology and QT interval', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Identifies the territory of ischemia/infarction if present', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Identifies conduction abnormalities (blocks, bundle branch)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Identifies arrhythmia type if present', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Provides correct ECG diagnosis', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Diagnosis', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Correlates ECG findings with clinical presentation', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Suggests appropriate next steps/investigations', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Presents interpretation in a structured logical sequence', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                ],
            },
            {
                'name': 'Data Interpretation (Labs + Imaging)',
                'scenario': 'A 50-year-old diabetic patient is admitted with fatigue, peripheral edema, and reduced urine output. Review the provided laboratory results (CBC, BMP, urinalysis) and chest X-ray, then provide your interpretation and management plan.',
                'instructions': 'Interpret the lab results and imaging provided. Identify abnormalities, formulate a diagnosis, and outline initial management.',
                'items': [
                    {'desc': 'Systematically reviews CBC results (Hb, WBC, platelets)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Identifies renal function abnormalities (creatinine, BUN, GFR)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Identifies electrolyte imbalances (K+, Na+, Ca2+)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Interprets urinalysis findings (proteinuria, casts, hematuria)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Assesses glycemic control parameters (HbA1c, glucose)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Interprets chest X-ray systematically (ABCDE approach)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Identifies pulmonary edema / pleural effusion on CXR', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Correlates lab and imaging findings into a unified clinical picture', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 3},
                    {'desc': 'States correct primary diagnosis (e.g. CKD with fluid overload)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Diagnosis', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Lists appropriate differential diagnoses', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Outlines initial management (fluid, electrolytes, diuretics)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Addresses urgent needs (hyperkalemia management if present)', 'pts': 0.5, 'critical': True, 'rubric': 'binary', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Requests appropriate further investigations', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Management', 'interact': 'passive', 'theme': 4},
                    {'desc': 'Presents interpretation confidently using medical terminology', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                ],
            },
        ],
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # EXAM 2: PEDIATRICS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'Pediatrics OSCE': {
        'course_id': 14,
        'department': 'Pediatrics',
        'stations': [
            {
                'name': 'History Taking — Febrile Child',
                'scenario': 'A 3-year-old child is brought to the pediatric ER by his mother with high fever (39.5°C) for 3 days, irritability, and decreased oral intake. Take a focused pediatric history.',
                'instructions': 'Take a comprehensive pediatric history from the mother. Cover all age-appropriate aspects.',
                'items': [
                    {'desc': 'Introduces self and confirms child identity and relationship with caretaker', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                    {'desc': 'Establishes rapport with parent/caretaker', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                    {'desc': 'Asks about fever characteristics (onset, pattern, max temp, response to antipyretics)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Asks about associated symptoms (rash, cough, diarrhea, vomiting, ear pulling)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Asks about urinary symptoms (frequency, crying during micturition)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Asks about oral intake and hydration status (wet diapers, tears)', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Asks about immunization history', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Asks about birth history and developmental milestones', 'pts': 0.75, 'critical': False, 'rubric': 'binary', 'cat': 'History', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Asks about previous similar episodes and hospitalizations', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'History', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Asks about sick contacts and daycare attendance', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'History', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Asks about medications given at home', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'History', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Screens for red flag symptoms (rash, neck stiffness, seizures, lethargy)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Provides appropriate differential diagnoses', 'pts': 1.0, 'critical': False, 'rubric': 'partial', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Demonstrates empathy and uses age-appropriate language', 'pts': 0.75, 'critical': False, 'rubric': 'binary', 'cat': 'Communication', 'interact': 'passive', 'theme': 6},
                ],
            },
            {
                'name': 'Clinical Examination — Respiratory System (Child)',
                'scenario': 'A 5-year-old boy presents with chronic cough and recurrent wheezing. Perform a focused respiratory examination.',
                'instructions': 'Perform a systematic respiratory examination on the pediatric mannequin/standardized patient. Narrate your findings.',
                'items': [
                    {'desc': 'Introduces self, explains procedure, and gains child cooperation', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                    {'desc': 'Washes hands / uses hand hygiene', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Professionalism', 'interact': 'passive', 'theme': 6},
                    {'desc': 'Performs general inspection (alertness, respiratory distress signs, color)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Counts respiratory rate and assesses work of breathing', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Looks for subcostal/intercostal retractions and nasal flaring', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Assesses oxygen saturation (states value or method)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Inspects chest for symmetry, deformities, Harrison sulcus', 'pts': 0.5, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Palpates trachea and chest expansion', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Percusses chest anteriorly and posteriorly', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Auscultates all lung zones (anterior, posterior, axillae)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Identifies abnormal breath sounds (wheeze, crackles, reduced air entry)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Checks for digital clubbing and peripheral cyanosis', 'pts': 0.75, 'critical': False, 'rubric': 'binary', 'cat': 'Skills', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Examines for lymphadenopathy (cervical, axillary)', 'pts': 0.75, 'critical': False, 'rubric': 'binary', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Presents findings clearly with appropriate differential', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                ],
            },
            {
                'name': 'Growth Chart Interpretation',
                'scenario': 'You are given the growth chart of a 2-year-old girl brought for a well-child visit. She was born at term with a birth weight of 3.2 kg. Review the growth trajectory and identify any concerns.',
                'instructions': 'Interpret the growth chart provided. Identify the growth pattern, flag abnormalities, and suggest an approach.',
                'items': [
                    {'desc': 'Identifies the correct chart type (WHO/CDC) and gender/age', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Approach', 'interact': 'passive', 'theme': 4},
                    {'desc': 'Reads weight-for-age percentile correctly', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Reads length/height-for-age percentile correctly', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Reads head circumference-for-age percentile correctly', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Calculates and interprets weight-for-length (BMI equivalent)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Identifies crossing of percentile lines (growth faltering or acceleration)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Identifies failure-to-thrive pattern if present', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Diagnosis', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Notes birth weight and compares with current trajectory', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Asks about dietary history and feeding practices', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Considers genetic/familial short stature (mid-parental height)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Lists differential diagnoses for growth abnormality', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Suggests appropriate investigations (CBC, TFTs, celiac screen)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Provides counseling points for parents on nutrition', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                    {'desc': 'Overall structured approach and clinical reasoning', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 4},
                ],
            },
            {
                'name': 'Neonatal Resuscitation Scenario',
                'scenario': 'You are called to attend the delivery of a term infant born via emergency C-section for fetal distress. At birth, the infant is floppy, not breathing, heart rate 80 bpm. Demonstrate your neonatal resuscitation approach.',
                'instructions': 'Using the neonatal mannequin, demonstrate the steps of neonatal resuscitation following NRP guidelines.',
                'items': [
                    {'desc': 'Calls for help and activates neonatal resuscitation team', 'pts': 0.5, 'critical': True, 'rubric': 'binary', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Performs initial steps: warm, dry, stimulate, position airway', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Clears airway with appropriate suctioning technique', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Assesses breathing and heart rate after initial steps', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Initiates positive pressure ventilation (PPV) with correct technique', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Uses correct FiO2 for term infant (starts with 21% or room air)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Assesses chest rise with ventilation and adjusts if needed (MR SOPA)', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Evaluates heart rate after 30 seconds of effective PPV', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Identifies indications for chest compressions (HR < 60 bpm)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Demonstrates correct compression:ventilation ratio (3:1)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Knows indications and dose of epinephrine', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Applies pulse oximetry to right hand (pre-ductal)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Skills', 'interact': 'passive', 'theme': 4},
                    {'desc': 'Assigns Apgar score at 1 and 5 minutes', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Assessment', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Communicates clearly with team and updates parents', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                ],
            },
        ],
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # EXAM 3: SURGERY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'Surgery OSCE': {
        'course_id': 16,
        'department': 'General Surgery',
        'stations': [
            {
                'name': 'History Taking — Acute Abdomen',
                'scenario': 'A 40-year-old male presents to the ER with severe abdominal pain that started 6 hours ago. The pain is periumbilical and has since localized to the right iliac fossa. Take a focused surgical history.',
                'instructions': 'Take a systematic surgical history from the standardized patient to evaluate the acute abdomen.',
                'items': [
                    {'desc': 'Introduces self and confirms patient identity', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                    {'desc': 'Establishes rapport and uses open-ended questions initially', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                    {'desc': 'Characterizes pain systematically (SOCRATES: Site, Onset, Character, Radiation, Associations, Time, Exacerbating/relieving, Severity)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Identifies migratory nature of pain (periumbilical → RIF)', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Asks about associated GI symptoms (nausea, vomiting, anorexia, bowel habits)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Asks about urinary symptoms to rule out renal colic/UTI', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Asks about fever and rigors', 'pts': 0.75, 'critical': False, 'rubric': 'binary', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Takes relevant past surgical and medical history', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Asks about medications, allergies, and last meal (fasting status)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Considers and asks about complications (perforation signs: sudden worsening)', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Asks about travel and contact history (infectious causes)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'History', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Provides focused differential diagnosis (appendicitis, mesenteric adenitis, renal colic)', 'pts': 1.0, 'critical': False, 'rubric': 'partial', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Outlines initial investigation plan (bloods, imaging)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Maintains professional demeanor and reassures patient', 'pts': 0.75, 'critical': False, 'rubric': 'binary', 'cat': 'Professionalism', 'interact': 'passive', 'theme': 6},
                ],
            },
            {
                'name': 'Surgical Examination — Abdominal Mass',
                'scenario': 'A 65-year-old female presents with a palpable mass in the right hypochondrium discovered incidentally. Perform a focused abdominal examination.',
                'instructions': 'Perform a systematic surgical abdominal examination focusing on the palpable mass. Demonstrate all relevant clinical signs.',
                'items': [
                    {'desc': 'Introduces self, obtains consent, and ensures patient comfort', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                    {'desc': 'Washes hands and positions patient supine with knees flexed', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Professionalism', 'interact': 'passive', 'theme': 6},
                    {'desc': 'Inspects abdomen (distension, scars, visible masses, skin changes)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Asks about tenderness before palpation', 'pts': 0.75, 'critical': False, 'rubric': 'binary', 'cat': 'Skills', 'interact': 'passive', 'theme': 6},
                    {'desc': 'Performs light palpation of all 9 regions systematically', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Performs deep palpation to characterize the mass (size, shape, surface, consistency, mobility, tenderness)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Checks if mass moves with respiration (hepatomegaly/splenomegaly)', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Attempts to get above/below the mass (distinguishing organ origin)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Performs percussion over mass (dull vs. resonant → solid vs. cystic)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Checks for shifting dullness / fluid thrill (ascites)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Auscultates for bowel sounds and bruits', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Examines for hepatomegaly and splenomegaly using bimanual technique', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Checks for lymphadenopathy and relevant peripheral signs', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Skills', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Presents findings with appropriate differential diagnosis', 'pts': 1.0, 'critical': False, 'rubric': 'partial', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                ],
            },
            {
                'name': 'Surgical Instrument Identification',
                'scenario': 'You are shown 7 commonly used surgical instruments. Identify each instrument, describe its use, and state in which surgical procedure it is commonly employed.',
                'instructions': 'Identify the instruments displayed, describe their function, and mention clinical applications.',
                'items': [
                    {'desc': 'Identifies Scalpel (handle + blade) and describes use for incision', 'pts': 0.75, 'critical': False, 'rubric': 'binary', 'cat': 'Knowledge', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Identifies Kelly/Mosquito forceps and describes hemostasis use', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Knowledge', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Identifies Metzenbaum scissors and differentiates from Mayo scissors', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Knowledge', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Identifies Needle holder (different from forceps) and describes suturing role', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Knowledge', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Identifies Babcock / Allis forceps and describes tissue grasping', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Knowledge', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Identifies Retractor (e.g. Langenbeck, Army-Navy) and describes exposure', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Knowledge', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Identifies Suction device (Yankauer) and describes intraoperative use', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Knowledge', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Correctly describes at least 3 instruments\' surgical applications', 'pts': 1.0, 'critical': False, 'rubric': 'partial', 'cat': 'Application', 'interact': 'passive', 'theme': 4},
                    {'desc': 'Differentiates between cutting and dissecting instruments', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Knowledge', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Demonstrates correct holding technique for at least 2 instruments', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Describes sterile handling principles for surgical instruments', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Professionalism', 'interact': 'passive', 'theme': 6},
                    {'desc': 'Names the appropriate suture material for at least 2 procedures', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Knowledge', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Explains basic instrument care and decontamination', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Professionalism', 'interact': 'passive', 'theme': 6},
                    {'desc': 'Demonstrates confidence and systematic approach throughout', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                ],
            },
            {
                'name': 'Post-operative Management Scenario',
                'scenario': 'A 55-year-old male underwent open cholecystectomy 12 hours ago. He is now tachycardic (HR 110), febrile (38.2°C), hypotensive (BP 90/60), with decreased urine output. Assess and manage this post-operative complication.',
                'instructions': 'Assess the patient, identify the likely complication, and outline your immediate management plan.',
                'items': [
                    {'desc': 'Performs structured ABCDE assessment', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Assessment', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Identifies signs of hypovolemic shock / post-operative hemorrhage', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Diagnosis', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Orders immediate IV fluid resuscitation (type and volume)', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Requests urgent blood work (FBC, coagulation, crossmatch, lactate)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Checks surgical drain output (volume, character)', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'Assessment', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Examines wound site and abdomen for signs of complication', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Assessment', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Inserts urinary catheter to monitor urine output', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Escalates to surgical registrar/consultant appropriately', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Management', 'interact': 'passive', 'theme': 4},
                    {'desc': 'Identifies need for return to operating theatre if ongoing hemorrhage', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Manages pain appropriately (analgesics, dose, route)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Considers and excludes other causes (PE, sepsis, MI)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Orders appropriate imaging (USS abdomen / CT if indicated)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Management', 'interact': 'passive', 'theme': 4},
                    {'desc': 'Documents assessment and management in patient notes', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Professionalism', 'interact': 'passive', 'theme': 6},
                    {'desc': 'Communicates with patient/family about findings and plan', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                ],
            },
        ],
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # EXAM 4: OBSTETRICS & GYNECOLOGY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'Obstetrics & Gynecology OSCE': {
        'course_id': 12,
        'department': 'Obstetrics & Gynecology',
        'stations': [
            {
                'name': 'History Taking — Antenatal Visit',
                'scenario': 'A 28-year-old primigravida at 32 weeks gestation presents for her routine antenatal visit. She reports mild headache and swollen ankles for 2 days. Take a focused antenatal history.',
                'instructions': 'Take a comprehensive antenatal history from the standardized patient. Identify risk factors and red flags.',
                'items': [
                    {'desc': 'Introduces self and confirms patient identity and gestational age', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                    {'desc': 'Establishes rapport and uses empathetic language', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                    {'desc': 'Asks about current pregnancy details (dating, booking, scans)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Asks about current symptoms (headache severity, visual disturbances, epigastric pain)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Asks about edema distribution and progression', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Screens for pre-eclampsia red flags (blurred vision, RUQ pain, sudden swelling)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Asks about fetal movements (frequency, pattern, any decrease)', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Asks about obstetric history (gravidity, parity, previous complications)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Asks about medical history (hypertension, diabetes, renal disease)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'History', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Asks about medications, supplements, and allergies', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'History', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Asks about blood group and Rh status', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'History', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Asks about results of previous investigations (glucose tolerance, anemia screen)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'History', 'interact': 'passive', 'theme': 7},
                    {'desc': 'Provides appropriate differential and identifies pre-eclampsia as concern', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Summarizes history and plans next steps clearly to patient', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Communication', 'interact': 'passive', 'theme': 6},
                ],
            },
            {
                'name': 'Clinical Examination — Obstetric Examination',
                'scenario': 'A 30-year-old multigravida at 36 weeks gestation presents for routine assessment. Perform a complete obstetric abdominal examination.',
                'instructions': 'Perform a systematic obstetric abdominal examination on the mannequin/standardized patient. Determine fetal lie, presentation, and engagement.',
                'items': [
                    {'desc': 'Introduces self, explains procedure, obtains consent', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                    {'desc': 'Washes hands and ensures patient comfort and privacy', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Professionalism', 'interact': 'passive', 'theme': 6},
                    {'desc': 'Positions patient supine with slight left lateral tilt', 'pts': 0.75, 'critical': False, 'rubric': 'binary', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Inspects abdomen (size, shape, scars, striae, linea nigra)', 'pts': 0.5, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Measures symphysis-fundal height (SFH) correctly using tape', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Performs fundal palpation (identifies what occupies the fundus)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Performs lateral palpation (determines fetal lie — longitudinal/transverse)', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Performs Pawlik grip (identifies presenting part — cephalic/breech)', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Performs deep pelvic grip to assess engagement (fifths palpable)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Auscultates fetal heart using Pinard or Doppler', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Records fetal heart rate and states normal range (110-160 bpm)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Skills', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Assesses liquor volume clinically (polyhydramnios/oligohydramnios)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Checks for edema, varicosities, and measures BP', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Skills', 'interact': 'passive', 'theme': 7},
                    {'desc': 'Summarizes findings clearly (lie, presentation, engagement, FH)', 'pts': 1.0, 'critical': False, 'rubric': 'partial', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                ],
            },
            {
                'name': 'CTG Interpretation',
                'scenario': 'A 34-week pregnant woman is on continuous CTG monitoring due to reduced fetal movements. You are shown a 20-minute CTG trace. Interpret the trace and recommend management.',
                'instructions': 'Interpret the CTG trace using the DR C BRAVADO systematic approach. Classify the trace and recommend management.',
                'items': [
                    {'desc': 'Uses systematic approach (DR C BRAVADO or equivalent)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Approach', 'interact': 'passive', 'theme': 4},
                    {'desc': 'Defines Risk (reason for monitoring and clinical context)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Checks Contractions (frequency, duration, regularity)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Determines Baseline Rate and states normal range', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Assesses Variability (normal 5-25 bpm, reduced, absent)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Identifies Accelerations (presence/absence, significance)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Identifies Decelerations and classifies type (early, late, variable)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Interpretation', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Differentiates between early, late, and variable decelerations', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'Knowledge', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Classifies overall CTG trace (normal, suspicious, pathological)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Diagnosis', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Explains clinical significance of the CTG findings', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Clinical Reasoning', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Recommends appropriate management based on classification', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Identifies when delivery is indicated (delivery decision)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Mentions conservative measures (position change, hydration, O2)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Management', 'interact': 'passive', 'theme': 7},
                    {'desc': 'Presents interpretation in a structured and confident manner', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                ],
            },
            {
                'name': 'Emergency Scenario — PPH Management',
                'scenario': 'A 32-year-old woman delivered vaginally 30 minutes ago. She is now bleeding heavily (estimated blood loss 1000 mL) and becoming tachycardic. Manage this postpartum hemorrhage.',
                'instructions': 'Demonstrate your systematic approach to managing primary PPH. Use the mannequin and state your actions clearly.',
                'items': [
                    {'desc': 'Calls for help and activates major obstetric hemorrhage protocol', 'pts': 0.5, 'critical': True, 'rubric': 'binary', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Performs ABCDE assessment and secures IV access (2 large bore)', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'Management', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Initiates fluid resuscitation (crystalloid, then blood products)', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Identifies the 4 Ts of PPH (Tone, Trauma, Tissue, Thrombin)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Knowledge', 'interact': 'passive', 'theme': 1},
                    {'desc': 'Performs uterine massage (rubbing up the fundus)', 'pts': 0.75, 'critical': True, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Administers uterotonics (oxytocin, ergometrine, misoprostol — correct doses)', 'pts': 1.0, 'critical': True, 'rubric': 'partial', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Examines for genital tract trauma (cervical/vaginal tears)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Ensures placenta is complete (no retained products)', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Requests bloods (FBC, coagulation screen, crossmatch, fibrinogen)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Monitors vital signs continuously and documents blood loss', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Management', 'interact': 'passive', 'theme': 4},
                    {'desc': 'Inserts urinary catheter and monitors urine output', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Considers bimanual uterine compression if uterus remains atonic', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Skills', 'interact': 'passive', 'theme': 2},
                    {'desc': 'Knows escalation pathway (balloon tamponade, surgical options, interventional radiology)', 'pts': 0.5, 'critical': False, 'rubric': 'binary', 'cat': 'Management', 'interact': 'passive', 'theme': 3},
                    {'desc': 'Communicates with team and patient/family throughout', 'pts': 0.75, 'critical': False, 'rubric': 'partial', 'cat': 'Communication', 'interact': 'passive', 'theme': 5},
                ],
            },
        ],
    },
}

# ─────────────────────────────────────────────────────────────────────
# ARABIC STUDENT NAMES (100 per exam = 400 total unique)
# ─────────────────────────────────────────────────────────────────────
MALE_FIRST = [
    'محمد', 'أحمد', 'عمر', 'خالد', 'يوسف', 'عبدالله', 'حسن', 'علي', 'إبراهيم', 'سعد',
    'ماجد', 'فيصل', 'عبدالرحمن', 'طارق', 'وليد', 'سامي', 'ناصر', 'ياسر', 'فهد', 'بلال',
    'حمزة', 'زياد', 'أنس', 'عادل', 'مصطفى', 'رائد', 'هاشم', 'تامر', 'جمال', 'كريم',
    'رامي', 'باسم', 'صالح', 'عمار', 'سليمان', 'منصور', 'نواف', 'حسين', 'عبدالعزيز', 'مالك',
]
FEMALE_FIRST = [
    'فاطمة', 'مريم', 'نور', 'سارة', 'لينا', 'رنا', 'هند', 'دانة', 'ريم', 'أميرة',
    'آية', 'لمى', 'تالا', 'جنى', 'رغد', 'شهد', 'ياسمين', 'ديما', 'هالة', 'سلمى',
    'عبير', 'مها', 'رانيا', 'سمر', 'غادة', 'منال', 'وفاء', 'إسراء', 'نهى', 'بيان',
    'رشا', 'لبنى', 'نجلاء', 'هبة', 'ملاك', 'أسماء', 'زينب', 'سحر', 'نسرين', 'رنيم',
]
FATHER_NAMES = [
    'محمد', 'أحمد', 'خالد', 'عبدالله', 'سعيد', 'إبراهيم', 'علي', 'حسن', 'عمر', 'يوسف',
    'ماجد', 'فيصل', 'سامي', 'ناصر', 'طارق', 'جمال', 'صالح', 'منصور', 'فهد', 'وليد',
    'حسين', 'عادل', 'كمال', 'رشيد', 'هاني', 'نبيل', 'بسام', 'زياد', 'رياض', 'شريف',
]
LAST_NAMES = [
    'الأحمد', 'العلي', 'المحمد', 'الحسن', 'السعيد', 'الخالدي', 'الشمري', 'العتيبي',
    'الحربي', 'الدوسري', 'القحطاني', 'الزهراني', 'المطيري', 'العنزي', 'البلوي',
    'الرشيدي', 'الشهري', 'الغامدي', 'الجهني', 'السبيعي', 'الثبيتي', 'العمري',
    'المالكي', 'الحازمي', 'النعيمي', 'الكعبي', 'البدري', 'المنصوري', 'الهاشمي', 'الصالحي',
    'الطراونة', 'الزعبي', 'المصري', 'الكيلاني', 'الحمداني', 'الربيعي', 'العبيدي',
    'النجار', 'الحداد', 'البكري',
]

def generate_student_name(rng):
    """Generate a random Arabic student name."""
    gender = rng.choice(['M', 'F'])
    if gender == 'M':
        first = rng.choice(MALE_FIRST)
    else:
        first = rng.choice(FEMALE_FIRST)
    father = rng.choice(FATHER_NAMES)
    last = rng.choice(LAST_NAMES)
    return f'{first} {father} {last}'


def generate_student_number(rng, used_numbers):
    """Generate a unique 8-digit student number."""
    while True:
        num = f'1224{rng.randint(1000, 9999)}'
        if num not in used_numbers:
            used_numbers.add(num)
            return num


# ─────────────────────────────────────────────────────────────────────
# MAIN SEEDER
# ─────────────────────────────────────────────────────────────────────
def seed_all():
    rng = random.Random(42)  # deterministic for reproducibility
    all_used_numbers = set()

    # Collect existing student numbers to avoid collision
    for sn in SessionStudent.objects.values_list('student_number', flat=True):
        all_used_numbers.add(sn)

    total_exams = 0
    total_sessions = 0
    total_paths = 0
    total_stations = 0
    total_items = 0
    total_students = 0

    for exam_name, exam_def in EXAM_DEFS.items():
        course_id = exam_def['course_id']
        department = exam_def['department']
        station_defs = exam_def['stations']

        print(f'\n{"="*60}')
        print(f'  Creating: {exam_name}')
        print(f'  Course ID: {course_id} | Department: {department}')
        print(f'{"="*60}')

        # ── Create Exam ──────────────────────────────────────────────
        exam = Exam.objects.create(
            course_id=course_id,
            name=exam_name,
            description=f'6th Year {department} OSCE Examination — 1/3 station format, 7 min/station, 4 stations.',
            exam_date=EXAM_DATE,
            department=department,
            number_of_stations=4,
            station_duration_minutes=STATION_DURATION,
            exam_weight=40.00,
            status='draft',
        )
        total_exams += 1
        print(f'  ✓ Exam created: {exam.id}')

        # ── Create 2 Sessions ────────────────────────────────────────
        sessions_config = [
            {'name': f'{department} — Morning Session', 'type': 'morning', 'start': time(8, 0)},
            {'name': f'{department} — Afternoon Session', 'type': 'afternoon', 'start': time(13, 0)},
        ]

        sessions = []
        for sc in sessions_config:
            session = ExamSession.objects.create(
                exam=exam,
                name=sc['name'],
                session_date=EXAM_DATE,
                session_type=sc['type'],
                start_time=sc['start'],
                number_of_stations=4,
                number_of_paths=NUM_PATHS_PER_SESSION,
                status='scheduled',
                created_at=NOW_TS,
                updated_at=NOW_TS,
            )
            sessions.append(session)
            total_sessions += 1
            print(f'  ✓ Session: {session.name} ({session.id})')

        # ── Create 10 Paths (5 per session) ──────────────────────────
        path_objects = []
        for sess_idx, session in enumerate(sessions):
            for p_num in range(1, NUM_PATHS_PER_SESSION + 1):
                path_name = str(sess_idx * NUM_PATHS_PER_SESSION + p_num)
                path = Path.objects.create(
                    session=session,
                    name=path_name,
                    rotation_minutes=ROTATION_MINUTES,
                    is_active=True,
                    is_deleted=False,
                )
                path_objects.append((session, path))
                total_paths += 1

        print(f'  ✓ {len(path_objects)} paths created')

        # ── Create Stations + Checklist Items (4 per path, identical) ─
        for session, path in path_objects:
            for stn_idx, stn_def in enumerate(station_defs, start=1):
                station = Station.objects.create(
                    path=path,
                    exam=exam,
                    station_number=stn_idx,
                    name=stn_def['name'],
                    scenario=stn_def['scenario'],
                    instructions=stn_def['instructions'],
                    duration_minutes=STATION_DURATION,
                    active=True,
                    is_deleted=False,
                )
                total_stations += 1

                for item_idx, item_def in enumerate(stn_def['items'], start=1):
                    ChecklistItem.objects.create(
                        station=station,
                        ilo_id=ilo_id_for(course_id, item_def['theme']),
                        item_number=item_idx,
                        description=item_def['desc'],
                        points=item_def['pts'],
                        category=item_def['cat'],
                        is_critical=item_def['critical'],
                        rubric_type=item_def['rubric'],
                        interaction_type=item_def['interact'],
                    )
                    total_items += 1

        print(f'  ✓ {total_stations} stations + {total_items} checklist items (so far)')

        # ── Create Students (10 per path, 100 per exam) ───────────────
        for session, path in path_objects:
            for _ in range(NUM_STUDENTS_PER_PATH):
                name = generate_student_name(rng)
                num = generate_student_number(rng, all_used_numbers)
                SessionStudent.objects.create(
                    session=session,
                    path=path,
                    student_number=num,
                    full_name=name,
                    status='registered',
                    created_at=NOW_TS,
                )
                total_students += 1

        print(f'  ✓ {total_students} students created (so far)')

    # ── Summary ───────────────────────────────────────────────────────
    print(f'\n{"="*60}')
    print(f'  SEED COMPLETE')
    print(f'{"="*60}')
    print(f'  Exams created:     {total_exams}')
    print(f'  Sessions created:  {total_sessions}')
    print(f'  Paths created:     {total_paths}')
    print(f'  Stations created:  {total_stations}')
    print(f'  Checklist items:   {total_items}')
    print(f'  Students created:  {total_students}')
    print(f'{"="*60}')


if __name__ == '__main__':
    # Safety: ask for confirmation
    print('='*60)
    print('  OSCE Demo Data Seeder')
    print('  This will INSERT demo data into your database.')
    print('  No existing data will be modified or deleted.')
    print('='*60)
    confirm = input('  Proceed? [y/N]: ').strip().lower()
    if confirm == 'y':
        seed_all()
    else:
        print('  Aborted.')
