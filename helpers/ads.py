import os
import json
import hashlib
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from helpers.listing_helper import ListingData
from typing import Generator, Optional, Tuple

_content_pool: Optional[dict] = None


def _load_pool(path: str = "data/generated_content.json") -> dict:
    global _content_pool
    if _content_pool is None:
        if os.path.exists(path):
            with open(path) as f:
                _content_pool = json.load(f)
        else:
            _content_pool = {}
    return _content_pool


def _pick_from_pool(equipment_type: str, city: str, language: str = "eng") -> Tuple[Optional[str], Optional[str]]:
    """Return (title, description) from pre-generated pool, or (None, None) if slot is missing."""
    pool = _load_pool()
    slot = f"{equipment_type}_{city}_{language}"
    variants = pool.get(slot, [])
    if not variants:
        return None, None
    v = random.choice(variants)
    return v.get("title"), v.get("description")


def hash_image(image):
    # Convert image to bytes. 'tobytes()' gives you the raw pixel data.
    image_bytes = image.tobytes()

    # Hash the bytes. Here we're using MD5 for simplicity, but you could use SHA-1, SHA-256, etc.
    hash_obj = hashlib.md5(image_bytes)

    # Get the hexadecimal representation of the hash
    hash_digest = hash_obj.hexdigest()

    # Shorten to 16 characters by taking the first 16 of the hex digest
    return hash_digest[:16]

def get_equipment() -> dict:
    equipment = {
        "mini-ex": {
            "model": "kx71",
            "names": {
                "eng": ["Mini-Excavator"],
                "spa": ["Excavadora Compacta"]
            },
            "prices": {"daily": 200,
                       "weekly": 750,
                       "monthly": 2250},
            "blurb": {"eng": "KX71-3; 6,300#; 12” and 24” buckets",
                      "spa": "KX71-3; 6,300#; 12” y 24” cucharas"},
        },
        "trackloader": {
            "model": "svl75",
            "names": {
                "eng": [
                    "Skidsteer",
                ],
                "spa": [
                    "Cargadora compacta"]},
            "prices": {"daily": 280,
                       "weekly": 1000,
                       "monthly": 3000},
            "blurb": {"eng": "SVL75-2; 9,100#, 75 HP; Toothed & Smooth buckets, Standard Flow Attachments",
                      "spa": "SVL75-2; 9,100#, 75 HP; Cucharas dentadas y lisas, accesorios de flujo estándar"},
        },
    }
    return equipment

# Task-based title templates – English and Spanish
TASK_TEMPLATES_MINI_EX = {
    "eng": [
        "Mini Excavator Rental – Drainage & Trenching – {city}",     # 54 chars
        "French Drain Install? Mini Ex Rental – {city}",             # 47
        "Trenching for Irrigation/Utilities? Mini Excavator",        # 51
        "Mini Ex Rental for Yard Grading & Footings – {city}",       # 53
        "Compact Excavator for Pond/Landscaping – {city}",           # 49
        "Uneven Yard Leveling? Mini Ex Ready – {city}",              # 47
        "Site Prep for Patio/Wall? Mini Excavator – {city}",         # 51
        "Tree Holes or Sod Removal? Mini Ex Rental – {city}",         # 52
        "Backfilling Trenches? Mini Excavator Available – {city}",   # 56
        "Mini Ex for Foundation Redirect Drainage – {city}",         # 51
    ],
    "spa": [
        "Renta Mini Excavadora – Drenaje y Zanjas – {city}",         # ~50
        "¿Dren Francés? Mini Ex Disponible – {city}",                # ~43
        "Zanjas para Riego/Utilidades? Mini Excavadora",             # ~47
        "Renta Mini Ex para Nivelar Patio – {city}",                 # ~43
        "Excavadora Compacta para Estanque/Paisaje – {city}",        # ~52
        "¿Patio Desnivelado? Mini Ex Lista – {city}",                # ~43
        "Prep Terreno Terraza/Muro? Mini Ex – {city}",               # ~45
        "Rellenar Zanjas? Mini Excavadora – {city}",                 # ~43
        "Mini Ex para Drenaje Cimientos – {city}",                   # ~43
    ]
}

TASK_TEMPLATES_TRACK_LOADER = {
    "eng": [
        "Track Loader Rental – Driveway Grading – {city}",           # 49
        "Muddy Gravel Driveway Fix? Track Loader – {city}",          # 50
        "Spreading Topsoil/Gravel? Track Loader Rental – {city}",    # 55
        "Moving Dirt/Debris? Heavy Track Loader – {city}",           # 48
        "Backfilling Trenches? Track Loader Rental – {city}",        # 51
        "Loading Pallets w/ Forks? Track Loader – {city}",           # 48
        "Yard Prep for Sod/Seed? Track Loader – {city}",             # 47
        "Clearing & Leveling Site? Track Loader – {city}",           # 49
        "Gravel Driveway Base Work? Track Loader Rental – {city}",   # 56
        "Material Handling w/ Forks? Track Loader – {city}",         # 50
    ],
    "spa": [
        "Renta Cargadora Orugas – Nivelar Entrada – {city}",         # ~50
        "¿Entrada Grava Baches? Cargadora Orugas – {city}",          # ~49
        "Esparcir Tierra/Grava? Renta Cargadora – {city}",           # ~48
        "Mover Tierra/Escombros? Cargadora Pesada – {city}",         # ~51
        "Rellenar Zanjas? Renta Cargadora Orugas – {city}",          # ~50
        "Cargar Palets c/ Horquillas? Cargadora – {city}",           # ~48
        "Prep Patio para Césped? Cargadora Lista – {city}",          # ~48
        "Limpiar y Nivelar Terreno? Cargadora – {city}",             # ~46
        "Base Entrada Grava? Renta Cargadora – {city}",              # ~46
        "Manejo Materiales c/ Horquillas? Cargadora – {city}",       # ~52
    ]
}

def get_locations(path='data/cities_data.json'):
    with open(path, 'r') as cities_file:
        return json.load(cities_file)

profiles = ["100000068273898"]

def get_listing_title(equipment_type: str, city: str, language: str = "eng") -> str:
    """
    Generates a random title.
    80% chance = task-based (customer intent), 20% chance = classic style (your original varied templates).
    """
    # 80% task-based titles
    if random.random() < 0.8:
        if equipment_type == "mini-ex":
            templates = TASK_TEMPLATES_MINI_EX[language]
        elif equipment_type == "trackloader":
            templates = TASK_TEMPLATES_TRACK_LOADER[language]
        else:
            templates = TASK_TEMPLATES_MINI_EX[language]  # fallback
        return random.choice(templates).format(city=city)

    # 20% classic varied titles (your original style)
    equipment = get_equipment()[equipment_type]
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

def get_listing_description(language: str, blurb: str, title: str, daily_price: str, delivery_cost: float, location: str):
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

    address_variants_eng = [
        "Pickup Address:\n5510 Old Lorena Road\nLorena, Texas 76655",
        "Our Equipment Lot:\n5510 Old Lorena Road\nLorena, TX 76655",
        "Location:\n5510 Old Lorena Road, Lorena, Texas",
        "Based out of:\n5510 Old Lorena Road\nLorena, Texas 76655",
    ]
    address_variants_spa = [
        "Dirección de Recogida:\n5510 Old Lorena Road\nLorena, Texas 76655",
        "Nuestro Lote:\n5510 Old Lorena Road\nLorena, TX 76655",
        "Ubicación:\n5510 Old Lorena Road, Lorena, Texas",
        "Operamos desde:\n5510 Old Lorena Road\nLorena, Texas 76655",
    ]

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

    payment_variants_eng = [
        "Payment accepted: Zelle • Venmo • Cash App • PayPal • Check • Cash",
        "We take: Zelle, Venmo, Cash App, PayPal, checks, or cash",
        "Multiple payment options: Zelle | Venmo | Cash App | PayPal | Check | Cash",
        "Easy payment via Zelle, Venmo, Cash App, PayPal, check, or cash",
    ]
    payment_variants_spa = [
        "Pagos aceptados: Zelle • Venmo • Cash App • PayPal • Cheque • Efectivo",
        "Aceptamos: Zelle, Venmo, Cash App, PayPal, cheque o efectivo",
        "Múltiples opciones: Zelle | Venmo | Cash App | PayPal | Cheque | Efectivo",
        "Pago fácil con Zelle, Venmo, Cash App, PayPal, cheque o efectivo",
    ]

    closing_variants_eng = [
        "Affordable heavy equipment rental — reliable and hassle-free",
        "Get the job done right — clean, maintained equipment at great rates",
        "Local rental you can count on — fast and simple",
        "Quality machines, fair prices, easy process",
        "Message anytime for questions or to book!",
        "Call or text today — quick response guaranteed",
    ]
    closing_variants_spa = [
        "Renta de equipo pesado económica — confiable y sin complicaciones",
        "Termina el trabajo bien — equipo limpio y mantenido a buen precio",
        "Renta local en la que puedes confiar — rápida y sencilla",
        "Maquinaria de calidad, precios justos, proceso fácil",
        "¡Manda mensaje cuando quieras para preguntas o reservar!",
        "Llama o escribe hoy — respuesta rápida garantizada",
    ]

    # Build the list of sections
    sections = [
        random.choice(intro_variants_eng if language == "eng" else intro_variants_spa),
        random.choice(pricing_variants_eng if language == "eng" else pricing_variants_spa),
        random.choice(address_variants_eng if language == "eng" else address_variants_spa),
        random.choice(delivery_variants_eng if language == "eng" else delivery_variants_spa),
        random.choice(payment_variants_eng if language == "eng" else payment_variants_spa),
        random.choice(closing_variants_eng if language == "eng" else closing_variants_spa),
    ]

    # Optional hook at the very top
    hook = random.choice(hooks_eng if language == "eng" else hooks_spa)
    if hook and random.random() < 0.7:  # 70% chance to include a hook
        sections.insert(0, hook)

    # Shuffle middle parts for different flow
    random.shuffle(sections[1:-2])

    return "\n\n".join(sections)

def get_listings(output_directory: str = "./images/output/") -> Generator[ListingData, None, None]:
    equipment = get_equipment()
    for item in equipment:
        base_image_dir = f"./images/{equipment[item]['model']}"
        loc = get_locations()
        for location in loc:
            for lang in ['eng']:
                images = []
                for image in random_images_from_directory(base_image_dir):
                    images.append(generate_random_controlled_image(input_image=image))
                daily_price = equipment[item]['prices']['daily']
                city = location.get('city')
                listed_location = f"{city}, Texas"
                delivery_cost = location.get('estimated_cost')

                title, description = _pick_from_pool(item, city, lang)
                if title is None:
                    title = get_listing_title(equipment_type=item, city=listed_location, language=lang)
                if description is None:
                    description = get_listing_description(
                        language=lang,
                        blurb=equipment[item]['blurb'][lang],
                        title=title,
                        daily_price=daily_price,
                        delivery_cost=delivery_cost,
                        location=listed_location,
                    )

                yield ListingData(
                    images=["\n".join(images)],
                    price=daily_price,
                    description=description,
                    location=listed_location,
                    title=title,
                    category='Miscellaneous',
                    equipment_type=item,
                    lang=lang,
                )


def generate_random_controlled_image(input_image: str = "images/basic.jpeg",
                                     output_directory: str = "./images/output/"):
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    if os.name == 'posix':
        font_path = '/Library/Fonts/Arial Bold.ttf'
    else:
        font_path = 'C:\\Windows\\Fonts\\arialbd.ttf'

    photo = Image.open(input_image).convert('RGB')

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

def random_images_from_directory(path, number=9):
    # List all files in the directory
    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]

    # Filter for image files (you can extend this list to include more formats)
    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
    images = [f for f in files if any(f.lower().endswith(ext) for ext in image_extensions)]

    # If we have fewer images than requested, we'll return all of them
    if len(images) < number:
        number = len(images)

    # Randomly select 'number' images
    selected_images = random.sample(images, number)

    # Return full paths to the selected images
    return [os.path.join(path, img) for img in selected_images]
