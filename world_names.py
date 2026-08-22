"""
world_names.py — Realistic Global Geographical Naming Database for REGNUM.

Hierarchical database of 10 top populous nations/countries, each containing:
- 10 prominent states / provinces
- 10 prominent cities / settlements per province (1,000 total cities)
Also provides atmospheric wilderness, mountain, forest, and ocean names.
"""

import random

# 10 Populous Countries -> 10 States/Provinces -> 10 Cities each
GLOBAL_NATION_DATA = {
    "United States": {
        "California": ["Los Angeles", "San Diego", "San Jose", "San Francisco", "Fresno", "Sacramento", "Long Beach", "Oakland", "Bakersfield", "Anaheim"],
        "Texas": ["Houston", "San Antonio", "Dallas", "Austin", "Fort Worth", "El Paso", "Arlington", "Corpus Christi", "Plano", "Lubbock"],
        "Florida": ["Jacksonville", "Miami", "Tampa", "Orlando", "St. Petersburg", "Hialeah", "Port St. Lucie", "Cape Coral", "Tallahassee", "Fort Lauderdale"],
        "New York": ["New York City", "Buffalo", "Rochester", "Yonkers", "Syracuse", "Albany", "New Rochelle", "Mount Vernon", "Schenectady", "Utica"],
        "Pennsylvania": ["Philadelphia", "Pittsburgh", "Allentown", "Reading", "Erie", "Upper Darby", "Scranton", "Bethlehem", "Lancaster", "Harrisburg"],
        "Illinois": ["Chicago", "Aurora", "Joliet", "Naperville", "Rockford", "Elgin", "Springfield", "Peoria", "Waukegan", "Champaign"],
        "Ohio": ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron", "Dayton", "Parma", "Canton", "Lorain", "Hamilton"],
        "Georgia": ["Atlanta", "Columbus", "Augusta", "Macon", "Savannah", "Athens", "Sandy Springs", "South Fulton", "Roswell", "Johns Creek"],
        "North Carolina": ["Charlotte", "Raleigh", "Greensboro", "Durham", "Winston-Salem", "Fayetteville", "Cary", "Wilmington", "High Point", "Concord"],
        "Michigan": ["Detroit", "Grand Rapids", "Warren", "Sterling Heights", "Ann Arbor", "Lansing", "Dearborn", "Clinton", "Livonia", "Troy"],
    },
    "China": {
        "Guangdong": ["Guangzhou", "Shenzhen", "Dongguan", "Foshan", "Huizhou", "Zhongshan", "Shantou", "Jiangmen", "Zhanjiang", "Zhuhai"],
        "Shandong": ["Jinan", "Qingdao", "Yantai", "Weifang", "Zibo", "Jining", "Linyi", "Taian", "Dezhou", "Liaocheng"],
        "Henan": ["Zhengzhou", "Luoyang", "Nanyang", "Kaifeng", "Xinxiang", "Anyang", "Xuchang", "Pingdingshan", "Jiaozuo", "Shangqiu"],
        "Sichuan": ["Chengdu", "Mianyang", "Nanchong", "Yibin", "Luzhou", "Dazhou", "Deyang", "Leshan", "Zigong", "Panzhihua"],
        "Jiangsu": ["Nanjing", "Suzhou", "Wuxi", "Changzhou", "Nantong", "Xuzhou", "Yangzhou", "Yancheng", "Taizhou", "Zhenjiang"],
        "Hebei": ["Shijiazhuang", "Tangshan", "Baoding", "Handan", "Cangzhou", "Langfang", "Xingtai", "Qinhuangdao", "Zhangjiakou", "Chengde"],
        "Zhejiang": ["Hangzhou", "Ningbo", "Wenzhou", "Shaoxing", "Jiaxing", "Jinhua", "Taizhou", "Huzhou", "Quzhou", "Zhoushan"],
        "Hunan": ["Changsha", "Hengyang", "Zhuzhou", "Xiangtan", "Yueyang", "Changde", "Yiyang", "Chenzhou", "Yongzhou", "Huaihua"],
        "Anhui": ["Hefei", "Wuhu", "Bengbu", "Huainan", "Maanshan", "Huaibei", "Tongling", "Anqing", "Huangshan", "Chuzhou"],
        "Hubei": ["Wuhan", "Xiangyang", "Yichang", "Jingzhou", "Huangshi", "Shiyan", "Xiaogan", "Huanggang", "Xianning", "Suizhou"],
    },
    "India": {
        "Uttar Pradesh": ["Lucknow", "Kanpur", "Varanasi", "Agra", "Prayagraj", "Meerut", "Ghaziabad", "Bareilly", "Aligarh", "Moradabad"],
        "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Thane", "Nashik", "Kalyan", "Aurangabad", "Solapur", "Amravati", "Kolhapur"],
        "Bihar": ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Purnia", "Darbhanga", "Bihar Sharif", "Arrah", "Begusarai", "Katihar"],
        "West Bengal": ["Kolkata", "Howrah", "Asansol", "Siliguri", "Durgapur", "Bardhaman", "Malda", "Baharampur", "Habra", "Kharagpur"],
        "Madhya Pradesh": ["Indore", "Bhopal", "Jabalpur", "Gwalior", "Ujjain", "Sagar", "Dewas", "Satna", "Ratlam", "Rewa"],
        "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tiruppur", "Erode", "Vellore", "Thoothukudi", "Dindigul"],
        "Rajasthan": ["Jaipur", "Jodhpur", "Kota", "Bikaner", "Ajmer", "Udaipur", "Bhilwara", "Alwar", "Bharatpur", "Sikar"],
        "Karnataka": ["Bengaluru", "Mysuru", "Hubballi", "Mangaluru", "Belagavi", "Davanagere", "Ballari", "Vijayapura", "Shivamogga", "Tumakuru"],
        "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Jamnagar", "Junagadh", "Gandhinagar", "Anand", "Navsari"],
        "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur", "Nellore", "Kurnool", "Kakinada", "Rajahmundry", "Tirupati", "Kadapa", "Anantapur"],
    },
    "Indonesia": {
        "West Java": ["Bandung", "Bekasi", "Depok", "Bogor", "Tasikmalaya", "Cimahi", "Sukabumi", "Cirebon", "Garut", "Purwakarta"],
        "East Java": ["Surabaya", "Malang", "Kediri", "Probolinggo", "Pasuruan", "Madiun", "Batu", "Blitar", "Mojokerto", "Banyuwangi"],
        "Central Java": ["Semarang", "Surakarta", "Tegal", "Pekalongan", "Magelang", "Salatiga", "Purwokerto", "Cilacap", "Kudus", "Klaten"],
        "North Sumatra": ["Medan", "Pematangsiantar", "Binjai", "Tebing Tinggi", "Tanjungbalai", "Sibolga", "Padang Sidempuan", "Gunungsitoli", "Kabanjahe", "Balige"],
        "Banten": ["Tangerang", "South Tangerang", "Serang", "Cilegon", "Pandeglang", "Rangkasbitung", "Tigaraksa", "Ciruas", "Malingping", "Labuan"],
        "South Sumatra": ["Palembang", "Prabumulih", "Lubuklinggau", "Pagar Alam", "Baturaja", "Kayu Agung", "Lahat", "Muara Enim", "Sekayu", "Indralaya"],
        "Riau": ["Pekanbaru", "Dumai", "Duri", "Bengkalis", "Siak", "Rengat", "Bangkinang", "Pangkalan Kerinci", "Pasir Pengaraian", "Bagansiapiapi"],
        "South Sulawesi": ["Makassar", "Palopo", "Parepare", "Maros", "Gowa", "Watampone", "Bulukumba", "Sengkang", "Bantaeng", "Jeneponto"],
        "Lampung": ["Bandar Lampung", "Metro", "Kotabumi", "Kalianda", "Gunung Sugih", "Gedong Tataan", "Pringsewu", "Liwa", "Menggala", "Sukadana"],
        "Bali": ["Denpasar", "Singaraja", "Semarapura", "Amlapura", "Tabanan", "Gianyar", "Bangli", "Negara", "Ubud", "Kuta"],
    },
    "Brazil": {
        "São Paulo": ["São Paulo", "Guarulhos", "Campinas", "São Bernardo", "Santo André", "Osasco", "São José dos Campos", "Ribeirão Preto", "Sorocaba", "Santos"],
        "Minas Gerais": ["Belo Horizonte", "Uberlândia", "Contagem", "Juiz de Fora", "Betim", "Montes Claros", "Ribeirão das Neves", "Uberaba", "Governador Valadares", "Ipatinga"],
        "Rio de Janeiro": ["Rio de Janeiro", "São Gonçalo", "Duque de Caxias", "Nova Iguaçu", "Niterói", "Belford Roxo", "Campos dos Goytacazes", "São João de Meriti", "Petrópolis", "Volta Redonda"],
        "Bahia": ["Salvador", "Feira de Santana", "Vitória da Conquista", "Camaçari", "Juazeiro", "Itabuna", "Lauro de Freitas", "Ilhéus", "Jequié", "Teixeira de Freitas"],
        "Paraná": ["Curitiba", "Londrina", "Maringá", "Ponta Grossa", "Cascavel", "São José dos Pinhais", "Foz do Iguaçu", "Colombo", "Guarapuava", "Paranaguá"],
        "Rio Grande do Sul": ["Porto Alegre", "Caxias do Sul", "Canoas", "Pelotas", "Santa Maria", "Gravataí", "Viamão", "Novo Hamburgo", "São Leopoldo", "Rio Grande"],
        "Pernambuco": ["Recife", "Jaboatão dos Guararapes", "Olinda", "Caruaru", "Petrolina", "Paulista", "Cabo de Santo Agostinho", "Camaragibe", "Garanhuns", "Vitória de Santo Antão"],
        "Ceará": ["Fortaleza", "Caucaia", "Juazeiro do Norte", "Maracanaú", "Sobral", "Crato", "Itapipoca", "Maranguape", "Iguatu", "Quixadá"],
        "Pará": ["Belém", "Ananindeua", "Santarém", "Marabá", "Parauapebas", "Castanhal", "Abaetetuba", "Cametá", "Marituba", "Bragança"],
        "Santa Catarina": ["Joinville", "Florianópolis", "Blumenau", "São José", "Chapecó", "Itajaí", "Criciúma", "Jaraguá do Sul", "Palhoça", "Lages"],
    },
    "Mexico": {
        "State of Mexico": ["Ecatepec", "Nezahualcóyotl", "Toluca", "Naucalpan", "Chimalhuacán", "Tlalnepantla", "Cuautitlán Izcalli", "Tecámac", "Ixtapaluca", "Atizapán"],
        "Jalisco": ["Guadalajara", "Zapopan", "Tlaquepaque", "Tonalá", "Tlajomulco", "Puerto Vallarta", "Lagos de Moreno", "Tepatitlán", "Ciudad Guzmán", "Ocotlán"],
        "Veracruz": ["Veracruz", "Xalapa", "Coatzacoalcos", "Poza Rica", "Córdoba", "Boca del Río", "Orizaba", "Minatitlán", "Tuxpan", "San Andrés Tuxtla"],
        "Puebla": ["Puebla", "Tehuacán", "San Martín Texmelucan", "Atlixco", "San Pedro Cholula", "Amozoc", "Huauchinango", "Teziutlán", "San Andrés Cholula", "Izúcar de Matamoros"],
        "Guanajuato": ["León", "Irapuato", "Celaya", "Salamanca", "Silao", "Guanajuato", "San Miguel de Allende", "Dolores Hidalgo", "Valle de Santiago", "Cortazar"],
        "Nuevo León": ["Monterrey", "Guadalupe", "San Nicolás", "Apodaca", "General Escobedo", "Santa Catarina", "Juárez", "San Pedro Garza García", "Cadereyta", "García"],
        "Chiapas": ["Tuxtla Gutiérrez", "Tapachula", "San Cristóbal", "Comitán", "Chiapa de Corzo", "Palenque", "Ocosingo", "Villaflores", "Tonalá", "Huixtla"],
        "Michoacán": ["Morelia", "Uruapan", "Zamora", "Lázaro Cárdenas", "Zitácuaro", "Apatzingán", "Hidalgo", "La Piedad", "Pátzcuaro", "Sahuayo"],
        "Oaxaca": ["Oaxaca de Juárez", "Salina Cruz", "Juchitán", "Tuxtepec", "Tehuantepec", "Huajuapan", "Puerto Escondido", "Huatulco", "Miahuatlán", "Tlaxiaco"],
        "Chihuahua": ["Ciudad Juárez", "Chihuahua", "Cuauhtémoc", "Delicias", "Parral", "Nuevo Casas Grandes", "Camargo", "Jiménez", "Ojinaga", "Meoqui"],
    },
    "Nigeria": {
        "Lagos": ["Ikeja", "Lagos Island", "Epe", "Ikorodu", "Badagry", "Surulere", "Yaba", "Apapa", "Lekki", "Agege"],
        "Kano": ["Kano City", "Wudil", "Gwarzo", "Bichi", "Rano", "Gaya", "Karaye", "Dambatta", "Tudun Wada", "Minjibir"],
        "Kaduna": ["Kaduna", "Zaria", "Kafanchan", "Kagoro", "Saminaka", "Birnin Gwari", "Zonkwa", "Makarfi", "Giwa", "Kachia"],
        "Rivers": ["Port Harcourt", "Obio-Akpor", "Bonny", "Eleme", "Okrika", "Degema", "Ahoada", "Opobo", "Bori", "Omoku"],
        "Oyo": ["Ibadan", "Ogbomosho", "Oyo Town", "Iseyin", "Saki", "Kishi", "Eruwa", "Igboho", "Kisi", "Lalupon"],
        "Delta": ["Warri", "Asaba", "Sapele", "Ughelli", "Agbor", "Effurun", "Oghara", "Ozoro", "Kwale", "Burutu"],
        "Anambra": ["Onitsha", "Awka", "Nnewi", "Ekwulobia", "Ihiala", "Aguata", "Ogidi", "Abagana", "Nkpor", "Obosi"],
        "Edo": ["Benin City", "Auchi", "Uromi", "Ekpoma", "Igarra", "Irrua", "Sabongida-Ora", "Abudu", "Ubiaja", "Agenebode"],
        "Ogun": ["Abeokuta", "Ijebu Ode", "Sagamu", "Ota", "Ilaro", "Ifo", "Ago Iwoye", "Ijebu Igbo", "Ayetoro", "Owode"],
        "Enugu": ["Enugu", "Nsukka", "Oji River", "Udi", "Awgu", "Enugu-Ezike", "Agre", "Nike", "Ngwo", "Eha Amufu"],
    },
    "Pakistan": {
        "Punjab": ["Lahore", "Faisalabad", "Rawalpindi", "Gujranwala", "Multan", "Sialkot", "Bahawalpur", "Sargodha", "Sheikhupura", "Jhang"],
        "Sindh": ["Karachi", "Hyderabad", "Sukkur", "Larkana", "Nawabshah", "Mirpur Khas", "Jacobabad", "Shikarpur", "Thatta", "Badin"],
        "Khyber Pakhtunkhwa": ["Peshawar", "Mardan", "Abbottabad", "Mingora", "Kohat", "Dera Ismail Khan", "Swabi", "Charsadda", "Nowshera", "Mansehra"],
        "Balochistan": ["Quetta", "Turbat", "Khuzdar", "Hub", "Chaman", "Gwadar", "Sibi", "Zhob", "Loralai", "Dera Murad Jamali"],
        "Islamabad": ["Islamabad", "Margalla", "Rawal", "Nilore", "Sihala", "Golra", "Tarlai", "Sohan", "Koral", "Bara Kahu"],
        "Azad Kashmir": ["Muzaffarabad", "Mirpur", "Kotli", "Rawalakot", "Bagh", "Bhimber", "Pallandri", "Hattian", "Haveli", "Chakswari"],
        "Gilgit-Baltistan": ["Gilgit", "Skardu", "Chilas", "Hunza", "Ghizer", "Ghanche", "Astore", "Nagar", "Shigar", "Kharmang"],
        "Faisalabad Region": ["Samundri", "Jaranwala", "Tandlianwala", "Chak Jhumra", "Khurrianwala", "Dijkot", "Mamu Kanjan", "Satiana", "Saluni", "Gojra"],
        "Rawalpindi Region": ["Gujar Khan", "Taxila", "Murree", "Kahuta", "Kallar Syedan", "Kotli Sattian", "Wah Cantt", "Daultala", "Mandra", "Chak Beli"],
        "Multan Region": ["Shujabad", "Jalalpur Pirwala", "Makhdoom Rashid", "Lar", "Basti Malook", "Qadirpur Ran", "Raza Abad", "Bahauddin", "Muzaffarabad", "Suraj Miani"],
    },
    "Bangladesh": {
        "Dhaka": ["Dhaka", "Gazipur", "Narayanganj", "Tangail", "Narsingdi", "Faridpur", "Manikganj", "Munshiganj", "Gopalganj", "Madaripur"],
        "Chittagong": ["Chittagong", "Comilla", "Cox's Bazar", "Brahmanbaria", "Chandpur", "Noakhali", "Feni", "Lakshmipur", "Rangamati", "Bandarban"],
        "Rajshahi": ["Rajshahi", "Bogura", "Pabna", "Sirajganj", "Naogaon", "Natore", "Chapai Nawabganj", "Joypurhat", "Ishwardi", "Santahar"],
        "Khulna": ["Khulna", "Jashore", "Kushtia", "Satkhira", "Jhenaidah", "Bagerhat", "Chuadanga", "Magura", "Narail", "Meherpur"],
        "Barisal": ["Barisal", "Patuakhali", "Bhola", "Pirojpur", "Jhalokati", "Barguna", "Bakerganj", "Gournadi", "Kuakata", "Mathbaria"],
        "Sylhet": ["Sylhet", "Moulvibazar", "Habiganj", "Sunamganj", "Sreemangal", "Beanibazar", "Golapganj", "Zakiganj", "Chhatak", "Jagannathpur"],
        "Rangpur": ["Rangpur", "Dinajpur", "Saidpur", "Gaibandha", "Kurigram", "Nilphamari", "Lalmonirhat", "Panchagarh", "Thakurgaon", "Pirganj"],
        "Mymensingh": ["Mymensingh", "Jamalpur", "Netrokona", "Sherpur", "Muktagacha", "Bhaluka", "Trishal", "Gafargaon", "Ishwarganj", "Phulpur"],
        "Comilla Region": ["Comilla City", "Laksam", "Daudkandi", "Chandina", "Debidwar", "Burichang", "Brahmanpara", "Muradnagar", "Homna", "Meghna"],
        "Bogura Region": ["Bogura City", "Sherpur", "Shibganj", "Gabtali", "Kahaloo", "Dhunat", "Adamdighi", "Dupchanchia", "Sonatala", "Sariakandi"],
    },
    "Russia": {
        "Moscow Oblast": ["Balashikha", "Podolsk", "Khimki", "Mytishchi", "Korolyov", "Lyubertsy", "Krasnogorsk", "Elektrostal", "Kolomna", "Odintsovo"],
        "Saint Petersburg": ["Saint Petersburg", "Kolpino", "Pushkin", "Petergof", "Kronshtadt", "Sestroretsk", "Lomonosov", "Zelenogorsk", "Pavlovsk", "Krasnoye Selo"],
        "Krasnodar Krai": ["Krasnodar", "Sochi", "Novorossiysk", "Armavir", "Yeysk", "Anapa", "Gelendzhik", "Kropotkin", "Slavyansk", "Tuapse"],
        "Tatarstan": ["Kazan", "Naberezhnye Chelny", "Nizhnekamsk", "Almetyevsk", "Zelenodolsk", "Bugulma", "Yelabuga", "Leninogorsk", "Chistopol", "Zainsk"],
        "Sverdlovsk Oblast": ["Yekaterinburg", "Nizhny Tagil", "Kamensk-Uralsky", "Pervouralsk", "Serov", "Novouralsk", "Asbest", "Polevskoy", "Revda", "Verkhnyaya Pyshma"],
        "Rostov Oblast": ["Rostov-on-Don", "Taganrog", "Shakhty", "Novocherkassk", "Volgodonsk", "Bataysk", "Novoshakhtinsk", "Kamensk-Shakhtinsky", "Azov", "Gukovo"],
        "Bashkortostan": ["Ufa", "Sterlitamak", "Salavat", "Neftekamsk", "Oktyabrsky", "Beloretsk", "Ishimbay", "Tuymazy", "Kumertau", "Sibay"],
        "Chelyabinsk Oblast": ["Chelyabinsk", "Magnitogorsk", "Zlatoust", "Miass", "Kopeysk", "Ozersk", "Troitsk", "Snezhinsk", "Satka", "Chebarkul"],
        "Samara Oblast": ["Samara", "Tolyatti", "Syzran", "Novokuybyshevsk", "Chapayevsk", "Zhigulyovsk", "Otradny", "Kinel", "Pokhvistnevo", "Oktyabrsk"],
        "Nizhny Novgorod Oblast": ["Nizhny Novgorod", "Dzerzhinsk", "Arzamas", "Sarov", "Bor", "Kstovo", "Pavlovo", "Vyksa", "Balakhna", "Zavolzhye"],
    },
}

# Evocative wilderness terrain names for uncolonized tiles
WILD_TERRAIN_NAMES = [
    "Echo Valley", "Great Basin", "Whispering Ridge", "Emerald Steppe",
    "Silver Plateau", "Red Canyon", "Verdant Reach", "Shadow Peak",
    "Golden Meadows", "Mist Haven", "Bramble Wilds", "Eagle Crag",
    "Silent Marsh", "Timber Highlands", "Sunken Hollow", "Breeze Crest",
]

OCEAN_BASIN_NAMES = [
    "Azure Abyss", "Sapphire Deep", "Cobalt Strait", "Glacial Basin",
    "Cerulean Bay", "Leviathan Trench", "Coral Expanse", "Storm Reach",
    "Trident Waters", "Abyssal Gulf", "Indigo Shelf", "Pelagic Sea",
]


def get_country_names():
    """Return the list of 10 major country names."""
    return list(GLOBAL_NATION_DATA.keys())


def get_provinces_for_country(country_name: str):
    """Return dict of provinces -> list of cities for a given country."""
    return GLOBAL_NATION_DATA.get(country_name, {})


def assign_world_identities(tiles, nations):
    """Assign realistic country names to nations, state names to provinces, and city names to tiles."""
    available_countries = list(GLOBAL_NATION_DATA.keys())
    random.shuffle(available_countries)

    for i, n in enumerate(nations):
        country_name = available_countries[i % len(available_countries)]
        n.display_name = country_name
        country_data = GLOBAL_NATION_DATA[country_name]
        prov_names = list(country_data.keys())

        # Assign province identities
        for p_idx, prov in enumerate(getattr(n, 'provinces', [])):
            p_name = prov_names[p_idx % len(prov_names)]
            prov.display_name = p_name
            cities = list(country_data[p_name])
            random.shuffle(cities)

            # Assign city names to each tile in this province
            for t_idx, tile in enumerate(prov.tiles):
                tile.city_name = cities[t_idx % len(cities)]
                tile.display_name = tile.city_name
                tile.province_display = p_name
                tile.nation_display = country_name

    # Name remaining wilderness and ocean tiles
    wild_pool = list(WILD_TERRAIN_NAMES)
    ocean_pool = list(OCEAN_BASIN_NAMES)
    random.shuffle(wild_pool)
    random.shuffle(ocean_pool)

    w_idx = 0
    o_idx = 0
    for tile in tiles:
        if not hasattr(tile, 'display_name') or getattr(tile, 'owner_nation', None) is None:
            if getattr(tile, 'is_ocean', False) or getattr(tile, 'elevation', 0.0) < 0.0:
                tile.city_name = ocean_pool[o_idx % len(ocean_pool)]
                tile.display_name = tile.city_name
                tile.province_display = "Open Sea"
                tile.nation_display = "Ocean Basin"
                o_idx += 1
            else:
                tile.city_name = wild_pool[w_idx % len(wild_pool)]
                tile.display_name = tile.city_name
                tile.province_display = "Wild Frontier"
                tile.nation_display = "Unclaimed"
                w_idx += 1
