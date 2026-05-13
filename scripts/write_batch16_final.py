import json

def make_mini(city, cost):
    return [
        {"title": f"Mini Excavator Rental {city} TX — $200/Day Delivered", "description": f"Compact excavator for rent near {city} TX. Delivered to your job site.\n\nGreat for trenching, grading, utility lines, stump removal, and land clearing.\n\n$200/day. Delivery to {city}: ${cost}.\n\n📍 5510 Old Lorena Road, Lorena TX 76655\n📞 254.655.3339\n💳 Zelle · Venmo · Cash App · PayPal · Check · Cash\n\nAsk about multi-day rates."},
        {"title": f"Excavator for Rent Near {city} TX — Delivery Available", "description": f"Kubota compact excavator available for {city} TX. We haul it to your site.\n\n$200/day + ${cost} delivery to {city}.\n\n📞 254.655.3339 | Lorena TX 76655\n💳 Zelle · Venmo · Cash App · PayPal · Check · Cash\n\nAsk about multi-day rates."},
        {"title": f"{city} TX Excavator Rental — Trenching, Grading & Land Clearing", "description": f"Compact excavator rental in {city} TX. Handles rural lots, fence lines, utility work, and construction prep.\n\n$200/day. Delivery: ${cost}.\n\n📍 5510 Old Lorena Rd, Lorena TX | 📞 254.655.3339\n💳 Zelle · Venmo · Cash App · PayPal · Check · Cash\n\nAsk about multi-day rates."},
        {"title": f"Rent a Mini-Ex in {city} TX — $200/Day", "description": f"Kubota compact excavator rental serving {city} TX. Delivered and picked up from your property.\n\nRate: $200/day. Delivery: ${cost}.\n\n254.655.3339 | 5510 Old Lorena Rd, Lorena TX\n💳 Zelle · Venmo · Cash App · PayPal · Check · Cash\n\nAsk about multi-day rates."},
        {"title": f"Mini Excavator — {city} TX — $200/Day Delivered to Site", "description": f"Compact excavator available for {city} TX and surrounding areas.\n\n$200/day + ${cost} delivery.\n\n📞 254.655.3339 | 📍 Lorena TX 76655\n💳 Zelle · Venmo · Cash App · PayPal · Check · Cash\n\nAsk about multi-day rates."}
    ]

def make_track(city, cost):
    return [
        {"title": f"Track Loader Rental {city} TX — $300/Day Delivered", "description": f"Kubota SVL75-2 compact track loader for rent near {city} TX.\n\nIdeal for grading, clearing, loading, and heavy site work.\n\n$300/day. Delivery to {city}: ${cost}.\n\n📍 5510 Old Lorena Road, Lorena TX 76655\n📞 254.655.3339\n💳 Zelle · Venmo · Cash App · PayPal · Check · Cash\n\nAsk about multi-day rates."},
        {"title": f"Skid Steer Track Loader Near {city} TX — Rent by the Day", "description": f"Kubota SVL75-2 track loader rental in {city} TX. More traction than wheeled skid steers on rough terrain.\n\n$300/day. {city} delivery: ${cost}.\n\n📍 Lorena TX 76655 | 📞 254.655.3339\n💳 Zelle · Venmo · Cash App · PayPal · Check · Cash\n\nAsk about multi-day rates."},
        {"title": f"Compact Track Loader for Rent — {city} TX — $300/Day", "description": f"Need a track loader near {city} TX? We deliver the Kubota SVL75-2 to you.\n\n$300/day + ${cost} delivery to {city}.\n\n254.655.3339 | Lorena TX 76655\n💳 Zelle · Venmo · Cash App · PayPal · Check · Cash\n\nAsk about multi-day rates."},
        {"title": f"{city} TX Track Loader Rental — Kubota SVL75-2", "description": f"SVL75-2 track loader rental near {city} TX. Handles tough terrain and heavy loads.\n\nDaily rate: $300. Delivery: ${cost}.\n\n📍 5510 Old Lorena Rd, Lorena TX | 📞 254.655.3339\n💳 Zelle · Venmo · Cash App · PayPal · Check · Cash\n\nAsk about multi-day rates."},
        {"title": f"SVL75-2 Track Loader — {city} TX — Delivered to Site", "description": f"Compact track loader rental serving {city} TX. Delivered and picked up on your schedule.\n\n$300/day. Delivery: ${cost}.\n\n📞 254.655.3339 | 📍 Lorena TX 76655\n💳 Zelle · Venmo · Cash App · PayPal · Check · Cash\n\nAsk about multi-day rates."}
    ]

cities = [
    ("Levita", "254.20"),
    ("South Elm", "254.60"),
    ("Ater", "254.60"),
    ("Winslow", "254.60"),
    ("Harker Heights", "255.00"),
    ("Hillsboro", "255.80"),
    ("Bynum", "257.00"),
    ("Coolidge", "257.40"),
    ("Lakewood Harbor", "258.60"),
    ("Prairie Dell", "259.00"),
    ("Highbank", "259.40"),
    ("Vaughan", "260.20"),
    ("Baileyville", "260.20"),
    ("Buckholts", "261.00"),
    ("Coymack", "261.40"),
    ("Turnersville", "261.40"),
    ("Val Verde", "261.40"),
    ("Alto Springs", "261.80"),
    ("Thelma", "261.80"),
    ("Echols", "261.80"),
    ("Pancake", "262.60"),
    ("Munger", "262.60"),
    ("Mason Crossing", "263.40"),
    ("Groesbeck", "263.40"),
    ("South Purmela", "264.60"),
    ("Eloise", "265.40"),
    ("Kosse", "265.40"),
    ("Dawson", "265.40"),
    ("Marak", "265.80"),
    ("Bartlett", "266.20"),
    ("Jonesboro", "266.60"),
    ("Irene", "266.60"),
    ("Whitney", "267.40"),
    ("Pidcoke", "268.20"),
    ("Coit", "268.60"),
    ("Purmela", "268.60"),
    ("Burlington", "269.00"),
    ("Vilas", "269.80"),
    ("Meridian", "269.80"),
    ("Pelham", "269.80"),
    ("Datura", "271.00"),
    ("Jackson Crossing", "271.80"),
    ("Bremond", "273.40"),
    ("Pettibone", "273.40"),
    ("Saint Elijah Village", "274.20"),
    ("Splawn", "274.60"),
    ("Bosque", "274.60"),
    ("Donahoe", "274.60"),
]

batch = {}
for city, cost in cities:
    batch[f"mini-ex_{city}_eng"] = make_mini(city, cost)
    batch[f"trackloader_{city}_eng"] = make_track(city, cost)

with open("data/batch_temp.json", "w") as f:
    json.dump(batch, f, indent=2)
print(f"Written {len(batch)} slots to batch_temp.json")
