"""
Kenya Administrative Location Hierarchy (47 Counties, Sub-Counties, Wards)
Used for Artisan Origin Badges, Shop Location Registration, and Order Shipping/Pickup.
"""

KENYA_COUNTIES = [
    "Mombasa", "Kwale", "Kilifi", "Tana River", "Lamu", "Taita–Taveta", "Garissa",
    "Wajir", "Mandera", "Marsabit", "Isiolo", "Meru", "Tharaka-Nithi", "Embu",
    "Kitui", "Machakos", "Makueni", "Nyandarua", "Nyeri", "Kirinyaga", "Murang'a",
    "Kiambu", "Turkana", "West Pokot", "Samburu", "Trans-Nzoia", "Uasin Gishu",
    "Elgeyo-Marakwet", "Nandi", "Baringo", "Laikipia", "Nakuru", "Narok", "Kajiado",
    "Kericho", "Bomet", "Kakamega", "Vihiga", "Bungoma", "Busia", "Siaya",
    "Kisumu", "Homa Bay", "Migori", "Kisii", "Nyamira", "Nairobi"
]

KENYA_SUB_COUNTIES = {
    "Nairobi": ["Westlands", "Dagoretti North", "Dagoretti South", "Lang'ata", "Kibra", "Ruaraka", "Kasarani", "Embakasi South", "Embakasi North", "Embakasi Central", "Embakasi East", "Embakasi West", "Makadara", "Kamukunji", "Starehe", "Mathare"],
    "Mombasa": ["Changamwe", "Jomvu", "Kisauni", "Nyali", "Likoni", "Mvita"],
    "Machakos": ["Machakos Town", "Mavoko", "Mwala", "Yatta", "Kangundo", "Matungulu", "Kathiani", "Masinga"],
    "Kiambu": ["Githunguri", "Kiambu Town", "Ruiru", "Thika Town", "Juja", "Kikuyu", "Kabete", "Limuru", "Lari", "Gatundu South", "Gatundu North", "Karuri"],
    "Nakuru": ["Nakuru East", "Nakuru West", "Naivasha", "Gilgil", "Kuresoi South", "Kuresoi North", "Molo", "Njoro", "Rongai", "Subukia", "Bahati"],
    "Kisumu": ["Kisumu Central", "Kisumu East", "Kisumu West", "Muhoroni", "Nyando", "Nyakach", "Seme"],
    "Kilifi": ["Kilifi North", "Kilifi South", "Kaloleni", "Rabai", "Ganze", "Malindi", "Magarini"],
    "Lamu": ["Lamu East", "Lamu West"],
    "Kisii": ["Kitutu Chache North", "Kitutu Chache South", "Nyaribari Chache", "Nyaribari Masaba", "Bommachoge Borabu", "Bommachoge Chache", "Bobasi", "South Mugirango", "Bonchari"],
}

KENYA_WARDS = {
    "Machakos Town": ["Machakos Central", "Muvuti/Kiima-Kimwe", "Mutituni", "Kalama", "Kua", "Kimutwa"],
    "Mwala": ["Mwala", "Makaveti", "Kibauni", "Masii", "Kathama", "Vyulya"],
    "Westlands": ["Kitisuru", "Parklands/Highridge", "Karura", "Kangemi", "Mountain View"],
    "Kibra": ["Laini Saba", "Lindi", "Makina", "Woodley/Kenyatta Golf Course", "Sarang'ombe"],
    "Nyali": ["Frere Town", "Ziwa La Ng'ombe", "Mkomani", "Kongowea", "Kaduruni"],
    "Naivasha": ["Naivasha Town", "Hell's Gate", "Olkaria", "Mai Mahiu", "Maeila"],
}


def get_counties():
    """Return all 47 Kenyan Counties sorted alphabetically."""
    return sorted(KENYA_COUNTIES)


def get_sub_counties(county_name: str):
    """Return list of sub-counties for a given county."""
    return KENYA_SUB_COUNTIES.get(county_name, ["Central", "North", "South", "East", "West"])


def get_wards(sub_county_name: str):
    """Return list of wards for a given sub-county."""
    return KENYA_WARDS.get(sub_county_name, ["Central Ward", "Township", "North Ward", "South Ward"])
