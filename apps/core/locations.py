"""
Kenya Administrative Location Hierarchy (47 Counties, Sub-Counties, Wards)
Used for Artisan Origin Badges, Shop Location Registration, Order Shipping/Pickup, and Ziuza Local Discovery.
"""

KENYA_COUNTIES = [
    "Baringo", "Bomet", "Bungoma", "Busia", "Elgeyo-Marakwet", "Embu", "Garissa",
    "Homa Bay", "Isiolo", "Kajiado", "Kakamega", "Kericho", "Kiambu", "Kilifi",
    "Kirinyaga", "Kisii", "Kisumu", "Kitui", "Kwale", "Lamu", "Laikipia",
    "Machakos", "Makueni", "Mandera", "Marsabit", "Meru", "Migori", "Mombasa",
    "Murang'a", "Nairobi", "Nakuru", "Nandi", "Narok", "Nyamira", "Nyandarua",
    "Nyeri", "Samburu", "Siaya", "Taita–Taveta", "Tana River", "Tharaka-Nithi",
    "Trans-Nzoia", "Turkana", "Uasin Gishu", "Vihiga", "Wajir", "West Pokot"
]

KENYA_SUB_COUNTIES = {
    "Nairobi": [
        "Westlands", "Dagoretti North", "Dagoretti South", "Lang'ata", "Kibra",
        "Ruaraka", "Kasarani", "Embakasi South", "Embakasi North", "Embakasi Central",
        "Embakasi East", "Embakasi West", "Makadara", "Kamukunji", "Starehe", "Mathare", "Roysambu"
    ],
    "Mombasa": ["Changamwe", "Jomvu", "Kisauni", "Nyali", "Likoni", "Mvita"],
    "Machakos": ["Machakos Town", "Mavoko", "Mwala", "Yatta", "Kangundo", "Matungulu", "Kathiani", "Masinga"],
    "Kiambu": ["Githunguri", "Kiambu Town", "Ruiru", "Thika Town", "Juja", "Kikuyu", "Kabete", "Limuru", "Lari", "Gatundu South", "Gatundu North", "Karuri"],
    "Nakuru": ["Nakuru East", "Nakuru West", "Naivasha", "Gilgil", "Kuresoi South", "Kuresoi North", "Molo", "Njoro", "Rongai", "Subukia", "Bahati"],
    "Kisumu": ["Kisumu Central", "Kisumu East", "Kisumu West", "Muhoroni", "Nyando", "Nyakach", "Seme"],
    "Kilifi": ["Kilifi North", "Kilifi South", "Kaloleni", "Rabai", "Ganze", "Malindi", "Magarini"],
    "Lamu": ["Lamu East", "Lamu West"],
    "Kisii": ["Kitutu Chache North", "Kitutu Chache South", "Nyaribari Chache", "Nyaribari Masaba", "Bommachoge Borabu", "Bommachoge Chache", "Bobasi", "South Mugirango", "Bonchari"],
    "Uasin Gishu": ["Ainabkoi", "Kapseret", "Kesses", "Moiben", "Soy", "Turbo"],
    "Kajiado": ["Kajiado Central", "Kajiado North", "Kajiado South", "Kajiado East", "Kajiado West"],
    "Nyeri": ["Tetu", "Kieni", "Mathira", "Othaya", "Mukurweini", "Nyeri Town"],
    "Meru": ["Imenti South", "Imenti Central", "Imenti North", "Buuri", "Tigania West", "Tigania East", "Tigania Central", "Igembe South", "Igembe Central", "Igembe North"],
    "Kakamega": ["Lurambi", "Shinyalu", "Ikolomani", "Mumias East", "Mumias West", "Matungu", "Butere", "Khwisero", "Malava", "Navakholo", "Likuyani", "Lugari"],
    "Bungoma": ["Bumula", "Kanduyi", "Sirisia", "Kabuchai", "Tongaren", "Webuye West", "Webuye East", "Mt. Elgon", "Kimilili"],
    "Kericho": ["Ainamoi", "Belgut", "Bureti", "Kipkelion East", "Kipkelion West", "Soin/Sigowet"],
    "Murang'a": ["Kangema", "Mathioya", "Kiharu", "Kigumo", "Maragua", "Kandara", "Gatanga"],
    "Embu": ["Manyatta", "Runyenjes", "Mbeere South", "Mbeere North"],
    "Laikipia": ["Laikipia West", "Laikipia East", "Laikipia North"],
    "Kwale": ["Msambweni", "Lungalunga", "Matuga", "Kinango"],
    "Taita–Taveta": ["Taveta", "Wundanyi", "Mwatate", "Voi"],
}

KENYA_WARDS = {
    # Nairobi
    "Westlands": ["Kitisuru", "Parklands/Highridge", "Karura", "Kangemi", "Mountain View"],
    "Dagoretti North": ["Kilimani", "Kawangware", "Gatina", "Kileleshwa", "Kabiro"],
    "Dagoretti South": ["Mutu-ini", "Ngando", "Riruta", "Uthiru/Ruthimitu", "Waithaka"],
    "Lang'ata": ["Karen", "Nairobi West", "Mugumo-ini", "South C", "Nyayo Highrise"],
    "Kibra": ["Laini Saba", "Lindi", "Makina", "Woodley/Kenyatta Golf Course", "Sarang'ombe"],
    "Roysambu": ["Githurai", "Kahawa West", "Zimmerman", "Roysambu", "Kahawa"],
    "Kasarani": ["Clay City", "Mwiki", "Kasarani", "Njiru", "Ruai"],
    "Ruaraka": ["Babadogo", "Utalii", "Mathare North", "Lucky Summer", "Korogocho"],
    "Embakasi South": ["Imara Daima", "Kwa Njenga", "Kwa Reuben", "Pipeline", "Kware"],
    "Embakasi North": ["Kariobangi North", "Dandora Area I", "Dandora Area II", "Dandora Area III", "Dandora Area IV"],
    "Embakasi Central": ["Kayole North", "Kayole Central", "Kayole South", "Komarock", "Matopeni/Spring Valley"],
    "Embakasi East": ["Upper Savanna", "Lower Savanna", "Embakasi", "Utawala", "Mihango"],
    "Embakasi West": ["Umoja I", "Umoja II", "Mowlem", "Kariobangi South"],
    "Makadara": ["Maringo/Hamza", "Viwandani", "Harambee", "Makongeni"],
    "Kamukunji": ["Pumwani", "Eastleigh North", "Eastleigh South", "Airbase", "California"],
    "Starehe": ["Nairobi Central", "Ngara", "Pangani", "Ziwani/Kariokor", "Landimawe", "Nairobi South"],
    "Mathare": ["Hospital", "Mabatini", "Huruma", "Ngei", "Mlango Kubwa", "Kiamaiko"],
    # Mombasa
    "Mvita": ["Mji wa Kale/Makadara", "Tudor", "Tononoka", "Shimanzi/Ganjoni", "Majengo"],
    "Nyali": ["Frere Town", "Ziwa La Ng'ombe", "Mkomani", "Kongowea", "Kaduruni"],
    "Changamwe": ["Port Reitz", "Kipevu", "Airport", "Changamwe", "Chaani"],
    "Kisauni": ["Mjambere", "Junda", "Bamburi", "Mwakirunge", "Mtopanga", "Magogoni", "Shanzu"],
    "Likoni": ["Mtongwe", "Shika Adabu", "Bofu", "Likoni", "Timbwani"],
    # Machakos
    "Machakos Town": ["Machakos Central", "Muvuti/Kiima-Kimwe", "Mutituni", "Kalama", "Kua", "Kimutwa"],
    "Mavoko": ["Athi River", "Kinanie", "Muthwani", "Syokimau/Mulolongo"],
    "Mwala": ["Mwala", "Makaveti", "Kibauni", "Masii", "Kathama", "Vyulya"],
    # Kiambu
    "Kiambu Town": ["Ting'ang'a", "Ndumberi", "Riabai", "Township"],
    "Ruiru": ["Gitothua", "Biashara", "Gatongora", "Kahawa/Sukari", "Kahawa Wendani", "Kiuu", "Mwiki", "Mwihoko"],
    "Thika Town": ["Township", "Kamenu", "Hospital", "Gatuanyaga", "Ngoliba"],
    "Juja": ["Murera", "Theta", "Juja", "Witeithie", "Kalimoni"],
    "Kikuyu": ["Karai", "Nachu", "Sigona", "Kikuyu", "Kinoo"],
    # Nakuru
    "Naivasha": ["Naivasha Town", "Hell's Gate", "Olkaria", "Mai Mahiu", "Maeila"],
    "Nakuru East": ["Biashara", "Kivumbini", "Flamingo", "Menengai", "Nakuru East"],
    "Nakuru West": ["Barut", "London", "Kaptembwo", "Kapkures", "Rhoda", "Shaabab"],
    # Kisumu
    "Kisumu Central": ["Railways", "Migosi", "Shaurimoyo Kaloleni", "Market Milimani", "Kondele", "Nyalenda A"],
    "Kisumu East": ["Kajulu", "Kolwa East", "Manyatta B", "Nyando", "Kolwa Central"],
    # Uasin Gishu
    "Turbo": ["Ngenyilel", "Tapsagoi", "Kamagut", "Kiplombe", "Kapsaos", "Huruma"],
    "Ainabkoi": ["Kapsoya", "Kaptagat", "Ainabkoi/Olare"],
}


def get_counties() -> list[str]:
    """Return all 47 Kenyan Counties sorted alphabetically."""
    return sorted(KENYA_COUNTIES)


def get_sub_counties(county_name: str) -> list[str]:
    """Return list of sub-counties for a given county."""
    county_clean = (county_name or "").strip()
    if county_clean in KENYA_SUB_COUNTIES:
        return KENYA_SUB_COUNTIES[county_clean]
    # Check case-insensitive match
    for c_name, sub_list in KENYA_SUB_COUNTIES.items():
        if c_name.lower() == county_clean.lower():
            return sub_list
    return ["Central", "North", "South", "East", "West", "Township"]


def get_wards(sub_county_name: str) -> list[str]:
    """Return list of wards for a given sub-county."""
    sc_clean = (sub_county_name or "").strip()
    if sc_clean in KENYA_WARDS:
        return KENYA_WARDS[sc_clean]
    # Case-insensitive match
    for sc_name, ward_list in KENYA_WARDS.items():
        if sc_name.lower() == sc_clean.lower():
            return ward_list
    return ["Central Ward", "Township", "North Ward", "South Ward", "East Ward", "West Ward"]

