import os
import json
import hashlib
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from helpers.listing_helper import ListingData
from typing import Generator, Optional

def hash_image(image) -> str:
    return hashlib.md5(image.tobytes()).hexdigest()[:16]

_EQUIPMENT: dict = {
    "mini-ex": {
        "kind": "rental",
        "model": "kx71",
        "names": {
            "eng": ["Mini-Excavator"],
            "spa": ["Excavadora Compacta"],
        },
        "prices": {"daily": 200, "weekly": 750, "monthly": 2250},
        "blurb": {
            "eng": "KX030-4; 7,700#; 12in and 24in buckets",
            "spa": "KX030-4; 7,700#; 12in y 24in cucharas",
        },
    },
    "trackloader": {
        "kind": "rental",
        "model": "svl75",
        "names": {
            "eng": ["Skidsteer"],
            "spa": ["Cargadora compacta"],
        },
        "prices": {"daily": 280, "weekly": 1000, "monthly": 3000},
        "blurb": {
            "eng": "SVL75-2; 9,100#, 75 HP; Toothed & Smooth buckets, Standard Flow Attachments",
            "spa": "SVL75-2; 9,100#, 75 HP; Cucharas dentadas y lisas, accesorios de flujo estándar",
        },
    },
    # ── Service listings ──────────────────────────────────────────────────────
    # Not a rentable machine: no real product photos exist, so get_listings()
    # generates a short text-card image instead (see generate_text_card_image).
    # Restricted to a single launch city per service via "cities" until proven
    # out; "price" is a flat number (not daily/weekly/monthly tiers) since these
    # are repair/shredding services, not rentals.
    "trimmer_repair": {
        "kind": "service",
        "cities": ["Waco"],
        "image_text": "Weedeater Repair",
        "price": 60,
        "blurb": {"eng": "Free diagnostic on every trimmer and weedeater repair — if we can't fix it, there's no charge."},
    },
    "pushmower_repair": {
        "kind": "service",
        "cities": ["Waco"],
        "image_text": "Push Mower Repair",
        "price": 60,
        "blurb": {"eng": "Free diagnostic on every push mower repair — if we can't fix it, there's no charge."},
    },
    "ridingmower_repair": {
        "kind": "service",
        "cities": ["Waco"],
        "image_text": "Riding Mower Repair",
        "price": 60,
        "blurb": {"eng": "Free diagnostic on every riding mower repair — if we can't fix it, there's no charge."},
    },
    "zeroturn_repair": {
        "kind": "service",
        "cities": ["Waco"],
        "image_text": "Zero-Turn Repair",
        "price": 60,
        "blurb": {"eng": "Free diagnostic on every zero-turn repair — if we can't fix it, there's no charge."},
    },
    "tiller_repair": {
        "kind": "service",
        "cities": ["Waco"],
        "image_text": "Tiller Repair",
        "price": 60,
        "blurb": {"eng": "Free diagnostic on every tiller repair — if we can't fix it, there's no charge."},
    },
    "generator_repair": {
        "kind": "service",
        "cities": ["Waco"],
        "image_text": "Generator Repair",
        "price": 60,
        "blurb": {"eng": "Free diagnostic on every generator repair — if we can't fix it, there's no charge."},
    },
    "field_shredding": {
        "kind": "service",
        "cities": ["Lorena"],
        "image_text": "Field Shredding",
        "price": 50,
        "blurb": {"eng": "Field shredding / brush hogging for overgrown lots, pastures, and acreage — starting at $50/acre depending on overgrowth."},
    },
}


def get_equipment() -> dict:
    return _EQUIPMENT




TASK_VARIANTS = {
    "mini-ex": [
        {
            "slug": "drainage",
            "titles": {
                "eng": [
                    "Mini Excavator Rental – Drainage & Trenching – {city}",
                    "French Drain Install? Mini Ex Rental – {city}",
                    "Trenching for Irrigation/Utilities? Mini Excavator – {city}",
                    "Backfilling Trenches? Mini Excavator Available – {city}",
                    "Mini Ex for Foundation/Drainage Work – {city}",
                ],
                "spa": [
                    "Renta Mini Excavadora – Drenaje y Zanjas – {city}",
                    "¿Dren Francés? Mini Ex Disponible – {city}",
                    "Zanjas para Riego o Utilidades? Mini Excavadora – {city}",
                    "Mini Ex para Drenaje de Cimientos – {city}",
                    "Rellenar Zanjas? Mini Excavadora Disponible – {city}",
                ],
            },
            "desc_intro": {
                "eng": "Need to install a French drain, trench for irrigation, or redirect water away from your foundation? Our mini-excavator handles all of it.",
                "spa": "¿Necesitas instalar un dren francés, zanjas para riego, o redirigir el agua de tu cimentación? Nuestra mini excavadora lo maneja todo.",
            },
        },
        {
            "slug": "grading",
            "titles": {
                "eng": [
                    "Mini Ex Rental for Yard Grading & Footings – {city}",
                    "Uneven Yard Leveling? Mini Ex Ready – {city}",
                    "Mini Excavator for Land Grading – {city}",
                    "Grade Your Lot with a Mini Excavator – {city}",
                    "Footing Excavation & Yard Leveling – Mini Ex – {city}",
                ],
                "spa": [
                    "Renta Mini Ex para Nivelar Patio – {city}",
                    "¿Patio Desnivelado? Mini Ex Lista – {city}",
                    "Mini Excavadora para Nivelar Terreno – {city}",
                    "Nivelar tu Lote con Mini Excavadora – {city}",
                    "Excavación de Cimientos y Nivelación – Mini Ex – {city}",
                ],
            },
            "desc_intro": {
                "eng": "Sloped yard, uneven lot, or need footings for a slab or addition? Our mini-excavator is perfect for precision grading and excavation.",
                "spa": "¿Patio inclinado, terreno desnivelado, o necesitas cimientos para una losa? Nuestra mini excavadora es perfecta para nivelar con precisión.",
            },
        },
        {
            "slug": "pond",
            "titles": {
                "eng": [
                    "Compact Excavator for Pond/Landscaping – {city}",
                    "Dig a Backyard Pond? Mini Excavator Rental – {city}",
                    "Mini Ex for Pond Digging & Landscaping – {city}",
                    "Backyard Pond or Water Feature? Mini Ex – {city}",
                    "Mini Excavator for Landscaping Projects – {city}",
                ],
                "spa": [
                    "Excavadora Compacta para Estanque/Paisaje – {city}",
                    "¿Estanque en Patio? Renta Mini Excavadora – {city}",
                    "Mini Ex para Excavar Estanques – {city}",
                    "Estanque o Fuente de Agua? Mini Ex – {city}",
                    "Mini Excavadora para Paisajismo – {city}",
                ],
            },
            "desc_intro": {
                "eng": "Building a backyard pond, water feature, or landscaping project? Our mini-excavator makes quick work of digging and shaping.",
                "spa": "¿Construyendo un estanque, fuente de agua, o proyecto de paisajismo? Nuestra mini excavadora hace rápido el trabajo de excavar y moldear.",
            },
        },
        {
            "slug": "site_prep",
            "titles": {
                "eng": [
                    "Site Prep for Patio/Wall? Mini Excavator – {city}",
                    "Mini Ex Rental – Patio & Retaining Wall Prep – {city}",
                    "Excavate for a Patio or Addition? Mini Ex – {city}",
                    "Mini Excavator for Construction Site Prep – {city}",
                    "Retaining Wall or Patio Install? Mini Ex Rental – {city}",
                ],
                "spa": [
                    "Prep Terreno Terraza/Muro? Mini Ex – {city}",
                    "Renta Mini Ex – Prep para Patio y Muro de Contención – {city}",
                    "Excavar para Patio o Ampliación? Mini Ex – {city}",
                    "Mini Excavadora para Preparar Sitio de Construcción – {city}",
                    "Muro de Contención o Patio? Renta Mini Ex – {city}",
                ],
            },
            "desc_intro": {
                "eng": "Prepping for a new patio, retaining wall, addition, or outbuilding? Our mini-excavator handles site prep, rough grading, and utility trenching.",
                "spa": "¿Preparando para un nuevo patio, muro de contención, ampliación o construcción auxiliar? Nuestra mini excavadora maneja la preparación del sitio.",
            },
        },
        {
            "slug": "tree_work",
            "titles": {
                "eng": [
                    "Tree Holes or Sod Removal? Mini Ex Rental – {city}",
                    "Mini Excavator for Tree Removal & Planting – {city}",
                    "Stump & Root Removal with Mini Ex – {city}",
                    "Mini Ex for Tree Planting & Sod Work – {city}",
                    "Dig Tree Holes or Remove Sod? Mini Ex – {city}",
                ],
                "spa": [
                    "Hoyos para Árboles o Quitar Pasto? Mini Ex – {city}",
                    "Mini Excavadora para Árboles y Extracción de Pasto – {city}",
                    "Extracción de Tocones y Raíces con Mini Ex – {city}",
                    "Mini Ex para Plantar Árboles y Trabajos de Pasto – {city}",
                    "¿Excavar Hoyos para Árboles? Mini Excavadora – {city}",
                ],
            },
            "desc_intro": {
                "eng": "Need to remove stumps, dig planting holes, pull sod, or clear roots? Our mini-excavator is the right tool for tree and landscape work.",
                "spa": "¿Necesitas quitar tocones, excavar hoyos para plantar, quitar pasto o limpiar raíces? Nuestra mini excavadora es la herramienta perfecta.",
            },
        },
        {
            "slug": "driveway",
            "titles": {
                "eng": [
                    "Gravel Driveway Repair? Mini Excavator – {city}",
                    "Washed-Out Driveway? Mini Ex for Regrade & Culvert – {city}",
                    "New Driveway Excavation & Culvert Install – {city}",
                    "Mini Ex for Driveway Drainage & Potholes – {city}",
                    "Fix or Prep Your Driveway – Mini Excavator – {city}",
                ],
                "spa": [
                    "¿Reparar Entrada de Grava? Mini Excavadora – {city}",
                    "¿Entrada Dañada? Mini Ex para Nivelar y Alcantarilla – {city}",
                    "Excavación de Entrada Nueva e Instalación de Alcantarilla – {city}",
                    "Mini Ex para Drenaje y Baches de Entrada – {city}",
                    "Repara o Prepara tu Entrada – Mini Excavadora – {city}",
                ],
            },
            "desc_intro": {
                "eng": "Washed-out gravel driveway, potholes, or need a culvert and proper drainage? Our mini-excavator digs out, regrades, and preps driveways the right way.",
                "spa": "¿Entrada de grava dañada, baches, o necesitas una alcantarilla y buen drenaje? Nuestra mini excavadora excava, nivela y prepara entradas correctamente.",
            },
        },
    ],
    "trackloader": [
        {
            "slug": "clearing",
            "titles": {
                "eng": [
                    "Track Loader Rental – Land Clearing – {city}",
                    "Brush & Land Clearing with Track Loader – {city}",
                    "Skid Steer Rental for Land Clearing – {city}",
                    "Clear Brush, Trees & Debris – Track Loader – {city}",
                    "Track Loader Available for Clearing Work – {city}",
                ],
                "spa": [
                    "Renta Cargadora de Orugas – Limpieza de Terreno – {city}",
                    "Limpieza de Maleza y Terreno con Cargadora – {city}",
                    "Renta Skid Steer para Limpieza de Terreno – {city}",
                    "Limpiar Maleza, Árboles y Escombros – Cargadora – {city}",
                    "Cargadora de Orugas Disponible para Limpieza – {city}",
                ],
            },
            "desc_intro": {
                "eng": "Clearing overgrown land, removing brush, or preparing a lot for development? Our track loader handles heavy clearing work efficiently.",
                "spa": "¿Limpiando terreno, quitando maleza, o preparando un lote para construcción? Nuestra cargadora de orugas maneja trabajos pesados eficientemente.",
            },
        },
        {
            "slug": "grading",
            "titles": {
                "eng": [
                    "Track Loader Rental – Grading & Leveling – {city}",
                    "Grade & Level Your Land – Skid Steer Rental – {city}",
                    "Track Loader for Land Grading – {city}",
                    "Lot Grading & Leveling with Track Loader – {city}",
                    "Skid Steer Available for Grading Projects – {city}",
                ],
                "spa": [
                    "Renta Cargadora – Nivelación y Grading – {city}",
                    "Nivelar tu Terreno – Renta Skid Steer – {city}",
                    "Cargadora de Orugas para Nivelación – {city}",
                    "Nivelación de Lote con Cargadora de Orugas – {city}",
                    "Skid Steer Disponible para Proyectos de Nivelación – {city}",
                ],
            },
            "desc_intro": {
                "eng": "Need to grade a lot, level a pad, or move large amounts of dirt? Our track loader has the power and capacity to get it done fast.",
                "spa": "¿Necesitas nivelar un lote, preparar una base, o mover grandes cantidades de tierra? Nuestra cargadora tiene la potencia para hacerlo rápido.",
            },
        },
        {
            "slug": "demo",
            "titles": {
                "eng": [
                    "Track Loader for Demolition & Cleanup – {city}",
                    "Skid Steer Rental – Demo & Debris Removal – {city}",
                    "Demolition Work? Track Loader Rental – {city}",
                    "Remove Old Structures with a Track Loader – {city}",
                    "Track Loader for Concrete & Demo Work – {city}",
                ],
                "spa": [
                    "Cargadora de Orugas para Demolición y Limpieza – {city}",
                    "Renta Skid Steer – Demolición y Retiro de Escombros – {city}",
                    "¿Trabajo de Demolición? Renta Cargadora – {city}",
                    "Quitar Estructuras Viejas con Cargadora de Orugas – {city}",
                    "Cargadora para Trabajo de Concreto y Demolición – {city}",
                ],
            },
            "desc_intro": {
                "eng": "Tearing down old structures, removing concrete, or hauling away debris? Our track loader is built for demo and cleanup work.",
                "spa": "¿Derrumbando estructuras viejas, quitando concreto, o retirando escombros? Nuestra cargadora de orugas está hecha para demolición y limpieza.",
            },
        },
        {
            "slug": "foundation",
            "titles": {
                "eng": [
                    "Track Loader for Foundation & Pad Work – {city}",
                    "Skid Steer Rental – Foundation Prep – {city}",
                    "Build a Concrete Pad? Track Loader Rental – {city}",
                    "Foundation Prep & Dirt Work – Track Loader – {city}",
                    "Track Loader Available for Pad & Foundation – {city}",
                ],
                "spa": [
                    "Cargadora de Orugas para Cimientos y Bases – {city}",
                    "Renta Skid Steer – Preparación de Cimientos – {city}",
                    "¿Construir Base de Concreto? Renta Cargadora – {city}",
                    "Preparación de Cimientos y Movimiento de Tierra – {city}",
                    "Cargadora Disponible para Bases y Cimientos – {city}",
                ],
            },
            "desc_intro": {
                "eng": "Prepping for a concrete pad, building foundation, or slab pour? Our track loader is ideal for moving material and establishing grade.",
                "spa": "¿Preparando para una base de concreto, cimientos de construcción, o colada de losa? Nuestra cargadora es ideal para mover material y establecer nivel.",
            },
        },
        {
            "slug": "driveway",
            "titles": {
                "eng": [
                    "Gravel Driveway Repair & Regrading – Skid Steer – {city}",
                    "Spread Gravel or Level Your Driveway – Track Loader – {city}",
                    "Pothole & Washboard Driveway Fix – Skid Steer – {city}",
                    "New Gravel Driveway? Track Loader Rental – {city}",
                    "Track Loader for Driveway Grading & Gravel – {city}",
                ],
                "spa": [
                    "Reparación y Nivelación de Entrada de Grava – Skid Steer – {city}",
                    "Esparcir Grava o Nivelar tu Entrada – Cargadora – {city}",
                    "Arreglo de Baches y Surcos en Entrada – Skid Steer – {city}",
                    "¿Entrada de Grava Nueva? Renta Cargadora de Orugas – {city}",
                    "Cargadora de Orugas para Nivelar Entradas y Grava – {city}",
                ],
            },
            "desc_intro": {
                "eng": "Rutted, potholed, or washboarded gravel driveway? Our track loader spreads new gravel, regrades, and levels driveways fast — or builds a new one from scratch.",
                "spa": "¿Entrada de grava con baches, surcos o desniveles? Nuestra cargadora de orugas esparce grava nueva, nivela y repara entradas rápido — o construye una nueva.",
            },
        },
    ],
    # ── Service task variants (English only, single launch city per service) ──
    "trimmer_repair": [
        {
            "slug": "wont_start",
            "titles": {"eng": ["Weedeater Won't Start? – {city} Repair", "Trimmer Won't Start – Fast {city} Repair"]},
            "desc_intro": {"eng": "Pulling and pulling with nothing happening usually means carb or fuel line trouble, not a dead trimmer — we can usually get it running same week."},
        },
        {
            "slug": "cheaper_than_new",
            "titles": {"eng": ["String Trimmer Repair – Cheaper Than a New One – {city}", "Don't Replace That Trimmer – {city} Repair"]},
            "desc_intro": {"eng": "Before you drop money on a new weedeater, let us take a look — most trimmer issues are a quick, inexpensive fix."},
        },
        {
            "slug": "wont_feed_line",
            "titles": {"eng": ["Trimmer Won't Feed Line? Fast Fix – {city}", "String Trimmer Head Just Spins? – {city} Repair"]},
            "desc_intro": {"eng": "If the head just spins and spins without feeding string, it's almost always a worn spring or tangled spool — we fix it while you wait."},
        },
        {
            "slug": "bogs_down",
            "titles": {"eng": ["Weedeater Bogs Down and Dies in Tall Grass – {city}", "Trimmer Dies in Thick Weeds? – {city} Repair"]},
            "desc_intro": {"eng": "If your trimmer runs fine at idle but dies the second it hits thick weeds, that's a carburetor or air filter problem we see constantly."},
        },
        {
            "slug": "revs_no_spin",
            "titles": {"eng": ["Trimmer Revs but Cutting Head Won't Spin – {city}", "Weedeater Motor Fine, Head Won't Turn? – {city}"]},
            "desc_intro": {"eng": "If the motor sounds fine but the head just sits there when you squeeze the throttle, that's usually a worn clutch or drive shaft, not a dead trimmer."},
        },
        {
            "slug": "spring_tuneup",
            "titles": {"eng": ["Trimmer Spring Tune-Up – Get Ready for Mowing Season – {city}", "Weedeater Sat All Winter? Tune-Up in {city}"]},
            "desc_intro": {"eng": "Sat in the shed all winter and now won't start or runs rough? Old fuel gums up the carb — we'll get it back in shape before the grass takes over."},
        },
    ],
    "pushmower_repair": [
        {
            "slug": "wont_start",
            "titles": {"eng": ["Push Mower Won't Start? – {city} Repair", "Push Mower Cranks But Won't Fire – {city}"]},
            "desc_intro": {"eng": "No spark, no fire, or just cranks and cranks — nine times out of ten it's the carburetor or a fouled spark plug, both quick fixes."},
        },
        {
            "slug": "runs_then_dies",
            "titles": {"eng": ["Push Mower Runs Then Dies – Fast {city} Diagnosis", "Mower Quits After a Minute? – {city} Repair"]},
            "desc_intro": {"eng": "Starts fine, then quits within a minute or two? That's a classic fuel-starvation symptom we can usually fix same visit."},
        },
        {
            "slug": "selfpropel",
            "titles": {"eng": ["Push Mower Self-Propel Not Working – {city}", "Mower Won't Pull Itself? – {city} Repair"]},
            "desc_intro": {"eng": "If the wheels won't pull anymore, it's typically a worn drive cable or belt, not a reason to buy a whole new mower."},
        },
        {
            "slug": "blade_wont_engage",
            "titles": {"eng": ["Mower Blade Won't Engage – {city} Repair", "No Blade Engagement? – {city} Push Mower Fix"]},
            "desc_intro": {"eng": "No blade engagement usually traces back to a bad cable, worn belt, or the blade brake clutch — all repairable."},
        },
        {
            "slug": "cheaper_than_new",
            "titles": {"eng": ["Push Mower Repair – Cheaper Than Buying New – {city}", "Before You Curb That Mower – {city} Repair"]},
            "desc_intro": {"eng": "Before you haul it to the curb, let us look at it. Most push mowers we see need one part, not a replacement."},
        },
        {
            "slug": "winter_start",
            "titles": {"eng": ["Push Mower Won't Start After Sitting All Winter – {city}", "Mower Sat All Winter? – {city} Repair"]},
            "desc_intro": {"eng": "Old gas gums up the carburetor over winter storage — a cleaning and fresh fuel usually has it running again before spring."},
        },
    ],
    "ridingmower_repair": [
        {
            "slug": "wont_start",
            "titles": {"eng": ["Riding Mower Won't Start? – {city} Repair", "Riding Mower Clicks But Won't Crank – {city}"]},
            "desc_intro": {"eng": "Clicking, cranking but no fire, or dead silence — could be the battery, solenoid, or safety switch. We'll find it fast."},
        },
        {
            "slug": "deck_wont_engage",
            "titles": {"eng": ["Riding Mower Deck Won't Engage – {city}", "Blades Won't Kick On? – {city} Riding Mower Repair"]},
            "desc_intro": {"eng": "If the blades won't kick on when you flip the PTO switch, it's usually the clutch, a blown fuse, or a bad switch — all fixable."},
        },
        {
            "slug": "before_buy_new",
            "titles": {"eng": ["Riding Mower Repair – Before You Buy New – {city}", "Don't Replace That Rider – {city} Repair"]},
            "desc_intro": {"eng": "A new rider is a big purchase. Most of the ones we see are one belt or switch away from running fine again."},
        },
        {
            "slug": "belt_slipping",
            "titles": {"eng": ["Riding Mower Belt Keeps Slipping or Coming Off – {city}", "Deck Belt Issues? – {city} Riding Mower Repair"]},
            "desc_intro": {"eng": "A deck belt that won't stay put is usually a worn idler pulley or bad belt tension — we'll get it tracking right."},
        },
        {
            "slug": "wont_move",
            "titles": {"eng": ["Riding Mower Won't Move – Transmission or Hydro Issue – {city}", "Engine Runs, Mower Won't Drive? – {city} Repair"]},
            "desc_intro": {"eng": "Engine runs but the mower won't drive forward or reverse — that's a drive belt or hydrostatic transmission problem, not a lost cause."},
        },
        {
            "slug": "spring_tuneup",
            "titles": {"eng": ["Riding Mower Spring Tune-Up Before Mowing Season – {city}", "Rider Sat All Winter? – {city} Tune-Up"]},
            "desc_intro": {"eng": "Sat in the barn all winter and now cranks but won't fire? Stale fuel and a gummed carb are the usual cause — get ahead of the season."},
        },
    ],
    "zeroturn_repair": [
        {
            "slug": "wont_turn_one_dir",
            "titles": {"eng": ["Zero-Turn Won't Turn One Direction – {city}", "Zero-Turn Dragging on One Side? – {city} Repair"]},
            "desc_intro": {"eng": "If it spins fine one way but drags or won't pivot the other, that's almost always a hydro-drive or steering lever adjustment issue."},
        },
        {
            "slug": "deck_wont_engage",
            "titles": {"eng": ["Zero-Turn Deck Won't Engage – PTO Clutch Issue – {city}", "Blades Won't Kick On? – {city} Zero-Turn Repair"]},
            "desc_intro": {"eng": "Blades not kicking on when you engage the PTO usually means a worn electric clutch, not a mower on its way out."},
        },
        {
            "slug": "before_buy_new",
            "titles": {"eng": ["Zero-Turn Repair – Before You Buy a New One – {city}", "Don't Replace That Zero-Turn – {city} Repair"]},
            "desc_intro": {"eng": "Zero-turns aren't cheap. Most hydro-drive and deck issues we see are a repair, not a replacement."},
        },
        {
            "slug": "pulling_to_side",
            "titles": {"eng": ["Zero-Turn Hydrostatic Drive Pulling to One Side – {city}", "Zero-Turn Drifting Left or Right? – {city} Repair"]},
            "desc_intro": {"eng": "Drifting left or right when you push both levers evenly points to a hydro-drive linkage that's out of adjustment."},
        },
        {
            "slug": "wont_hold_rpm",
            "titles": {"eng": ["Zero-Turn Won't Hold RPM Under Load – {city}", "Zero-Turn Bogging Down? – {city} Repair"]},
            "desc_intro": {"eng": "Engine bogs down the moment the deck engages or you hit thicker grass — usually a carb or governor problem."},
        },
        {
            "slug": "spring_checkup",
            "titles": {"eng": ["Zero-Turn Spring Check-Up Before Cutting Season – {city}", "Zero-Turn Hesitating to Engage? – {city} Tune-Up"]},
            "desc_intro": {"eng": "Sat all winter and now hesitates to engage the deck or hold RPM? Get it looked at before the grass outgrows your schedule."},
        },
    ],
    "tiller_repair": [
        {
            "slug": "tines_wont_turn",
            "titles": {"eng": ["Tiller Tines Won't Turn? – {city} Repair", "Tiller Runs, Tines Won't Spin – {city}"]},
            "desc_intro": {"eng": "Engine runs fine but the tines just sit there — that's almost always a slipping belt or worn drive clutch, an easy fix."},
        },
        {
            "slug": "transmission",
            "titles": {"eng": ["Tiller Transmission Won't Engage – {city}", "Tiller Won't Shift Into Gear? – {city} Repair"]},
            "desc_intro": {"eng": "If shifting into gear does nothing, the gearbox or shift linkage needs attention — not a reason to replace the whole tiller."},
        },
        {
            "slug": "before_buy_new",
            "titles": {"eng": ["Tiller Repair – Before You Buy New – {city}", "Don't Replace That Tiller – {city} Repair"]},
            "desc_intro": {"eng": "Most tillers we see need a belt, clutch, or carb cleaning — far cheaper than a brand-new machine."},
        },
        {
            "slug": "stalls_under_load",
            "titles": {"eng": ["Tiller Stalls the Moment Tines Hit the Ground – {city}", "Tiller Dies Under Load? – {city} Repair"]},
            "desc_intro": {"eng": "Runs fine at idle but dies under load in the dirt — that's a classic fuel delivery or carburetor issue."},
        },
        {
            "slug": "winter_start",
            "titles": {"eng": ["Tiller Won't Start After Sitting All Winter – {city}", "Tiller Sat All Winter? – {city} Repair"]},
            "desc_intro": {"eng": "Old fuel gums up the carburetor fast. If it won't fire after sitting in the shed, that's usually the culprit, not the engine itself."},
        },
        {
            "slug": "jammed",
            "titles": {"eng": ["Tiller Tines Jammed With Grass or Vines – {city}", "Tiller Wrapped Up and Stalled? – {city} Repair"]},
            "desc_intro": {"eng": "Wrapped-up grass, vines, or roots around the tine shaft will stall a tiller dead — a quick clear-out, and sometimes a straightened tine, is usually all it takes."},
        },
    ],
    "generator_repair": [
        {
            "slug": "wont_hold_load",
            "titles": {"eng": ["Generator Won't Hold a Load? – {city} Repair", "Generator Dies Under Load – {city} Repair"]},
            "desc_intro": {"eng": "Runs fine with nothing plugged in but drops or dies the moment you add a real load — that's a governor or carb issue we see all the time."},
        },
        {
            "slug": "wont_start_after_sitting",
            "titles": {"eng": ["Generator Won't Start After Sitting – {city}", "Generator Sat Unused? – {city} Repair"]},
            "desc_intro": {"eng": "Stale gas gums up the carburetor fast in a generator that only runs occasionally — a cleaning usually solves it."},
        },
        {
            "slug": "before_buy_new",
            "titles": {"eng": ["Generator Repair – Before You Buy New – {city}", "Don't Replace That Generator – {city} Repair"]},
            "desc_intro": {"eng": "A new generator is a real investment. Most of the ones we see just need a carb cleaning or fuel system flush."},
        },
        {
            "slug": "transfer_switch",
            "titles": {"eng": ["Generator Transfer Switch Not Working Right – {city}", "Power Not Switching Over? – {city} Generator Repair"]},
            "desc_intro": {"eng": "If power isn't switching over cleanly during an outage, the transfer switch itself may need service, not the generator."},
        },
        {
            "slug": "surging",
            "titles": {"eng": ["Generator Surging or RPM Fluctuating – {city}", "Generator Revving Up and Down? – {city} Repair"]},
            "desc_intro": {"eng": "An engine that revs up and down on its own usually has a carb or governor problem, easy to diagnose."},
        },
        {
            "slug": "fall_checkup",
            "titles": {"eng": ["Generator Fall Check-Up Before Storm Season – {city}", "Make Sure Your Generator Starts – {city} Check-Up"]},
            "desc_intro": {"eng": "Before the next outage hits, make sure yours actually starts and holds a load — most failures happen exactly when you need it most."},
        },
    ],
    "field_shredding": [
        {
            "slug": "show_ready",
            "titles": {"eng": ["Field Shredding – Get Your Land Show-Ready Before It Sells – {city}", "Selling Land? Shred It First – {city}"]},
            "desc_intro": {"eng": "Buyers judge land the second they pull up. Knock down the overgrowth so your property shows well instead of looking neglected."},
        },
        {
            "slug": "reset_pasture",
            "titles": {"eng": ["Field Shredding – Reset a Pasture That's Gotten Away From You – {city}", "Pasture Gone to Weeds? – {city} Shredding"]},
            "desc_intro": {"eng": "A field that's gone from grazing land to head-high weeds needs more than mowing — shredding knocks it back to usable ground."},
        },
        {
            "slug": "fire_risk",
            "titles": {"eng": ["Field Shredding – Cut Down Your Fire Risk This Summer – {city}", "Dry Overgrown Field? – {city} Shredding"]},
            "desc_intro": {"eng": "Dry, overgrown fields are fuel waiting for a spark. Shredding removes the dead growth before it becomes a real hazard."},
        },
        {
            "slug": "fence_line",
            "titles": {"eng": ["Field Shredding – Clear an Overgrown Fence Line or Right-of-Way – {city}", "Can't See Your Fence Line? – {city} Shredding"]},
            "desc_intro": {"eng": "Brush swallowing your fence line makes it impossible to spot damage or check your boundary. Open it back up."},
        },
        {
            "slug": "tick_habitat",
            "titles": {"eng": ["Field Shredding – Knock Down the Tick Habitat – {city}", "Tall Grass Breeding Ticks? – {city} Shredding"]},
            "desc_intro": {"eng": "Tall grass and brush are exactly where ticks thrive. Keeping fields shredded means fewer bites for you, your family, and your animals."},
        },
        {
            "slug": "overgrown_lot",
            "titles": {"eng": ["Field Shredding – Got an Overgrown Lot, Not Just Acreage? – {city}", "Small Overgrown Lot? – {city} Shredding"]},
            "desc_intro": {"eng": "A quarter-acre gone wild draws the same weeds, pests, and complaints as a big field. We shred small in-town lots too, not just ranches."},
        },
    ],
}


_locations_cache: Optional[list] = None


def get_locations(path='data/cities_data.json') -> list:
    global _locations_cache
    if _locations_cache is None:
        with open(path, 'r') as f:
            _locations_cache = json.load(f)
    return _locations_cache


def get_cities_for_equipment(equipment_type: str) -> list:
    """Cities a given equipment_type is offered in. Rental equipment is offered
    in every city in cities_data.json; service equipment_types (repairs,
    shredding) are restricted to whatever launch cities are listed under their
    "cities" key in _EQUIPMENT."""
    info = get_equipment().get(equipment_type, {})
    override = info.get('cities')
    if override:
        return override
    return [loc['city'] for loc in get_locations()]

def get_listing_title(equipment_type: str, city: str, language: str = "eng") -> str:
    """
    Generates a random title.
    Service equipment_types (repairs, shredding) are always task-based — there's
    no "classic rental style" that makes sense for them.
    Rental equipment: 80% chance = task-based (customer intent), 20% chance =
    classic style (your original varied templates).
    """
    equipment = get_equipment()[equipment_type]
    is_service = equipment.get('kind') == 'service'

    # Task-based titles — pick a random task variant for this equipment type
    if is_service or random.random() < 0.8:
        tasks = TASK_VARIANTS.get(equipment_type, [])
        if tasks:
            task = random.choice(tasks)
            return random.choice(task["titles"][language]).format(city=city)

    # 20% classic varied titles (your original style) — rental equipment only
    name = random.choice(equipment["names"][language])

    adjectives = {
        "eng": ["", "Reliable", "Affordable", "Well-Maintained", "Powerful", "Professional-Grade", "Local", "Heavy-Duty"],
        "spa": ["", "Confiable", "Económica", "Bien Mantenida", "Potente", "Grado Profesional", "Local", "Resistente"]
    }
    adj = random.choice(adjectives[language])
    adj = adj + " " if adj else ""

    templates_eng = [
        f"{adj}{name} Rental – {city}",
        f"{adj}{name} for Rent in {city}",
        f"Rent a {adj}{name} in {city}",
        f"{adj}{name} Available – {city} Area",
        f"Daily & Weekly {adj}{name} Rental ({city})",
        f"{city} – {adj}{name} Rental",
        f"Need a {name}? Rent in {city}",
        f"{adj}{name} Rental Serving {city}",
    ]

    templates_spa = [
        f"{adj}Renta de {name} – {city}",
        f"{adj}{name} en Renta – {city}",
        f"Alquiler de {adj}{name} en {city}",
        f"{adj}{name} Disponible – Zona de {city}",
        f"Renta Diaria y Semanal de {adj}{name} ({city})",
        f"{city} – {adj}Renta de {name}",
        f"¿Necesitas un {name}? Renta en {city}",
        f"{adj}Renta de {name} Sirviendo {city}",
    ]

    templates = templates_eng if language == "eng" else templates_spa
    return random.choice(templates)

# Shared across get_listing_description (rentals) and get_service_description
# (repairs/shredding) — same shop, same payment options, regardless of what's
# being listed.
ADDRESS_VARIANTS_ENG = [
    "Pickup Address:\n5510 Old Lorena Road\nLorena, Texas 76655",
    "Our Equipment Lot:\n5510 Old Lorena Road\nLorena, TX 76655",
    "Location:\n5510 Old Lorena Road, Lorena, Texas",
    "Based out of:\n5510 Old Lorena Road\nLorena, Texas 76655",
]
ADDRESS_VARIANTS_SPA = [
    "Dirección de Recogida:\n5510 Old Lorena Road\nLorena, Texas 76655",
    "Nuestro Lote:\n5510 Old Lorena Road\nLorena, TX 76655",
    "Ubicación:\n5510 Old Lorena Road, Lorena, Texas",
    "Operamos desde:\n5510 Old Lorena Road\nLorena, Texas 76655",
]

PAYMENT_VARIANTS_ENG = [
    "Payment accepted: Zelle • Venmo • Cash App • PayPal • Check • Cash",
    "We take: Zelle, Venmo, Cash App, PayPal, checks, or cash",
    "Multiple payment options: Zelle | Venmo | Cash App | PayPal | Check | Cash",
    "Easy payment via Zelle, Venmo, Cash App, PayPal, check, or cash",
]
PAYMENT_VARIANTS_SPA = [
    "Pagos aceptados: Zelle • Venmo • Cash App • PayPal • Cheque • Efectivo",
    "Aceptamos: Zelle, Venmo, Cash App, PayPal, cheque o efectivo",
    "Múltiples opciones: Zelle | Venmo | Cash App | PayPal | Cheque | Efectivo",
    "Pago fácil con Zelle, Venmo, Cash App, PayPal, cheque o efectivo",
]

CLOSING_VARIANTS_ENG = [
    "Affordable heavy equipment rental — reliable and hassle-free",
    "Get the job done right — clean, maintained equipment at great rates",
    "Local rental you can count on — fast and simple",
    "Quality machines, fair prices, easy process",
    "Message anytime for questions or to book!",
    "Call or text today — quick response guaranteed",
]
CLOSING_VARIANTS_SPA = [
    "Renta de equipo pesado económica — confiable y sin complicaciones",
    "Termina el trabajo bien — equipo limpio y mantenido a buen precio",
    "Renta local en la que puedes confiar — rápida y sencilla",
    "Maquinaria de calidad, precios justos, proceso fácil",
    "¡Manda mensaje cuando quieras para preguntas o reservar!",
    "Llama o escribe hoy — respuesta rápida garantizada",
]

# Closing variants specific to repair/shredding services (no "rental" framing)
SERVICE_CLOSING_VARIANTS_ENG = [
    "Local, family-owned — fast turnaround and fair prices",
    "Quality work, fair prices, easy process",
    "Message anytime for questions or to schedule!",
    "Call or text today — quick response guaranteed",
    "We stand behind our work — that's why the diagnostic is free",
]


def get_listing_description(language: str, blurb: str, daily_price: str, delivery_cost: float, location: str, task_intro: Optional[str] = None):
    """
    Maximum natural variation with shuffled sections, multiple phrasings, and optional extras.
    """
    # Optional opening hooks (sometimes used, sometimes not)
    hooks_eng = [
        None,
        "Great for construction, landscaping, or any heavy work!",
        "Clean, serviced, and ready to go.",
        "Message or call for quick booking.",
        "Flexible rental terms to fit your schedule.",
        "Family-owned local rental service.",
    ]
    hooks_spa = [
        None,
        "¡Ideal para construcción, jardinería o cualquier trabajo pesado!",
        "Limpio, revisado y listo para usar.",
        "Manda mensaje o llama para reservar rápido.",
        "Términos de renta flexibles según tu horario.",
        "Servicio de renta local familiar.",
    ]

    intro_variants_eng = [
        f"{blurb}\n\nCurrently available for rent in {location}.",
        f"{blurb}\n\nServing {location} and nearby areas.",
        f"{blurb}\n\nPerfect for jobs in {location}.",
        f"Renting out: {blurb.lower()}\n\nAvailable now in {location}.",
        f"{blurb}\n\nBook today for delivery or pickup in {location}.",
    ]
    intro_variants_spa = [
        f"{blurb}\n\nDisponible actualmente para renta en {location}.",
        f"{blurb}\n\nSirviendo {location} y zonas cercanas.",
        f"{blurb}\n\nPerfecto para trabajos en {location}.",
        f"En renta: {blurb.lower()}\n\nDisponible ahora en {location}.",
        f"{blurb}\n\nReserva hoy con entrega o recogida en {location}.",
    ]

    pricing_variants_eng = [
        f"Daily rate: ${float(daily_price):.2f} (full 24 hours) — ask about multi-day rates",
        f"Rates: ${float(daily_price):.2f}/day — ask us about multi-day pricing",
        f"${float(daily_price):.2f} per day. Need it longer? Ask about multi-day rates.",
        f"Daily: ${float(daily_price):.2f} | Ask about extended rental pricing",
        f"Rent by the day: ${float(daily_price):.2f} — multi-day rates available, just ask",
    ]
    pricing_variants_spa = [
        f"Tarifa diaria: ${float(daily_price):.2f} (24 horas completas) — pregunta por tarifas de varios días",
        f"Precio: ${float(daily_price):.2f}/día — pregunta por descuentos para rentas largas",
        f"${float(daily_price):.2f} por día. ¿Necesitas más tiempo? Pregunta por tarifas extendidas.",
        f"Diario: ${float(daily_price):.2f} | Consulta precios para rentas largas",
        f"Renta por día: ${float(daily_price):.2f} — tarifas de varios días disponibles, solo pregunta",
    ]

    address_variants_eng = ADDRESS_VARIANTS_ENG
    address_variants_spa = ADDRESS_VARIANTS_SPA

    delivery_variants_eng = [
        f"Delivery to {location} available for ${float(delivery_cost):.2f} — includes drop-off, pickup, and a full tank of fuel",
        f"We can deliver to {location} for ${float(delivery_cost):.2f} (fuel, delivery & pickup included)",
        f"Optional transport: ${float(delivery_cost):.2f} to {location} with free fuel fill",
        f"Need it delivered? ${float(delivery_cost):.2f} covers delivery, pickup, and fuel to {location}",
        f"Delivery service to {location}: ${float(delivery_cost):.2f} (includes fuel + round trip)",
    ]
    delivery_variants_spa = [
        f"Entrega a {location} por ${float(delivery_cost):.2f} — incluye entrega, recogida y tanque lleno de combustible",
        f"Podemos entregar en {location} por ${float(delivery_cost):.2f} (combustible, entrega y recogida incluidos)",
        f"Transporte opcional: ${float(delivery_cost):.2f} a {location} con tanque lleno gratis",
        f"¿Necesitas entrega? ${float(delivery_cost):.2f} cubre ida, vuelta y combustible a {location}",
        f"Servicio de entrega a {location}: ${float(delivery_cost):.2f} (incluye combustible + viaje redondo)",
    ]

    payment_variants_eng = PAYMENT_VARIANTS_ENG
    payment_variants_spa = PAYMENT_VARIANTS_SPA

    closing_variants_eng = CLOSING_VARIANTS_ENG
    closing_variants_spa = CLOSING_VARIANTS_SPA

    # Build the list of sections
    sections = [
        random.choice(intro_variants_eng if language == "eng" else intro_variants_spa),
        random.choice(pricing_variants_eng if language == "eng" else pricing_variants_spa),
        random.choice(address_variants_eng if language == "eng" else address_variants_spa),
        random.choice(delivery_variants_eng if language == "eng" else delivery_variants_spa),
        random.choice(payment_variants_eng if language == "eng" else payment_variants_spa),
        random.choice(closing_variants_eng if language == "eng" else closing_variants_spa),
    ]

    # task_intro pins the opening; fall back to random hook
    if task_intro:
        sections.insert(0, task_intro)
    else:
        hook = random.choice(hooks_eng if language == "eng" else hooks_spa)
        if hook and random.random() < 0.7:
            sections.insert(0, hook)

    # Shuffle middle parts for different flow
    random.shuffle(sections[1:-2])

    return "\n\n".join(sections)


def get_service_description(blurb: str, location: str, task_intro: Optional[str] = None) -> str:
    """
    Description builder for repair/shredding service listings — no rental
    pricing tiers or delivery-fee section, since these are flat/quoted
    services rather than a per-day machine rental. English only (services
    aren't in Spanish rotation yet). Reuses the same address/payment/closing
    pools as get_listing_description — same shop, same terms.
    """
    intro_variants = [
        f"{blurb}\n\nServing {location} and surrounding areas.",
        f"{blurb}\n\nLocal to {location} — message or call to schedule.",
        f"{blurb}\n\nBased near {location}.",
    ]

    sections = [
        random.choice(intro_variants),
        random.choice(ADDRESS_VARIANTS_ENG),
        random.choice(PAYMENT_VARIANTS_ENG),
        random.choice(SERVICE_CLOSING_VARIANTS_ENG),
    ]

    if task_intro:
        sections.insert(0, task_intro)

    # Shuffle middle parts for different flow (keep opening and closing pinned)
    random.shuffle(sections[1:-1])

    return "\n\n".join(sections)


def get_listings(output_directory: str = "./images/output/", skip_slots: Optional[set] = None, generate_images: bool = True) -> Generator[ListingData, None, None]:
    equipment = get_equipment()
    loc_by_city = {loc['city']: loc for loc in get_locations()}
    for item, info in equipment.items():
        is_service = info.get('kind') == 'service'
        tasks = TASK_VARIANTS.get(item, [])
        for city in get_cities_for_equipment(item):
            location = loc_by_city.get(city)
            if not location:
                continue
            listed_location = f"{city}, TX"
            for task in tasks:
                for lang in ['eng']:
                    if skip_slots and f"{item}_{city}_{lang}_{task['slug']}" in skip_slots:
                        continue
                    images = []
                    if generate_images:
                        if is_service:
                            for _ in range(4):
                                card = generate_text_card_image(info['image_text'])
                                images.append(generate_random_controlled_image(input_image=card, output_directory=output_directory))
                        else:
                            base_image_dir = f"./images/{info['model']}"
                            for image in random_images_from_directory(base_image_dir):
                                images.append(generate_random_controlled_image(input_image=image, output_directory=output_directory))
                    title = random.choice(task['titles'][lang]).format(city=city)
                    if is_service:
                        price = info['price']
                        description = get_service_description(
                            blurb=info['blurb'][lang],
                            location=listed_location,
                            task_intro=task['desc_intro'][lang],
                        )
                    else:
                        price = info['prices']['daily']
                        description = get_listing_description(
                            language=lang,
                            blurb=info['blurb'][lang],
                            daily_price=price,
                            delivery_cost=location.get('estimated_cost'),
                            location=listed_location,
                            task_intro=task['desc_intro'][lang],
                        )
                    yield ListingData(
                        images=["\n".join(images)],
                        price=price,
                        description=description,
                        location=listed_location,
                        title=title,
                        category='Miscellaneous',
                        equipment_type=item,
                        lang=lang,
                        task_slug=str(task['slug']),
                    )


# Text-card backgrounds for service listings (repairs, shredding) — no real
# product photo exists, so a plain colored card carries the short label text
# instead. Palette alternates light/dark so the phone-banner (always
# semi-transparent orange, drawn below) stays readable on either.
_TEXT_CARD_PALETTES = [
    ((255, 255, 255), (20, 20, 20)),    # white card, near-black text
    ((17, 34, 51), (255, 255, 255)),    # dark navy card, white text
    ((21, 71, 42), (255, 255, 255)),    # forest green card, white text
    ((40, 40, 40), (255, 255, 255)),    # charcoal card, white text
]


def generate_text_card_image(text: str, size=(1200, 900)) -> Image.Image:
    """Builds a plain background card with big, bold, centered text — the base
    "photo" for service listings (repairs, shredding) that have no real
    equipment to photograph. Fed through generate_random_controlled_image()
    exactly like a real photo, so it gets the same rotation/crop/noise/phone-
    banner treatment and a unique hash per listing (avoids FB flagging the
    handful of listings under one service as duplicates of each other)."""
    if os.name == 'posix':
        font_path = '/Library/Fonts/Arial Bold.ttf'
    else:
        font_path = 'C:\\Windows\\Fonts\\arialbd.ttf'

    bg_color, text_color = random.choice(_TEXT_CARD_PALETTES)
    width, height = size
    image = Image.new('RGB', size, bg_color)
    draw = ImageDraw.Draw(image)

    # Shrink font size until the text fits within ~85% of the card width —
    # keeps it big and thumbnail-readable without ever overflowing the card.
    max_width = int(width * 0.85)
    font_size = 180
    font = ImageFont.truetype(font_path, font_size)
    while font_size > 20:
        font = ImageFont.truetype(font_path, font_size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            break
        font_size -= 5

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((width - text_w) / 2 - bbox[0], (height - text_h) / 2 - bbox[1]),
        text, fill=text_color, font=font,
    )
    return image


def generate_random_controlled_image(input_image="images/basic.jpeg",
                                     output_directory: str = "./images/output/"):
    """input_image is either a file path (real equipment photos) or a PIL
    Image already in memory (generated text cards for service listings)."""
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    if os.name == 'posix':
        font_path = '/Library/Fonts/Arial Bold.ttf'
    else:
        font_path = 'C:\\Windows\\Fonts\\arialbd.ttf'

    photo = input_image.convert('RGB') if isinstance(input_image, Image.Image) else Image.open(input_image).convert('RGB')

    # --- Distortion 1: slight random rotation ---
    rotation_angle = random.uniform(1, 5) * random.choice([-1, 1])
    photo = photo.rotate(rotation_angle, expand=True, fillcolor='white')

    # --- Distortion 2: random crop (5-10% from edges) ---
    width, height = photo.size
    crop_pct = random.uniform(0.05, 0.10)
    lc = int(width * crop_pct)
    tc = int(height * crop_pct)
    photo = photo.crop((lc, tc, width - lc, height - tc))

    # --- Distortion 3: brightness + contrast variation ---
    photo = ImageEnhance.Brightness(photo).enhance(random.uniform(0.85, 1.15))
    photo = ImageEnhance.Contrast(photo).enhance(random.uniform(0.85, 1.15))
    photo = ImageEnhance.Color(photo).enhance(random.uniform(0.85, 1.15))

    # --- Distortion 4: subtle pixel noise ---
    arr = np.array(photo, dtype=np.int16)
    noise = np.random.randint(-12, 13, arr.shape, dtype=np.int16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    photo = Image.fromarray(arr)

    width, height = photo.size
    background = Image.new('RGB', (width, height), 'white')
    background.paste(photo, (0, 0))

    # --- Phone number overlay ---
    phone_number = "254.655.3339"
    font_size = random.randint(40, 50)
    font = ImageFont.truetype(font_path, font_size)

    bbox = font.getbbox(phone_number)
    text_width  = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Pad the banner slightly larger than the text
    pad_x, pad_y = 12, 8
    banner_w = text_width  + pad_x * 2
    banner_h = text_height + pad_y * 2

    # Horizontal: centered with ±2% random jitter
    jitter_x = int(width * 0.02)
    banner_x = (width - banner_w) // 2 + random.randint(-jitter_x, jitter_x)

    draw = ImageDraw.Draw(background)

    for position in ['top', 'bottom']:
        # Vertical: hug the edge with 8-18 px margin
        edge_margin = random.randint(8, 18)
        if position == 'top':
            banner_y = edge_margin
        else:
            banner_y = height - banner_h - edge_margin

        # Semi-transparent orange banner
        red   = 255
        green = random.randint(100, 200)
        blue  = random.randint(0, 40)
        alpha = random.randint(200, 245)
        overlay = Image.new('RGBA', (banner_w, banner_h), (red, green, blue, alpha))
        background.paste(overlay, (banner_x, banner_y), overlay)

        # Text inside banner
        text_x = banner_x + pad_x
        text_y = banner_y + pad_y
        draw.text((text_x, text_y), phone_number, fill='black', font=font)

    hash_name = hash_image(background)
    image_path = os.path.join(os.path.abspath(output_directory), f"{hash_name}.jpeg")
    background.save(image_path, quality=random.randint(82, 95))
    return image_path

def random_images_from_directory(path: str, number: int = 9) -> list[str]:
    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
    images = [f for f in files if any(f.lower().endswith(ext) for ext in image_extensions)]

    # Separate original equipment shots (numeric names) from YouTube-extracted frames.
    # Original photos are guaranteed to show the equipment; always use one as the lead.
    originals = [f for f in images if f.split('.')[0].isdigit()]

    selected = []
    if originals:
        selected.append(random.choice(originals))   # lead image = equipment shot
        pool = [f for f in images if f != selected[0]]
    else:
        pool = images

    remaining = min(number - len(selected), len(pool))
    selected += random.sample(pool, remaining)

    return [os.path.join(path, img) for img in selected]
