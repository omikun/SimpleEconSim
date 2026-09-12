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
        "District of Columbia": ["Washington, D.C.", "Georgetown", "Capitol Hill", "Foggy Bottom", "Dupont Circle", "Anacostia", "Adams Morgan", "Tenleytown", "Petworth", "Brookland"],
        "California": ["Sacramento", "Los Angeles", "San Diego", "San Jose", "San Francisco", "Fresno", "Long Beach", "Oakland", "Bakersfield", "Anaheim"],
        "Texas": ["Austin", "Houston", "San Antonio", "Dallas", "Fort Worth", "El Paso", "Arlington", "Corpus Christi", "Plano", "Lubbock"],
        "Florida": ["Tallahassee", "Jacksonville", "Miami", "Tampa", "Orlando", "St. Petersburg", "Hialeah", "Port St. Lucie", "Cape Coral", "Fort Lauderdale"],
        "New York": ["Albany", "New York City", "Buffalo", "Rochester", "Yonkers", "Syracuse", "New Rochelle", "Mount Vernon", "Schenectady", "Utica"],
        "Pennsylvania": ["Harrisburg", "Philadelphia", "Pittsburgh", "Allentown", "Reading", "Erie", "Upper Darby", "Scranton", "Bethlehem", "Lancaster"],
        "Illinois": ["Springfield", "Chicago", "Aurora", "Joliet", "Naperville", "Rockford", "Elgin", "Peoria", "Waukegan", "Champaign"],
        "Ohio": ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron", "Dayton", "Parma", "Canton", "Lorain", "Hamilton"],
        "Georgia": ["Atlanta", "Columbus", "Augusta", "Macon", "Savannah", "Athens", "Sandy Springs", "South Fulton", "Roswell", "Johns Creek"],
        "North Carolina": ["Raleigh", "Charlotte", "Greensboro", "Durham", "Winston-Salem", "Fayetteville", "Cary", "Wilmington", "High Point", "Concord"],
    },
    "China": {
        "Beijing Municipality": ["Beijing", "Chaoyang", "Haidian", "Fengtai", "Dongcheng", "Xicheng", "Tongzhou", "Changping", "Daxing", "Shunyi"],
        "Guangdong": ["Guangzhou", "Shenzhen", "Dongguan", "Foshan", "Huizhou", "Zhongshan", "Shantou", "Jiangmen", "Zhanjiang", "Zhuhai"],
        "Shandong": ["Jinan", "Qingdao", "Yantai", "Weifang", "Zibo", "Jining", "Linyi", "Taian", "Dezhou", "Liaocheng"],
        "Henan": ["Zhengzhou", "Luoyang", "Nanyang", "Kaifeng", "Xinxiang", "Anyang", "Xuchang", "Pingdingshan", "Jiaozuo", "Shangqiu"],
        "Sichuan": ["Chengdu", "Mianyang", "Nanchong", "Yibin", "Luzhou", "Dazhou", "Deyang", "Leshan", "Zigong", "Panzhihua"],
        "Jiangsu": ["Nanjing", "Suzhou", "Wuxi", "Changzhou", "Nantong", "Xuzhou", "Yangzhou", "Yancheng", "Taizhou", "Zhenjiang"],
        "Hebei": ["Shijiazhuang", "Tangshan", "Baoding", "Handan", "Cangzhou", "Langfang", "Xingtai", "Qinhuangdao", "Zhangjiakou", "Chengde"],
        "Zhejiang": ["Hangzhou", "Ningbo", "Wenzhou", "Shaoxing", "Jiaxing", "Jinhua", "Taizhou", "Huzhou", "Quzhou", "Zhoushan"],
        "Hunan": ["Changsha", "Hengyang", "Zhuzhou", "Xiangtan", "Yueyang", "Changde", "Yiyang", "Chenzhou", "Yongzhou", "Huaihua"],
        "Anhui": ["Hefei", "Wuhu", "Bengbu", "Huainan", "Maanshan", "Huaibei", "Tongling", "Anqing", "Huangshan", "Chuzhou"],
    },
    "India": {
        "Uttar Pradesh": ["Lucknow", "Kanpur", "Varanasi", "Agra", "Prayagraj", "Meerut", "Ghaziabad", "Bareilly", "Aligarh", "Moradabad"],
        "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Thane", "Nashik", "Kalyan", "Aurangabad", "Solapur", "Amravati", "Kolhapur"],
        "Bihar": ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Purnia", "Darbhanga", "Bihar Sharif", "Arrah", "Begusarai", "Katihar"],
        "West Bengal": ["Kolkata", "Howrah", "Asansol", "Siliguri", "Durgapur", "Bardhaman", "Malda", "Baharampur", "Habra", "Kharagpur"],
        "Madhya Pradesh": ["Bhopal", "Indore", "Jabalpur", "Gwalior", "Ujjain", "Sagar", "Dewas", "Satna", "Ratlam", "Rewa"],
        "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tiruppur", "Erode", "Vellore", "Thoothukudi", "Dindigul"],
        "Rajasthan": ["Jaipur", "Jodhpur", "Kota", "Bikaner", "Ajmer", "Udaipur", "Bhilwara", "Alwar", "Bharatpur", "Sikar"],
        "Karnataka": ["Bengaluru", "Mysuru", "Hubballi", "Mangaluru", "Belagavi", "Davanagere", "Ballari", "Vijayapura", "Shivamogga", "Tumakuru"],
        "Gujarat": ["Gandhinagar", "Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Jamnagar", "Junagadh", "Anand", "Navsari"],
        "Andhra Pradesh": ["Amaravati", "Visakhapatnam", "Vijayawada", "Guntur", "Nellore", "Kurnool", "Kakinada", "Rajahmundry", "Tirupati", "Kadapa"],
    },
    "Indonesia": {
        "West Java": ["Bandung", "Bekasi", "Depok", "Bogor", "Tasikmalaya", "Cimahi", "Sukabumi", "Cirebon", "Garut", "Purwakarta"],
        "East Java": ["Surabaya", "Malang", "Kediri", "Probolinggo", "Pasuruan", "Madiun", "Batu", "Blitar", "Mojokerto", "Banyuwangi"],
        "Central Java": ["Semarang", "Surakarta", "Tegal", "Pekalongan", "Magelang", "Salatiga", "Purwokerto", "Cilacap", "Kudus", "Klaten"],
        "North Sumatra": ["Medan", "Pematangsiantar", "Binjai", "Tebing Tinggi", "Tanjungbalai", "Sibolga", "Padang Sidempuan", "Gunungsitoli", "Kabanjahe", "Balige"],
        "Banten": ["Serang", "Tangerang", "South Tangerang", "Cilegon", "Pandeglang", "Rangkasbitung", "Tigaraksa", "Ciruas", "Malingping", "Labuan"],
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
        "Santa Catarina": ["Florianópolis", "Joinville", "Blumenau", "São José", "Chapecó", "Itajaí", "Criciúma", "Jaraguá do Sul", "Palhoça", "Lages"],
    },
    "Mexico": {
        "State of Mexico": ["Toluca", "Ecatepec", "Nezahualcóyotl", "Naucalpan", "Chimalhuacán", "Tlalnepantla", "Cuautitlán Izcalli", "Tecámac", "Ixtapaluca", "Atizapán"],
        "Jalisco": ["Guadalajara", "Zapopan", "Tlaquepaque", "Tonalá", "Tlajomulco", "Puerto Vallarta", "Lagos de Moreno", "Tepatitlán", "Ciudad Guzmán", "Ocotlán"],
        "Veracruz": ["Xalapa", "Veracruz", "Coatzacoalcos", "Poza Rica", "Córdoba", "Boca del Río", "Orizaba", "Minatitlán", "Tuxpan", "San Andrés Tuxtla"],
        "Puebla": ["Puebla", "Tehuacán", "San Martín Texmelucan", "Atlixco", "San Pedro Cholula", "Amozoc", "Huauchinango", "Teziutlán", "San Andrés Cholula", "Izúcar de Matamoros"],
        "Guanajuato": ["Guanajuato", "León", "Irapuato", "Celaya", "Salamanca", "Silao", "San Miguel de Allende", "Dolores Hidalgo", "Valle de Santiago", "Cortazar"],
        "Nuevo León": ["Monterrey", "Guadalupe", "San Nicolás", "Apodaca", "General Escobedo", "Santa Catarina", "Juárez", "San Pedro Garza García", "Cadereyta", "García"],
        "Chiapas": ["Tuxtla Gutiérrez", "Tapachula", "San Cristóbal", "Comitán", "Chiapa de Corzo", "Palenque", "Ocosingo", "Villaflores", "Tonalá", "Huixtla"],
        "Michoacán": ["Morelia", "Uruapan", "Zamora", "Lázaro Cárdenas", "Zitácuaro", "Apatzingán", "Hidalgo", "La Piedad", "Pátzcuaro", "Sahuayo"],
        "Oaxaca": ["Oaxaca de Juárez", "Salina Cruz", "Juchitán", "Tuxtepec", "Tehuantepec", "Huajuapan", "Puerto Escondido", "Huatulco", "Miahuatlán", "Tlaxiaco"],
        "Chihuahua": ["Chihuahua", "Ciudad Juárez", "Cuauhtémoc", "Delicias", "Parral", "Nuevo Casas Grandes", "Camargo", "Jiménez", "Ojinaga", "Meoqui"],
    },
    "Nigeria": {
        "Lagos": ["Ikeja", "Lagos Island", "Epe", "Ikorodu", "Badagry", "Surulere", "Yaba", "Apapa", "Lekki", "Agege"],
        "Kano": ["Kano City", "Wudil", "Gwarzo", "Bichi", "Rano", "Gaya", "Karaye", "Dambatta", "Tudun Wada", "Minjibir"],
        "Kaduna": ["Kaduna", "Zaria", "Kafanchan", "Kagoro", "Saminaka", "Birnin Gwari", "Zonkwa", "Makarfi", "Giwa", "Kachia"],
        "Rivers": ["Port Harcourt", "Obio-Akpor", "Bonny", "Eleme", "Okrika", "Degema", "Ahoada", "Opobo", "Bori", "Omoku"],
        "Oyo": ["Ibadan", "Ogbomosho", "Oyo Town", "Iseyin", "Saki", "Kishi", "Eruwa", "Igboho", "Kisi", "Lalupon"],
        "Delta": ["Asaba", "Warri", "Sapele", "Ughelli", "Agbor", "Effurun", "Oghara", "Ozoro", "Kwale", "Burutu"],
        "Anambra": ["Awka", "Onitsha", "Nnewi", "Ekwulobia", "Ihiala", "Aguata", "Ogidi", "Abagana", "Nkpor", "Obosi"],
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
        "Faisalabad Region": ["Faisalabad", "Samundri", "Jaranwala", "Tandlianwala", "Chak Jhumra", "Khurrianwala", "Dijkot", "Mamu Kanjan", "Satiana", "Saluni"],
        "Rawalpindi Region": ["Rawalpindi", "Gujar Khan", "Taxila", "Murree", "Kahuta", "Kallar Syedan", "Kotli Sattian", "Wah Cantt", "Daultala", "Mandra"],
        "Multan Region": ["Multan", "Shujabad", "Jalalpur Pirwala", "Makhdoom Rashid", "Lar", "Basti Malook", "Qadirpur Ran", "Raza Abad", "Bahauddin", "Suraj Miani"],
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
        "Moscow Oblast": ["Moscow", "Krasnogorsk", "Balashikha", "Podolsk", "Khimki", "Mytishchi", "Korolyov", "Lyubertsy", "Elektrostal", "Kolomna"],
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
    "Japan": {
        "Kanto": ["Tokyo", "Yokohama", "Kawasaki", "Saitama", "Chiba", "Sagamihara", "Hachioji", "Funabashi", "Kawaguchi", "Machida"],
        "Kansai": ["Osaka", "Kyoto", "Kobe", "Sakai", "Higashiosaka", "Nishinomiya", "Amagasaki", "Nara", "Otsu", "Wakayama"],
        "Chubu": ["Nagoya", "Shizuoka", "Hamamatsu", "Niigata", "Kanazawa", "Toyama", "Gifu", "Toyota", "Fukui", "Nagano"],
        "Kyushu": ["Fukuoka", "Kitakyushu", "Kumamoto", "Kagoshima", "Oita", "Nagasaki", "Miyazaki", "Kurume", "Sasebo", "Saga"],
        "Tohoku": ["Sendai", "Iwaki", "Koriyama", "Aomori", "Morioka", "Akita", "Yamagata", "Fukushima", "Hachinohe", "Hirosaki"],
        "Hokkaido": ["Sapporo", "Asahikawa", "Hakodate", "Tomakomai", "Obihiro", "Kushiro", "Ebetsu", "Otaru", "Kitami", "Muroran"],
        "Chugoku": ["Hiroshima", "Okayama", "Kurashiki", "Fukuyama", "Shimonoseki", "Kure", "Matsue", "Tottori", "Ube", "Yamaguchi"],
        "Shikoku": ["Matsuyama", "Takamatsu", "Kochi", "Tokushima", "Imabari", "Niihama", "Marugame", "Saijo", "Uwajima", "Sakaide"],
        "Okinawa": ["Naha", "Okinawa City", "Uruma", "Urasoe", "Ginowan", "Nago", "Tomigusuku", "Itoman", "Miyakojima", "Ishigaki"],
        "Shinshu": ["Nagano", "Matsumoto", "Ueda", "Iida", "Saku", "Azumino", "Chino", "Shiojiri", "Suwa", "Ina"],
    },
    "Korea": {
        "Gyeonggi": ["Suwon", "Seongnam", "Goyang", "Yongin", "Bucheon", "Ansan", "Anyang", "Hwaseong", "Pyeongtaek", "Uijeongbu"],
        "Seoul Capital": ["Seoul", "Jongno", "Gangnam", "Songpa", "Mapo", "Yeongdeungpo", "Seocho", "Yongsan", "Jung-gu", "Seongbuk"],
        "Busan Region": ["Busan", "Haeundae", "Sasang", "Saha", "Busanjin", "Dongnae", "Nam-gu", "Buk-gu", "Yeongdo", "Geumjeong"],
        "Incheon Region": ["Incheon", "Bupyeong", "Namdong", "Yeonsu", "Michuhol", "Seo-gu", "Gyeyang", "Jung-gu", "Dong-gu", "Ganghwa"],
        "Gyeongsangnam": ["Changwon", "Gimhae", "Jinju", "Yangsan", "Geoje", "Tongyeong", "Sacheon", "Miryang", "Haman", "Changnyeong"],
        "Gyeongsangbuk": ["Andong", "Pohang", "Gumi", "Gyeongju", "Gyeongsan", "Gimcheon", "Yeongju", "Sangju", "Yeongcheon", "Mungyeong"],
        "Chungcheongnam": ["Hongseong", "Cheonan", "Asan", "Seosan", "Dangjin", "Gongju", "Boryeong", "Nonsan", "Gyeryong", "Yesan"],
        "Jeollanam": ["Muan", "Yeosu", "Suncheon", "Mokpo", "Naju", "Gwangyang", "Haenam", "Goheung", "Hwasun", "Yeongam"],
        "Jeollabuk": ["Jeonju", "Iksan", "Gunsan", "Jeongeup", "Namwon", "Gimje", "Wanju", "Gochang", "Buan", "Sunchang"],
        "Gangwon": ["Chuncheon", "Wonju", "Gangneung", "Donghae", "Sokcho", "Samcheok", "Taebaek", "Hongcheon", "Hoengseong", "Pyeongchang"],
    },
    "Vietnam": {
        "Red River Delta": ["Hanoi", "Hai Phong", "Bac Ninh", "Hai Duong", "Nam Dinh", "Thai Binh", "Ninh Binh", "Hung Yen", "Phu Ly", "Vinh Yen"],
        "Southeast": ["Ho Chi Minh City", "Bien Hoa", "Vung Tau", "Thu Dau Mot", "Di An", "Thuan An", "Ba Ria", "Dong Xoai", "Tay Ninh", "Long Khanh"],
        "Mekong Delta": ["Can Tho", "Rach Gia", "Long Xuyen", "My Tho", "Ca Mau", "Soc Trang", "Bac Lieu", "Tra Vinh", "Ben Tre", "Tan An"],
        "South Central Coast": ["Da Nang", "Nha Trang", "Quy Nhon", "Phan Thiet", "Tuy Hoa", "Tam Ky", "Quang Ngai", "Phan Rang", "Cam Ranh", "Hoi An"],
        "North Central Coast": ["Hue", "Vinh", "Thanh Hoa", "Dong Hoi", "Ha Tinh", "Dong Ha", "Sam Son", "Bim Son", "Ky Anh", "Ba Don"],
        "Central Highlands": ["Pleiku", "Da Lat", "Buon Ma Thuot", "Kon Tum", "Gia Nghia", "Bao Loc", "An Khe", "Ayun Pa", "Bu Dop", "Ea Kar"],
        "Northeast": ["Ha Long", "Thai Nguyen", "Viet Tri", "Cam Pha", "Uong Bi", "Bac Giang", "Lang Son", "Tuyen Quang", "Yen Bai", "Cao Bang"],
        "Northwest": ["Dien Bien Phu", "Son La", "Hoa Binh", "Lao Cai", "Lai Chau", "Sa Pa", "Nghia Lo", "Mai Chau", "Moc Chau", "Muong Lay"],
        "Binh Dinh Coast": ["Quy Nhon", "Hoai Nhon", "An Nhon", "Phu My", "Phu Cat", "Tay Son", "Hoai An", "Van Canh", "Vinh Thanh", "Tuy Phuoc"],
        "Quang Nam": ["Tam Ky", "Nui Thanh", "Dien Ban", "Dai Loc", "Duy Xuyen", "Thang Binh", "Que Son", "Tien Phuoc", "Bac Tra My", "Nam Tra My"],
    },
    "Britain": {
        "Greater London": ["London", "Westminster", "Camden", "Greenwich", "Kensington", "Croydon", "Bromley", "Islington", "Hackney", "Southwark"],
        "South East": ["Guildford", "Brighton", "Oxford", "Southampton", "Portsmouth", "Reading", "Milton Keynes", "Slough", "Canterbury", "Winchester"],
        "North West": ["Manchester", "Liverpool", "Bolton", "Warrington", "Preston", "Blackpool", "Chester", "Salford", "Stockport", "Blackburn"],
        "West Midlands": ["Birmingham", "Coventry", "Wolverhampton", "Solihull", "Stoke-on-Trent", "Dudley", "Walsall", "Telford", "Worcester", "Hereford"],
        "Yorkshire": ["Leeds", "Sheffield", "Bradford", "York", "Hull", "Huddersfield", "Doncaster", "Rotherham", "Wakefield", "Harrogate"],
        "Scotland": ["Edinburgh", "Glasgow", "Aberdeen", "Dundee", "Inverness", "Stirling", "Perth", "Paisley", "East Kilbride", "Dunfermline"],
        "South West": ["Bristol", "Plymouth", "Exeter", "Bournemouth", "Gloucester", "Cheltenham", "Bath", "Swindon", "Torquay", "Salisbury"],
        "East Midlands": ["Nottingham", "Leicester", "Derby", "Northampton", "Lincoln", "Chesterfield", "Mansfield", "Loughborough", "Kettering", "Corby"],
        "Wales": ["Cardiff", "Swansea", "Newport", "Wrexham", "Bangor", "Barry", "Neath", "Cwmbran", "Llanelli", "Bridgend"],
        "North East": ["Newcastle", "Sunderland", "Middlesbrough", "Durham", "Darlington", "Gateshead", "Hartlepool", "South Shields", "Stockton-on-Tees", "Tynemouth"],
    },
    "France": {
        "Île-de-France": ["Paris", "Boulogne-Billancourt", "Saint-Denis", "Argenteuil", "Montreuil", "Nanterre", "Créteil", "Versailles", "Courbevoie", "Vitry-sur-Seine"],
        "Auvergne-Rhône-Alpes": ["Lyon", "Saint-Étienne", "Grenoble", "Villeurbanne", "Clermont-Ferrand", "Annecy", "Chambéry", "Vénissieux", "Valence", "Vaulx-en-Velin"],
        "Provence-Alpes-Côte d'Azur": ["Marseille", "Nice", "Toulon", "Aix-en-Provence", "Avignon", "Cannes", "Antibes", "La Seyne-sur-Mer", "Hyères", "Arles"],
        "Occitanie": ["Toulouse", "Montpellier", "Nîmes", "Perpignan", "Béziers", "Montauban", "Narbonne", "Albi", "Carcassonne", "Sète"],
        "Nouvelle-Aquitaine": ["Bordeaux", "Limoges", "Poitiers", "Pau", "La Rochelle", "Mérignac", "Pessac", "Bayonne", "Angoulême", "Agen"],
        "Hauts-de-France": ["Lille", "Amiens", "Roubaix", "Tourcoing", "Dunkirk", "Calais", "Villeneuve-d'Ascq", "Saint-Quentin", "Beauvais", "Valenciennes"],
        "Grand Est": ["Strasbourg", "Reims", "Metz", "Mulhouse", "Nancy", "Colmar", "Troyes", "Charleville-Mézières", "Châlons-en-Champagne", "Thionville"],
        "Pays de la Loire": ["Nantes", "Angers", "Le Mans", "Saint-Nazaire", "Cholet", "La Roche-sur-Yon", "Laval", "Saint-Herblain", "Rezé", "Saumur"],
        "Brittany": ["Rennes", "Brest", "Quimper", "Lorient", "Vannes", "Saint-Malo", "Saint-Brieuc", "Lanester", "Fougères", "Concarneau"],
        "Normandy": ["Rouen", "Le Havre", "Caen", "Cherbourg", "Évreux", "Dieppe", "Sotteville-lès-Rouen", "Saint-Étienne-du-Rouvray", "Alençon", "Vernon"],
    },
    "Germany": {
        "Bavaria": ["Munich", "Nuremberg", "Augsburg", "Regensburg", "Ingolstadt", "Würzburg", "Fürth", "Erlangen", "Bamberg", "Bayreuth"],
        "North Rhine-Westphalia": ["Düsseldorf", "Cologne", "Dortmund", "Essen", "Duisburg", "Bochum", "Wuppertal", "Bielefeld", "Bonn", "Münster"],
        "Baden-Württemberg": ["Stuttgart", "Mannheim", "Karlsruhe", "Freiburg", "Heidelberg", "Heilbronn", "Ulm", "Pforzheim", "Reutlingen", "Esslingen"],
        "Lower Saxony": ["Hanover", "Braunschweig", "Oldenburg", "Osnabrück", "Wolfsburg", "Göttingen", "Salzgitter", "Hildesheim", "Delmenhorst", "Wilhelmshaven"],
        "Hesse": ["Wiesbaden", "Frankfurt", "Kassel", "Darmstadt", "Offenbach", "Hanau", "Gießen", "Marburg", "Fulda", "Rüsselsheim"],
        "Saxony": ["Dresden", "Leipzig", "Chemnitz", "Zwickau", "Plauen", "Görlitz", "Freiberg", "Bautzen", "Pirna", "Freital"],
        "Berlin-Brandenburg": ["Berlin", "Potsdam", "Cottbus", "Brandenburg an der Havel", "Frankfurt an der Oder", "Oranienburg", "Falkensee", "Eberswalde", "Bernau", "Königs Wusterhausen"],
        "Hamburg Region": ["Hamburg", "Altona", "Bergedorf", "Harburg", "Wandsbek", "Eimsbüttel", "Norderstedt", "Ahrensburg", "Wedel", "Pinneberg"],
        "Rhineland-Palatinate": ["Mainz", "Ludwigshafen", "Koblenz", "Trier", "Kaiserslautern", "Worms", "Neuwied", "Neustadt", "Speyer", "Bad Kreuznach"],
        "Schleswig-Holstein": ["Kiel", "Lübeck", "Flensburg", "Neumünster", "Norderstedt", "Elmshorn", "Pinneberg", "Itzehoe", "Wedel", "Rendsburg"],
    },
    "Italy": {
        "Lombardy": ["Milan", "Brescia", "Monza", "Bergamo", "Busto Arsizio", "Como", "Sesto San Giovanni", "Varese", "Cinisello Balsamo", "Pavia"],
        "Lazio": ["Rome", "Latina", "Guidonia Montecelio", "Fiumicino", "Aprilia", "Viterbo", "Pomezia", "Tivoli", "Anzio", "Velletri"],
        "Campania": ["Naples", "Salerno", "Giugliano in Campania", "Torre del Greco", "Pozzuoli", "Casoria", "Caserta", "Castellammare di Stabia", "Afragola", "Benevento"],
        "Veneto": ["Venice", "Verona", "Padua", "Vicenza", "Treviso", "Rovigo", "Chioggia", "Bassano del Grappa", "San Donà di Piave", "Schio"],
        "Sicily": ["Palermo", "Catania", "Messina", "Syracuse", "Marsala", "Gela", "Ragusa", "Trapani", "Caltanissetta", "Agrigento"],
        "Emilia-Romagna": ["Bologna", "Parma", "Modena", "Reggio Emilia", "Ravenna", "Rimini", "Ferrara", "Forlì", "Piacenza", "Cesena"],
        "Piedmont": ["Turin", "Novara", "Alessandria", "Asti", "Moncalieri", "Cuneo", "Collegno", "Rivoli", "Vercelli", "Biella"],
        "Tuscany": ["Florence", "Prato", "Livorno", "Arezzo", "Pistoia", "Pisa", "Lucca", "Grosseto", "Massa", "Carrara"],
        "Apulia": ["Bari", "Taranto", "Foggia", "Andria", "Lecce", "Barletta", "Brindisi", "Altamura", "Molfetta", "Cerignola"],
        "Liguria": ["Genoa", "La Spezia", "Savona", "Sanremo", "Imperia", "Rapallo", "Chiavari", "Ventimiglia", "Albenga", "Sarzana"],
    },
    "Spain": {
        "Madrid": ["Madrid", "Móstoles", "Alcalá de Henares", "Fuenlabrada", "Leganés", "Getafe", "Alcorcón", "Torrejón de Ardoz", "Parla", "Alcobendas"],
        "Catalonia": ["Barcelona", "L'Hospitalet de Llobregat", "Badalona", "Terrassa", "Sabadell", "Lleida", "Tarragona", "Mataró", "Santa Coloma de Gramenet", "Reus"],
        "Andalusia": ["Seville", "Málaga", "Córdoba", "Granada", "Jerez de la Frontera", "Almería", "Huelva", "Marbella", "Dos Hermanas", "Algeciras"],
        "Valencia": ["Valencia", "Alicante", "Elche", "Castellón de la Plana", "Torrevieja", "Orihuela", "Gandia", "Torrent", "Benidorm", "Sagunto"],
        "Galicia": ["Santiago de Compostela", "Vigo", "A Coruña", "Ourense", "Lugo", "Pontevedra", "Ferrol", "Vilagarcía de Arousa", "Narón", "Oleiros"],
        "Castile and León": ["Valladolid", "Burgos", "Salamanca", "León", "Palencia", "Ponferrada", "Zamora", "Segovia", "Ávila", "Soria"],
        "Basque Country": ["Vitoria-Gasteiz", "Bilbao", "San Sebastián", "Barakaldo", "Getxo", "Irun", "Portugalete", "Santurtzi", "Basauri", "Errenteria"],
        "Canary Islands": ["Santa Cruz de Tenerife", "Las Palmas", "San Cristóbal de La Laguna", "Telde", "Arona", "Santa Lucía de Tirajana", "Arrecife", "San Bartolomé de Tirajana", "Granadilla de Abona", "Adeje"],
        "Castilla-La Mancha": ["Toledo", "Albacete", "Talavera de la Reina", "Guadalajara", "Ciudad Real", "Cuenca", "Puertollano", "Tomelloso", "Azuqueca de Henares", "Alcázar de San Juan"],
        "Aragon": ["Zaragoza", "Huesca", "Teruel", "Calatayud", "Utebo", "Monzón", "Barbastro", "Ejea de los Caballeros", "Alcañiz", "Fraga"],
    },
}

# Aliases for flexibility
GLOBAL_NATION_DATA["US"] = GLOBAL_NATION_DATA["United States"]
GLOBAL_NATION_DATA["UK"] = GLOBAL_NATION_DATA["Britain"]
GLOBAL_NATION_DATA["South Korea"] = GLOBAL_NATION_DATA["Korea"]

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


# -----------------------------------------------------------------------------
# 50 Authentic Real-World Land Plot / Estate / Manorial Names for Each Country
# -----------------------------------------------------------------------------
COUNTRY_PLOT_NAMES = {
    "United States": [
        "Shenandoah Valley Bottomland", "Black Belt Cotton Bottom", "Chesapeake Bay Meadow", "Bluegrass Pasture",
        "Piney Woods Tract", "Piedmont Arable Parcel", "Delta Alluvial Acreage", "Red River Bottoms",
        "Appalachian Ridge Parcel", "Flint Hills Grazing Range", "Susquehanna Flats", "Hudson Valley Orchard Lot",
        "Great Plains Homestead Tract", "Willamette Prairie Strip", "Snake River Lowlands", "Cumberland Gap Pasture",
        "San Joaquin Orchard Parcel", "Ozark Plateau Clearance", "Wabash River Bottomland", "Suwannee River Hammock",
        "Connecticut River Meadow", "Platte River Grazing Range", "Sonoma Valley Vine Row", "Brazos River Farmstead",
        "Green Mountain Pasture", "Adirondack Timber Lot", "Genesee Valley Wheatfield", "Napa Valley Benchland",
        "Sacramento Delta Polder", "Everglades Muck Farm", "Smoky Mountain Hollow", "Tidewater Tobacco Strip",
        "Bitterroot Valley Run", "Blue Ridge Apple Orchard", "Santee River Swamp Field", "Black Hills Meadow",
        "Rio Grande Bosque Lot", "Columbia River Terrace", "Mohawk Valley Furrow", "Ouachita Forest Clearing",
        "Yazoo Basin Cotton Field", "Baraboo Hills Ridge Lot", "Palouse Wheat Hills", "St. Johns River Pasture",
        "Big Horn Basin Range", "Chattahoochee Bottoms", "Pecan Bayou Pasture", "Licking River Flats",
        "Monongahela Coal & Cornfield", "Cache Valley Grain Run"
    ],
    "Britain": [
        "Foxcover Wood & Pasture", "St. Jude's Common Strip", "Highfield Arable Run", "Blackwood Copse",
        "Moorland Sheep Run", "Bramble Bank Meadow", "Gallows Hill Pasture", "Abbey Grange Acreage",
        "Windmill Hill Allotment", "Kingswood Waste", "Willowbrook Hayfield", "Low Dike Enclosure",
        "Priory Glebe", "Thistledown Common", "Barley Hill Strip", "Foxglove Meadow",
        "Briar Ridge Pasture", "St. Mary's Tithe Ground", "Harrowgate Open Field", "Westcot Common Fen",
        "Cotswold Sheep Walk", "Dover Chalk Downland", "Avon River Mead", "Severn Vale Orchard",
        "Chiltern Beech Copse", "Peak District Grazing Common", "New Forest Heather Waste", "Dartmoor Granite Run",
        "Somerset Levels Fenland", "Weald Clay Furrow", "Yorkshire Dales Intack", "Northumberland Border Peat",
        "Wensleydale Meadow Pasture", "Exmoor Heather Run", "Cumbria Fellside Intake", "Lothian Wheat Rig",
        "Fife Coastal Allotment", "Tweed River Bottomland", "Grampian Strath Field", "Highland Glen Croft",
        "Ceredigion Hill Pasture", "Gower Peninsula Field", "Snowdonia Slate Run", "Brecon Beacons Grazing",
        "Anglesey Common Ground", "Rannoch Moor Heather Lot", "Cotswold Stone Quarry Field", "Wessex Downland Fold",
        "East Anglian Ditch Parcel", "Thames Valley Watermeadow"
    ],
    "France": [
        "Le Grand Domaine de Beauce", "Clos de l'Abbaye", "Pâturage des Bruyères", "Terre Sainte-Marie",
        "Le Moulin d'Eau", "Champ des Alouettes", "Bocage Normand", "Vignoble du Coteau",
        "Métairie Basse", "Pré Saint-Jean", "Clairière des Loups", "Domaine de la Garenne",
        "Fief de Montmirail", "Grange de Cîteaux", "Terres Communes du Val", "Parcelle du Chêne Liège",
        "Vigne des Papes", "Prairie de la Loire", "Coteaux de Gascogne", "Plaine de Brie",
        "Pâtis de Sologne", "Clos des Bénédictins", "Grande Cour de Normandie", "Lande Bretonne",
        "Basse-Cour du Manoir", "Champ Saint-Martin", "Verger d'Anjou", "Terre Noire d'Alsace",
        "Mas de la Garrigue", "Causse du Larzac", "Alpage du Beaufortain", "Jardin du Bailli",
        "Bocage Vendéen", "Châtaigneraie Cévenole", "Pâturage du Jura", "Marais Poitevin",
        "Combe aux Fées", "Enclos du Meunier", "Ferme des Tournesols", "Coteau du Roussillon",
        "Terre Fief de Bourgogne", "Olivette de Provence", "Vignoble de Saint-Émilion", "Plaine du Camargue",
        "Ferme de Bellevue", "Clairière d'Argonne", "Pâturage des Vosges", "Garenne du Baron",
        "Vallée de la Dordogne", "Grande Métairie d'Armagnac"
    ],
    "Germany": [
        "Rittergut Hohenlohe", "Klostergut Maulbronn", "Schwarzwald Weide", "Odenwald Acker",
        "Allmende Grünfeld", "Lindenhof Flur", "Birkenau Parzelle", "Königsforst Rodung",
        "Mühlental Wiese", "Klostermark Flurgang", "Falkenstein Gutshof", "Rebenhang Flur",
        "Heidewiese Allmende", "Sonnenberg Ackerbau", "Alpenvorland Weidegrund", "Lüneburger Heidekoppel",
        "Rheingau Weinparzelle", "Thüringer Becken Scholle", "Harzvorland Flurstück", "Spessart Eichenwaldung",
        "Moseltal Steillage", "Uckermark Weizenfeld", "Spreewald Fließanger", "Oberpfälzer Waldweide",
        "Teutoburger Waldparzelle", "Holsteiner Marschkoppel", "Schwäbische Alb Weide", "Fränkischer Weinberg",
        "Erzgebirge Bergwiese", "Bayerischer Wald Schlag", "Weserbergland Acker", "Taunus Hangwiese",
        "Münsterland Wallhecke", "Niederbayern Hopfengarten", "Brandenburger Sandacker", "Saarbrücker Rodungsland",
        "Pfalz Mandelhain", "Dithmarschen Kohlfeld", "Wetterau Schwarzerde", "Hunsrück Höhenweide",
        "Vogelsberg Basaltwiese", "Altmark Rinderweide", "Mecklenburger Seenacker", "Bodensee Obstgarten",
        "Ruhrwiese Allmende", "Würzburger Stein Parzelle", "Lausitzer Kiefernheide", "Bergisches Land Wiesental",
        "Siegerland Hauberg", "Allgäuer Käsereialm"
    ],
    "Spain": [
        "Dehesa de San Jerónimo", "Cortijo del Roble", "Hacienda La Purísima", "Vega del Guadalquivir",
        "Pasto de los Encinos", "Tierras del Marqués", "Comunal de la Sierra", "Huerta de San Pedro",
        "Finca Las Encinas", "Pasadizo de la Mesta", "Heredad Santa Ana", "Coto de San Juan",
        "Majada de las Ovejas", "Olivar de Santa Cruz", "Vega de Granada", "Campiña de Córdoba",
        "Dehesa Extremeña", "Secano de Castilla", "Viñedo de La Rioja", "Pinar de Soria",
        "Huerta Murciana", "Albufera Arroceira", "Dehesa de Salamanca", "Robledal de Cantabria",
        "Llanura de La Mancha", "Finca El Almendral", "Cortijo de la Serranía", "Monte Común de Galicia",
        "Pastizal de los Picos", "Pinar del Guadarrama", "Pago de Jerez", "Vega de Antequera",
        "Viña del Penedès", "Arrozal del Delta del Ebro", "Coto de Doñana", "Campiña Sevillana",
        "Rasa Costera Asturiana", "Valle del Jerte", "Vega de Aranjuez", "Dehesa de Monfragüe",
        "Territorio de la Mesta", "Majada de Gredos", "Soto del Henares", "Paraje de Cazorla",
        "Camino Real de Toledo", "Finca La Dehesilla", "Cortijo de San Fernando", "Tierras de Al-Ándalus",
        "Viñedo de Valdepeñas", "Bocage Gallego"
    ],
    "Italy": [
        "Cascina San Martino", "Podere Bellaria", "Tenuta dei Cipressi", "Masseria San Domenico",
        "Feudo di Santa Chiara", "Terre dei Monaci", "Pascolo della Majella", "Vigna Nuova del Vescovo",
        "Casale di Montefalco", "Fattoria della Pieve", "Campagna di Val d'Orcia", "Borgo San Lorenzo",
        "Prato dei Mulini", "Risaia del Vercellese", "Maremma Bonificata", "Uliveto del Chianti",
        "Limonaia di Sorrento", "Casale della Spiga", "Tenuta di San Guido", "Masseria delle Murge",
        "Campi Flegrei", "Piana di Catania", "Agro Pontino", "Corte Benedettina",
        "Vigneto delle Langhe", "Malga delle Dolomiti", "Colline del Prosecco", "Bosco di San Francesco",
        "Tenuta Farnese", "Podere La Querce", "Fattoria di Volpaia", "Pianura Padana Allodola",
        "Vigna del Barolo", "Ortale di Palermo", "Feudo dei Principi", "Pascolo del Gran Sasso",
        "Tenuta Castel del Monte", "Uliveto di Bitonto", "Corte Lombarda", "Risaia di Lomellina",
        "Prato delle Fonti", "Tenuta Ca' Vendramin", "Borgo dei Vigneti", "Casale San Gimignano",
        "Masseria Salentina", "Poggio alle Mura", "Tenuta di Pomino", "Valle dei Templi Terreno",
        "Coltivo delle Cinque Terre", "Alpeggio di Valtellina"
    ],
    "China": [
        "西溪水稻田", "青龙山梯田", "枫树下桑基鱼塘", "龙井茶园地",
        "云雾山牧场", "白鹭洲官田", "黄土坡旱作田", "杨柳岸草场",
        "灵芝山桑田", "松风岭桑梓地", "碧玉泉农庄", "翠竹冈公田",
        "赤壁棉花坡", "黑龙湾麦垄", "太湖芦苇滩", "九龙岗贡米田",
        "落霞坡菜圃", "紫金山果林", "武夷岩茶垄", "洞庭湖淤泥田",
        "雁荡山石斛谷", "凤凰台棉田", "泰山下老农庄", "天山苜蓿牧场",
        "大巴山油菜垄", "武当药草谷", "都江堰灌区田", "鄱阳湖早稻埒",
        "长白山人参垄", "河套平原玉米地", "吐鲁番葡萄园", "祁连山山麓草场",
        "武陵桃花源垄", "巴山夜雨茶园", "峨眉竹笋林", "淮河水乡菱角塘",
        "雷州半岛甘蔗坡", "崇明东滩荡地", "安阳殷墟黍麦地", "平遥老槐树田",
        "曲阜孔府圣田", "绍兴鉴湖水稻地", "徽州梯田油菜坂", "乌镇桑蚕圃",
        "景德镇瓷土林山", "香格里拉青稞垄", "桂林阳朔禾田", "黄山松烟茶垄",
        "衡山祝融贡稻坂", "泰和乌鸡竹林坡"
    ],
    "Japan": [
        "大野庄水田", "松風牧場", "白川荘園", "桜ヶ丘草地",
        "美山御料地", "吉野川菜園", "青柳草刈場", "稲荷山開拓地",
        "鹿野苑牧野", "千代田田園", "高天原農園", "日向牧草地",
        "秋津洲麦畑", "八雲開墾地", "富士裾野牧場", "筑波山麓水田",
        "近江八幡水郷畑", "阿苏カルデラ牧野", "信濃追分菜園", "丹波黒豆圃場",
        "越後平野米どころ", "出雲神苑御神田", "伊勢神宮神饌田", "庄内平野稲穂坂",
        "会津盆地酒米田", "十勝平野大豆畑", "石狩川泥炭干拓地", "那須野が原放牧地",
        "安曇野わさび沢", "木曽谷ヒノキ山林", "飛騨高山蕎麦畑", "播磨平野山田錦圃",
        "土佐湾段々畑", "讃岐平野溜池田", "宇治茶園茶畑", "狭山茶丘陵地",
        "八ヶ岳山麓開拓畑", "津軽平野林檎園", "南部曲家放牧野", "宮崎都城牛放牧地",
        "知多半島みかん園", "甲州葡萄棚園", "三方原茶畑台地", "日高サラブレッド牧場",
        "天竜川扇状地水田", "能登棚田白米千枚田", "熊野古道杉木立畑", "佐渡金山御料林",
        "吉野桜山下草刈場", "屋久杉山林保護地"
    ],
    "India": [
        "Ganga Terai Alluvium", "Vindhya Pasture Lands", "Malwa Black Soil Holding", "Doab Arable Tract",
        "Rohilkhand Sugar Acres", "Deccan Grazing Run", "Kaveri Delta Paddy Plot", "Brahmaputra Char Holding",
        "Chhotanagpur Upland Plot", "Konkan Coconut Grove", "Punjab Canal Colony Lot", "Sundarbans Bheri Plot",
        "Kashmir Saffron Field", "Awadh Sugarcane Allotment", "Coromandel Coastal Meadow", "Thar Desert Oasis Pasture",
        "Bundelkhand Stony Furrow", "Kerala Spice Garden", "Assam Tea Plantation Strip", "Gujarat Cotton Blacksoil",
        "Odisha Mahanadi Basin", "Mysore Silk Mulberry Plot", "Dharwad Cotton Acreage", "Telangana Redsoil Farm",
        "Marathwada Bajra Field", "Coorg Coffee Estate", "Nilgiri Tea Terrace", "Haryana Basmati Strip",
        "Chambal Ravine Grazing", "Bastar Forest Clearing", "Vidarbha Orange Grove", "Rann Cattle Grazing Banni",
        "Garhwal Terrace Farm", "Kumaon Apple Orchard", "Ladakh Barley Patch", "Darbhanga Mango Orchard",
        "Malabar Pepper Garden", "Raichur Doab Paddy Field", "Jharkhand Sal Forest Edge", "Kutch Grazing Commons",
        "Goan Khazan Land", "Narmada Alluvial Strip", "Godavari Delta Richfield", "Tirunelveli Palmyra Grove",
        "Shimla Apple Ridge", "Anamalai Cardamom Tract", "Bhojpur Wheat Basin", "Saurashtra Groundnut Farm",
        "Warangal Chilli Acres", "Guntur Mirchi Holding"
    ],
    "Indonesia": [
        "Sawah Subak Betutu", "Ladang Jagung Merapi", "Kebun Karet Bukit Barisan", "Padang Rumput Sumba",
        "Tanah Ulayat Minangkabau", "Sawah Terasering Jatiluwih", "Kebun Kelapa Sawit Riau", "Tegalan Gunung Slamet",
        "Tanah Kas Desa Cirebon", "Hutan Lindung Tengger", "Kebun Kopi Gayo", "Sawah Surjan Kulon Progo",
        "Kebun Teh Puncak", "Kebun Cengkeh Maluku", "Ladang Berpindah Dayak", "Sawah Lebak Palembang",
        "Tambak Bandeng Gresik", "Padang Gembala Toraja", "Kebun Tembakau Deli", "Kebun Pala Banda",
        "Tanah Bengkok Banyumas", "Ladang Ubi Jayawijaya", "Hutan Damar Krui", "Sawah Pasang Surut Barito",
        "Kebun Vanili Flores", "Ladang Sagu Asmat", "Perkebunan Lada Lampung", "Sawah Bawah Gunung Bromo",
        "Kebun Kakao Luwu", "Tanah Adat Baduy", "Kebun Kopi Toraja", "Hutan Jati Cepu",
        "Sawah Terasering Ubud", "Kebun Kelapa Tomohon", "Ladang Garam Madura", "Kebun Sawit Asahan",
        "Tambak Garam Rembang", "Padang Savana Baluran", "Kebun Jagung Madura", "Kebun Jeruk Berastagi",
        "Sawah Tadah Hujan Gunungkidul", "Perkebunan Kina Pengalengan", "Kebun Kopi Ijen", "Tanah Margasari Bali",
        "Sawah Rawa Banjarmasin", "Ladang Bawang Brebes", "Hutan Bakau Teluk Bintuni", "Kebun Sawit Minahasa",
        "Padang Rumput Timor", "Perkebunan Tebu Kediri"
    ],
    "Brazil": [
        "Fazenda Santa Gertrudes", "Engenho Real das Alagoas", "Pasto do Pantanal", "Sítio Primavera",
        "Roça de Mandioca Paraopeba", "Estância do Pampa", "Gleba Esperança", "Sertão da Canastra",
        "Chácara Boa Vista", "Pasto das Sete Lagoas", "Cafezal do Vale do Paraíba", "Seringal do Acre",
        "Cacaueiro de Ilhéus", "Fazenda Chapadão do Céu", "Invernada dos Pampas", "Engenho Massangana",
        "Roça Quilombola do Frechal", "Plantação de Soja do Cerrado", "Pasto de Nelore Uberaba", "Terra Roxa de Ribeirão Preto",
        "Canavial de Piracicaba", "Fazenda Pau D'Alho", "Sítio do Pica-Pau Amarelo", "Castanhal do Pará",
        "Estância da Fronteira", "Pasto do Araguaia", "Gleba Mutum", "Lavoura de Trigo de Passo Fundo",
        "Roça Caipira do Tietê", "Paragem dos Bandeirantes", "Engenho da Rainha", "Sítio Santo Antônio",
        "Fazenda Morro Agudo", "Terras de Babaçu Maranhão", "Laranjal de Bebedouro", "Pomar de Maçã de São Joaquim",
        "Cafezal da Mogiana", "Pasto da Nhecolândia", "Mandiocal do Xingu", "Terras Tradicionais Caiçaras",
        "Estância Minuano", "Fazenda Vista Alegre", "Plantação de Algodão do Oeste Baiano", "Canavial da Zona da Mata",
        "Roça das Vertentes", "Pasto de Capim Colonião", "Sítio Bela Manhã", "Engenho São João",
        "Colônia Witmarsum", "Pasto do Vale do Guaporé"
    ],
    "Mexico": [
        "Hacienda San Gabriel", "Ejido Emiliano Zapata", "Rancho El Olivo", "Potrero de San Miguel",
        "Tierras Comunales de Oaxaca", "Milpa de San Cristóbal", "Agave Real de Tequila", "Huerta de Uruapan",
        "Valle de Tehuacán Parcela", "Rancho La Purísima", "Hacienda de Chiconcuac", "Ejido El Fuerte",
        "Chinampa de Xochimilco", "Potrero de la Huasteca", "Hacienda de Santa Mónica", "Milpa Alta Solar",
        "Cafetal de Coatepec", "Rancho La Herradura", "Hacienda Henequenera Yaxcopoil", "Ejido Nueva Rosita",
        "Potrero del Bajío", "Huerta de Nogal Parras", "Tierra Ejidal de Tlaxcala", "Rancho Tres Potrillos",
        "Hacienda de Guadalupe", "Valles Centrales Parcela", "Milpa de la Sierra Tarahumara", "Platanar de Tabasco",
        "Potrero del Yaqui", "Hacienda San Francisco", "Viñedo de Valle de Guadalupe", "Tierras del Mayo",
        "Rancho El Encino", "Cafetal de Soconusco", "Algodonal de La Laguna", "Hacienda de San Mateo",
        "Ejido San Juan de las Huertas", "Potrero de la Mixteca", "Huerta de Mango Costa Chica", "Rancho El Mezquite",
        "Hacienda Soltepec", "Milpa Mazahua", "Tierras Purépechas", "Potrero de Apatzingán",
        "Hacienda de Cocoyoc", "Ejido Valle de Mexicali", "Rancho San Cayetano", "Hacienda de Cortés",
        "Milpa de Tepoztlán", "Potrero de Cuatro Ciénegas"
    ],
    "Nigeria": [
        "Ogun River Farmland", "Zaria Grain Plain", "Kano Groundnut Pyramid Plot", "Niger Delta Mangrove Farm",
        "Jos Plateau Grazing Range", "Oyo Yam Basin", "Benue River Floodplain", "Enugu Palm Plantation",
        "Sokoto Rima Pasture", "Calabar Cocoa Holding", "Ibadan Cassava Plantation", "Bida Rice Paddies",
        "Kaduna Ginger Field", "Oshogbo Sacred Forest Border", "Hadejia River Valley Farm", "Anambra River Basin Plot",
        "Benin Rubber Estate", "Cross River Oil Palm Estate", "Katsina Cotton Farm", "Adamawa Cattle Ranch",
        "Taraba Tea Estate", "Ekiti Cocoa Grove", "Kwara Sugar Estate", "Abeokuta Kola Nut Farm",
        "Yobe Millet Strip", "Borno Sorghum Plain", "Ondo Timber Reserve", "Kebbi Rice Polder",
        "Bauchi Cattle Run", "Ilorin Yam Farm", "Abakaliki Rice Bowl", "Gombe Cotton Basin",
        "Kogi Cashew Plantation", "Delta Cassava Acreage", "Zamfara Sorghum Field", "Plateau Potato Acres",
        "Owerri Palm Grove", "Nasarawa Sesame Field", "Warri Plantain Holding", "Sapele Rubber Plantation",
        "Lokoja Confluence Farm", "Argungu Fishing Grounds Farm", "Ijebu Cassava Farm", "Badagry Coconut Strip",
        "Epe Fishery & Farmstead", "Obudu Cattle Ranch Acreage", "Uyo Palm Belt Plot", "Afikpo Rice Terrace",
        "Zuru Onion Farm", "Biu Plateau Grain Terrace"
    ],
    "Pakistan": [
        "Indus Basin Canal Colony", "Chenab Wheat Plain", "Jhelum River Terrace", "Potohar Barani Land",
        "Thal Desert Pasture", "Bannu Agricultural Basin", "Peshawar Valley Orchard", "Cholistan Grazing Tract",
        "Kirthar Range Pasture", "Sindh Cotton Field", "Faisalabad Agricultural Block", "Sargodha Citrus Grove",
        "Multan Mango Orchard", "Okara Dairy Pasture", "Swat Valley Fruit Orchard", "Hunza Terraced Apricot Farm",
        "Sialkot Rice Paddock", "Bahawalpur Cotton Tract", "Gujranwala Guava Grove", "Mirpur Khas Mango Garden",
        "Sukkur Date Palm Grove", "Larkana Guava Orchard", "Chaman Apple Orchard", "Quetta Vineyard Strip",
        "Dera Ismail Khan Date Farm", "Mardan Sugarcane Holding", "Chiniot Shisham Timber Plot", "Kasur Fodder Field",
        "Sahiwal Cattle Grazing Land", "Attock Groundnut Acres", "Mianwali Gram Farm", "Hyderabad Cotton Estate",
        "Zhob Valley Almond Orchard", "Makran Date Oasis", "Gilgit Valley Walnut Grove", "Skardu Buckwheat Plot",
        "Nawabshah Banana Field", "Badin Sunflower Plot", "Thatta Sugarcane Basin", "Dadu Wheat Field",
        "Harnai Cumin Acreage", "Dir Timber Terrace", "Chitral Mulberry Terrace", "Sheikhupura Basmati Field",
        "Muzaffargarh Wheat Strip", "Khanewal Cotton Holding", "Toba Tek Singh Citrus Acre", "Vehari Grain Basin",
        "Rahim Yar Khan Sugar Acres", "Nowshera Tobacco Field"
    ],
    "Bangladesh": [
        "Padma Chhor Alluvial Land", "Sylhet Tea Garden Terrace", "Haor Basin Boro Plot", "Meghna Deltaic Farmland",
        "Barendra Tract Arable Field", "Chittagong Hill Tracts Jhum", "Madrasa Waqf Waqf Land", "Kushtia Tobacco Field",
        "Dinajpur Paddy Acreage", "Sundarbans Border Fishery", "Jamuna River Sandbar Farm", "Bogra Vegetable Allotment",
        "Mymensingh Fish Pond & Field", "Jessore Date Palm Sugar Grove", "Rangpur Tobacco Farm", "Comilla Co-op Vegetable Field",
        "Barisal Guava Floating Orchard", "Noakhali Saline Paddy Plot", "Cox's Bazar Betel Leaf Farm", "Tangail Mulberry Farm",
        "Faridpur Jute Basin", "Rajshahi Mango Orchard", "Pabna Milk Shed Pasture", "Sirajganj Cattle Sandbar",
        "Brahmanbaria Paddy Field", "Sunamganj Deep Haor Land", "Moulvibazar Rubber Estate", "Sreemangal Pineapple Hill",
        "Khulna Coconut Belt", "Satkhira Shrimp Gher & Field", "Patuakhali Coastal Polder", "Bhola Island Silt Flat",
        "Sherpur Rice Terrace", "Netrokona Boro Depression", "Natore Sugarcane Plantation", "Joypurhat Potato Field",
        "Chuadanga Corn Basin", "Manikganj Mustard Field", "Munshiganj Potato Polder", "Gazipur Jackfruit Orchard",
        "Chandpur Hilsa Basin Farm", "Kishoreganj Haor Alluvial Strip", "Meherpur Mango Garden", "Gopalganj Marshy Paddy",
        "Pirojpur Betel Nut Grove", "Thakurgaon Sugarcane Zone", "Kurigram Brahmaputra Char", "Bandarban Jhum Rice Slope",
        "Khagrachhari Pineapple Hill", "Rangamati Orange Orchard"
    ],
    "Russia": [
        "Chernozem Grain Tract", "Volga Steppe Grazing", "Kuban Black Earth Field", "Oka River Bottoms",
        "Siberian Taiga Clearing", "Don River Meadow", "Valdai Hills Pasture", "Altai Foothill Pasture",
        "Smolensk Flax Allotment", "Ryazan Arable Strip", "Stavropol Wheat Plain", "Krasnodar Sunflower Field",
        "Voronezh Black Soil Furrow", "Tambov Grain Estate", "Rostov Steppe Holding", "Kursk Magnetic Soil Tract",
        "Belgorod Chalk Pasture", "Tula Gingerbread Rye Farm", "Pskov Flax Field", "Novgorod Haymeadow",
        "Vologda Dairy Pasture", "Kostroma Timber Clearance", "Yaroslavl Volga Terrace", "Tver Birch Forest Plot",
        "Vladimir Meadowland", "Orenburg Steppe Ranch", "Bashkir Honey Forest Plot", "Tatarstan Black Soil Farm",
        "Saratov Grain Steppe", "Samara Bend Wheatfield", "Ural Mountain Valley Acreage", "West Siberian Rye Plain",
        "Tomsk River Alluvium", "Krasnoyarsk Yenisei Terrace", "Irkutsk Baikal Pasture", "Amur River Soybean Flat",
        "Primorsky Rice Polder", "Kamchatka Volcanic Valley", "Karelia Rocky Meadow", "Arkhangelsk Northern Pasture",
        "Chuvash Hop Garden", "Mordovia Forest Edge Farm", "Kaluga Rye Field", "Lipetsk Orchard Tract",
        "Bryansk Forest Clearing", "Kemerovo Foothill Meadow", "Khhakassia Steppe Run", "Buryatia Grazing Valley",
        "Dagestan Mountain Terrace", "Crimean Vine Slope"
    ],
    "Korea": [
        "Honam Plain Rice Field", "Yeongnam Basin Orchard", "Gangwon Alpine Pasture", "Han River Delta Farm",
        "Naju Pear Orchard", "Gimje Alluvial Flat", "Andong Hemp Field", "Paju Arable Terrace",
        "Jejudo Basalt Pasture", "Chungju Apple Orchard", "Sangju Persimmon Hill", "Boseong Green Tea Terrace",
        "Iksan Granary Basin", "Gyeongju Ancient Royal Field", "Seosan Reclaimed Rice Land", "Haenam Sweet Potato Acre",
        "Yeongam Radish Basin", "Mungyeong Schisandra Farm", "Cheongyang Chilli Pepper Terrace", "Pyeongchang Highland Cabbage Field",
        "Daegwallyeong Sheep Ranch", "Chuncheon Buckwheat Flat", "Wonju Corn Valley", "Gangneung Pine Forest Edge",
        "Cheonan Walnut Grove", "Gongju Chestnut Forest", "Yesan Apple Orchard", "Geumsan Ginseng Field",
        "Damyang Bamboo Grove Farm", "Gochang Watermelon Plot", "Buan Salt Marsh Paddy", "Sunchang Pepper Paste Basin",
        "Jangheung Shiitake Forest", "Wando Seaweed Border Farm", "Goryeong Strawberry Greenhouse Field", "Seongju Melon Ground",
        "Cheongdo Bupyeong Peach Orchard", "Uiseong Garlic Field", "Yeongyang Red Pepper Terrace", "Cheongsong Apple Valley",
        "Miryang Perilla Leaf Farm", "Changnyeong Onion Plain", "Haman Watermelon Polder", "Namhae Terraced Rice Paddies",
        "Hadong Wild Tea Hills", "Sacheon Grain Terrace", "Tongyeong Coastal Farm", "Geoje Aloe Farm",
        "Ulleungdo Medicinal Herb Slope", "Yangpyeong Eco Farmstead"
    ],
    "Vietnam": [
        "Dong Bang Song Hong Ricefield", "Mekong Delta Fruit Garden", "Tay Nguyen Coffee Estate", "Annamite Hill Terrace",
        "Ca Mau Mangrove Meadow", "Lam Dong Tea Terrace", "Ba Vi Grazing Pasture", "Bac Ninh Craft Village Field",
        "Hue Imperial Paddy", "Quang Nam Mulberry Plot", "Mu Cang Chai Rice Terraces", "Sa Pa Hmong Hillside Farm",
        "Hoang Su Phi Terraced Field", "Thai Binh Wet Rice Allotment", "Nam Dinh Coastal Alluvium", "Hung Yen Longan Orchard",
        "Hai Duong Green Bean Field", "Bac Giang Lychee Hill", "Lang Son Anise Forest", "Son La Plum Valley",
        "Moc Chau Dairy Plateau", "Dien Bien Valley Paddy", "Hoa Binh Orange Grove", "Thanh Hoa Sugarcane Basin",
        "Nghe An Peanut Field", "Ha Tinh Grapefruit Orchard", "Quang Binh Pepper Farm", "Quang Tri Rubber Strip",
        "Quang Ngai Garlic Island Field", "Binh Dinh Coconut Grove", "Phu Yen Tunny Border Farm", "Khanh Hoa Mango Hill",
        "Ninh Thuan Grape Vineyard", "Binh Thuan Dragon Fruit Farm", "Dak Lak Rubber Plantation", "Gia Lai Pepper Terrace",
        "Kon Tum Cassava Slope", "Dak Nong Cocoa Farm", "Bao Loc Silk Mulberry Hill", "Dong Nai Cashew Plantation",
        "Binh Duong Rubber Estate", "Binh Phuoc Pepper Grove", "Tay Ninh Sugar Plantation", "Long An Watermelon Polder",
        "Tien Giang Durian Orchard", "Ben Tre Coconut Basin", "Vinh Long Orange Garden", "Can Tho Floating Ricefield",
        "An Giang Floating Rice Delta", "Kien Giang Giant Prawn & Rice Polder"
    ]
}

# Country aliases
COUNTRY_PLOT_NAMES["US"] = COUNTRY_PLOT_NAMES["United States"]
COUNTRY_PLOT_NAMES["UK"] = COUNTRY_PLOT_NAMES["Britain"]
COUNTRY_PLOT_NAMES["South Korea"] = COUNTRY_PLOT_NAMES["Korea"]


def get_plot_names_for_country(country_name: str) -> list[str]:
    """Return the list of authentic plot names for *country_name* (fallback to Britain)."""
    return list(COUNTRY_PLOT_NAMES.get(country_name, COUNTRY_PLOT_NAMES["Britain"]))


def get_plot_name(country_name: str, used_names: set = None, rng = None) -> str:
    """Return a unique authentic plot name for *country_name* avoiding *used_names*."""
    names = get_plot_names_for_country(country_name)
    used = used_names if used_names is not None else set()
    available = [n for n in names if n not in used]
    if available:
        return available[0] if rng is None else rng.choice(available)
    # If all 50 used, append an increment
    cycle = (len(used) // len(names)) + 1
    base = names[len(used) % len(names)]
    return f"{base} Section {cycle}"


COUNTRY_CURRENCIES = {
    "United States": "USD",
    "China": "CNY",
    "Japan": "JPY",
    "India": "INR",
    "Indonesia": "IDR",
    "Brazil": "BRL",
    "Mexico": "MXN",
    "Nigeria": "NGN",
    "Pakistan": "PKR",
    "Bangladesh": "BDT",
    "Russia": "RUB",
    "Korea": "KRW",
    "Vietnam": "VND",
    "Britain": "GBP",
    "France": "EUR",
    "Germany": "EUR",
    "Italy": "EUR",
    "Spain": "EUR",
    # Aliases
    "US": "USD",
    "UK": "GBP",
    "South Korea": "KRW",
}

# Real official national capitals for all nations
NATIONAL_CAPITALS = {
    "United States": "Washington, D.C.",
    "China": "Beijing",
    "Japan": "Tokyo",
    "Korea": "Seoul",
    "Vietnam": "Hanoi",
    "Britain": "London",
    "France": "Paris",
    "Germany": "Berlin",
    "Italy": "Rome",
    "Spain": "Madrid",
    "India": "New Delhi",
    "Indonesia": "Jakarta",
    "Brazil": "Brasília",
    "Mexico": "Mexico City",
    "Nigeria": "Abuja",
    "Pakistan": "Islamabad",
    "Bangladesh": "Dhaka",
    "Russia": "Moscow",
    # Aliases
    "US": "Washington, D.C.",
    "UK": "London",
    "South Korea": "Seoul",
}

# The first city in each province's list is the official real provincial capital
PROVINCIAL_CAPITALS = {
    (country, prov): cities[0]
    for country, prov_dict in GLOBAL_NATION_DATA.items()
    for prov, cities in prov_dict.items()
}


def get_national_capital(country_name: str) -> str:
    """Return the official real national capital for a given country."""
    return NATIONAL_CAPITALS.get(country_name, "Capital City")


def get_provincial_capital(country_name: str, province_name: str) -> str:
    """Return the official real provincial capital for a given province in a country."""
    return PROVINCIAL_CAPITALS.get(
        (country_name, province_name),
        GLOBAL_NATION_DATA.get(country_name, {}).get(province_name, ["Provincial Capital"])[0]
    )


def get_country_names():
    """Return the list of major country names."""
    return [k for k in GLOBAL_NATION_DATA.keys() if k not in ("US", "UK", "South Korea")]


def get_starting_nations_claimed_by(seed=None):
    """Return 3 starting nations: strictly starts each game with US, China, and Japan with authentic currencies and tile quotas."""
    selected = ["United States", "China", "Japan"]
    tile_counts = [3, 4, 5]
    out = {}
    for country, count in zip(selected, tile_counts):
        currency = COUNTRY_CURRENCIES.get(country, "USD")
        out[country] = (currency, count)
    return out


def get_provinces_for_country(country_name: str):
    """Return dict of provinces -> list of cities for a given country."""
    return GLOBAL_NATION_DATA.get(country_name, {})


def assign_world_identities(tiles, nations, seed=None):
    """Assign realistic country identities, provinces, capitals, and city names to tiles."""
    available_countries = list(GLOBAL_NATION_DATA.keys())
    rng = random.Random(seed) if seed is not None else random.Random()

    for i, n in enumerate(nations):
        country_name = n.name if n.name in GLOBAL_NATION_DATA else available_countries[i % len(available_countries)]
        n.name = country_name
        n.display_name = country_name
        if not hasattr(n, 'currency') or n.currency in ("AL", "BE", "GA"):
            n.currency = COUNTRY_CURRENCIES.get(country_name, "USD")
        
        country_data = GLOBAL_NATION_DATA[country_name]
        prov_names = list(country_data.keys())

        # Real National Capital
        national_cap_name = get_national_capital(country_name)
        national_cap_tile = n.tiles[0] if n.tiles else None
        n.capital = national_cap_tile

        # Identify which province contains the national capital
        cap_prov_name = None
        for p_name, cities in country_data.items():
            if national_cap_name in cities or p_name == national_cap_name:
                cap_prov_name = p_name
                break
        if cap_prov_name is None:
            cap_prov_name = list(country_data.keys())[0]

        # Prioritize the capital province first
        prov_names = [cap_prov_name] + [p for p in country_data.keys() if p != cap_prov_name]

        # Find which province contains the national capital tile
        provs_list = getattr(n, 'provinces', [])
        prov_with_cap = next((p for p in provs_list if national_cap_tile in p.tiles),
                             provs_list[0] if provs_list else None)

        used_cities = set()
        used_provs = set()

        for prov in getattr(n, 'provinces', []):
            if prov is prov_with_cap:
                p_name = cap_prov_name
            else:
                p_name = next((p for p in prov_names if p not in used_provs and p != cap_prov_name), prov_names[0])
            used_provs.add(p_name)

            prov.name = f"{country_name}-{p_name}"
            prov.display_name = p_name

            cities_pool = list(country_data[p_name])
            real_prov_cap = get_provincial_capital(country_name, p_name)

            # Designate provincial capital:
            # Nations may have the same tile for both national capital and provincial capital
            if national_cap_tile in prov.tiles:
                prov.capital = national_cap_tile
            else:
                prov.capital = prov.tiles[0] if prov.tiles else None

            for t_idx, tile in enumerate(prov.tiles):
                if tile is national_cap_tile:
                    city = national_cap_name
                    used_cities.add(city)
                    tile_prov_disp = p_name
                elif tile is prov.capital:
                    city = real_prov_cap
                    used_cities.add(city)
                    tile_prov_disp = p_name
                else:
                    city = next((c for c in cities_pool if c not in used_cities and c != real_prov_cap), cities_pool[t_idx % len(cities_pool)])
                    used_cities.add(city)
                    tile_prov_disp = p_name

                tile.city_name = city
                tile.display_name = city
                tile.province_display = tile_prov_disp
                tile.nation_display = country_name

                tile.is_national_capital = (tile is national_cap_tile)
                tile.is_provincial_capital = (tile is prov.capital)

                # Name land plots with authentic country names
                if hasattr(tile, 'tenure') and tile.tenure and tile.tenure.plots:
                    for plot in tile.tenure.plots:
                        p_name = get_plot_name(country_name, used_names=used_cities, rng=rng)
                        plot.name = p_name
                        used_cities.add(p_name)

        # Fallback if nation has no provinces list
        if not getattr(n, 'provinces', []):
            p_name = cap_prov_name
            cities_pool = list(country_data[p_name])
            for t_idx, tile in enumerate(n.tiles):
                city = national_cap_name if t_idx == 0 else cities_pool[t_idx % len(cities_pool)]
                tile.city_name = city
                tile.display_name = city
                tile.province_display = p_name
                tile.nation_display = country_name
                tile.is_national_capital = (t_idx == 0)
                tile.is_provincial_capital = (t_idx == 0)
                if hasattr(tile, 'tenure') and tile.tenure and tile.tenure.plots:
                    for plot in tile.tenure.plots:
                        p_plot_name = get_plot_name(country_name, used_names=used_cities, rng=rng)
                        plot.name = p_plot_name
                        used_cities.add(p_plot_name)

    # Name remaining wilderness and ocean tiles
    wild_pool = list(WILD_TERRAIN_NAMES)
    ocean_pool = list(OCEAN_BASIN_NAMES)
    rng.shuffle(wild_pool)
    rng.shuffle(ocean_pool)

    w_idx = 0
    o_idx = 0
    for tile in tiles:
        if not hasattr(tile, 'display_name') or getattr(tile, 'owner_nation', None) is None:
            tile.is_national_capital = False
            tile.is_provincial_capital = False
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


def claim_wilderness_tile(tile, nation, prov=None):
    """Dynamically assign an authentic city and province name when a wilderness tile is claimed."""
    country_name = getattr(nation, 'display_name', nation.name)
    country_data = GLOBAL_NATION_DATA.get(country_name, {})
    if not country_data:
        tile.province_display = getattr(prov, 'display_name', 'Core') if prov else 'Core'
        tile.nation_display = country_name
        return

    # Find already used city and province names in this nation
    used_cities = {getattr(t, 'city_name', '') for t in nation.tiles}
    used_prov_names = {getattr(p, 'display_name', p.name.split('-')[-1]) for p in getattr(nation, 'provinces', [])}

    if prov is None or not getattr(prov, 'display_name', None):
        # Pick next unused province name
        prov_names = list(country_data.keys())
        p_name = next((p for p in prov_names if p not in used_prov_names), prov_names[0])
        if prov:
            prov.display_name = p_name
            prov.name = f"{country_name}-{p_name}"
    else:
        p_name = prov.display_name

    # Pick next unused city in this province
    prov_cities = country_data.get(p_name, list(country_data.values())[0])
    chosen_city = next((c for c in prov_cities if c not in used_cities), None)
    if not chosen_city:
        # Pick any unused city in the country
        for c_list in country_data.values():
            chosen_city = next((c for c in c_list if c not in used_cities), None)
            if chosen_city:
                break
    if not chosen_city:
        chosen_city = f"{p_name} New Settlement"

    tile.city_name = chosen_city
    tile.display_name = chosen_city
    tile.province_display = p_name
    tile.nation_display = country_name
    tile.is_national_capital = False
    tile.is_provincial_capital = (prov is not None and len(prov.tiles) == 1)

    if hasattr(tile, 'tenure') and tile.tenure and tile.tenure.plots:
        for plot in tile.tenure.plots:
            if not getattr(plot, 'name', None):
                plot.name = get_plot_name(country_name, used_names=used_cities)
                used_cities.add(plot.name)
