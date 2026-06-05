const countries = [
  {
    "es": "Afganistán",
    "en": "Afghanistan",
    "iso2": "AF",
    "iso3": "AFG",
    "phoneCode": "93"
  },
  {
    "es": "Albania",
    "en": "Albania",
    "iso2": "AL",
    "iso3": "ALB",
    "phoneCode": "355"
  },
  {
    "es": "Alemania",
    "en": "Germany",
    "iso2": "DE",
    "iso3": "DEU",
    "phoneCode": "49"
  },
  {
    "es": "Algeria",
    "en": "Algeria",
    "iso2": "DZ",
    "iso3": "DZA",
    "phoneCode": "213"
  },
  {
    "es": "Andorra",
    "en": "Andorra",
    "iso2": "AD",
    "iso3": "AND",
    "phoneCode": "376"
  },
  {
    "es": "Angola",
    "en": "Angola",
    "iso2": "AO",
    "iso3": "AGO",
    "phoneCode": "244"
  },
  {
    "es": "Anguila",
    "en": "Anguilla",
    "iso2": "AI",
    "iso3": "AIA",
    "phoneCode": "1 264"
  },
  {
    "es": "Antártida",
    "en": "Antarctica",
    "iso2": "AQ",
    "iso3": "ATA",
    "phoneCode": "672"
  },
  {
    "es": "Antigua y Barbuda",
    "en": "Antigua and Barbuda",
    "iso2": "AG",
    "iso3": "ATG",
    "phoneCode": "1 268"
  },
  {
    "es": "Antillas Neerlandesas",
    "en": "Netherlands Antilles",
    "iso2": "AN",
    "iso3": "ANT",
    "phoneCode": "599"
  },
  {
    "es": "Arabia Saudita",
    "en": "Saudi Arabia",
    "iso2": "SA",
    "iso3": "SAU",
    "phoneCode": "966"
  },
  {
    "es": "Argentina",
    "en": "Argentina",
    "iso2": "AR",
    "iso3": "ARG",
    "phoneCode": "54"
  },
  {
    "es": "Armenia",
    "en": "Armenia",
    "iso2": "AM",
    "iso3": "ARM",
    "phoneCode": "374"
  },
  {
    "es": "Aruba",
    "en": "Aruba",
    "iso2": "AW",
    "iso3": "ABW",
    "phoneCode": "297"
  },
  {
    "es": "Australia",
    "en": "Australia",
    "iso2": "AU",
    "iso3": "AUS",
    "phoneCode": "61"
  },
  {
    "es": "Austria",
    "en": "Austria",
    "iso2": "AT",
    "iso3": "AUT",
    "phoneCode": "43"
  },
  {
    "es": "Azerbayán",
    "en": "Azerbaijan",
    "iso2": "AZ",
    "iso3": "AZE",
    "phoneCode": "994"
  },
  {
    "es": "Bahamas",
    "en": "Bahamas",
    "iso2": "BS",
    "iso3": "BHS",
    "phoneCode": "1 242"
  },
  {
    "es": "Bahrein",
    "en": "Bahrain",
    "iso2": "BH",
    "iso3": "BHR",
    "phoneCode": "973"
  },
  {
    "es": "Bangladesh",
    "en": "Bangladesh",
    "iso2": "BD",
    "iso3": "BGD",
    "phoneCode": "880"
  },
  {
    "es": "Barbados",
    "en": "Barbados",
    "iso2": "BB",
    "iso3": "BRB",
    "phoneCode": "1 246"
  },
  {
    "es": "Bélgica",
    "en": "Belgium",
    "iso2": "BE",
    "iso3": "BEL",
    "phoneCode": "32"
  },
  {
    "es": "Belice",
    "en": "Belize",
    "iso2": "BZ",
    "iso3": "BLZ",
    "phoneCode": "501"
  },
  {
    "es": "Benín",
    "en": "Benin",
    "iso2": "BJ",
    "iso3": "BEN",
    "phoneCode": "229"
  },
  {
    "es": "Bhután",
    "en": "Bhutan",
    "iso2": "BT",
    "iso3": "BTN",
    "phoneCode": "975"
  },
  {
    "es": "Bielorrusia",
    "en": "Belarus",
    "iso2": "BY",
    "iso3": "BLR",
    "phoneCode": "375"
  },
  {
    "es": "Birmania",
    "en": "Myanmar",
    "iso2": "MM",
    "iso3": "MMR",
    "phoneCode": "95"
  },
  {
    "es": "Bolivia",
    "en": "Bolivia",
    "iso2": "BO",
    "iso3": "BOL",
    "phoneCode": "591"
  },
  {
    "es": "Bosnia y Herzegovina",
    "en": "Bosnia and Herzegovina",
    "iso2": "BA",
    "iso3": "BIH",
    "phoneCode": "387"
  },
  {
    "es": "Botsuana",
    "en": "Botswana",
    "iso2": "BW",
    "iso3": "BWA",
    "phoneCode": "267"
  },
  {
    "es": "Brasil",
    "en": "Brazil",
    "iso2": "BR",
    "iso3": "BRA",
    "phoneCode": "55"
  },
  {
    "es": "Brunéi",
    "en": "Brunei",
    "iso2": "BN",
    "iso3": "BRN",
    "phoneCode": "673"
  },
  {
    "es": "Bulgaria",
    "en": "Bulgaria",
    "iso2": "BG",
    "iso3": "BGR",
    "phoneCode": "359"
  },
  {
    "es": "Burkina Faso",
    "en": "Burkina Faso",
    "iso2": "BF",
    "iso3": "BFA",
    "phoneCode": "226"
  },
  {
    "es": "Burundi",
    "en": "Burundi",
    "iso2": "BI",
    "iso3": "BDI",
    "phoneCode": "257"
  },
  {
    "es": "Cabo Verde",
    "en": "Cape Verde",
    "iso2": "CV",
    "iso3": "CPV",
    "phoneCode": "238"
  },
  {
    "es": "Camboya",
    "en": "Cambodia",
    "iso2": "KH",
    "iso3": "KHM",
    "phoneCode": "855"
  },
  {
    "es": "Camerún",
    "en": "Cameroon",
    "iso2": "CM",
    "iso3": "CMR",
    "phoneCode": "237"
  },
  {
    "es": "Canadá",
    "en": "Canada",
    "iso2": "CA",
    "iso3": "CAN",
    "phoneCode": "1"
  },
  {
    "es": "Chad",
    "en": "Chad",
    "iso2": "TD",
    "iso3": "TCD",
    "phoneCode": "235"
  },
  {
    "es": "Chile",
    "en": "Chile",
    "iso2": "CL",
    "iso3": "CHL",
    "phoneCode": "56"
  },
  {
    "es": "China",
    "en": "China",
    "iso2": "CN",
    "iso3": "CHN",
    "phoneCode": "86"
  },
  {
    "es": "Chipre",
    "en": "Cyprus",
    "iso2": "CY",
    "iso3": "CYP",
    "phoneCode": "357"
  },
  {
    "es": "Ciudad del Vaticano",
    "en": "Vatican City State",
    "iso2": "VA",
    "iso3": "VAT",
    "phoneCode": "39"
  },
  {
    "es": "Colombia",
    "en": "Colombia",
    "iso2": "CO",
    "iso3": "COL",
    "phoneCode": "57"
  },
  {
    "es": "Comoras",
    "en": "Comoros",
    "iso2": "KM",
    "iso3": "COM",
    "phoneCode": "269"
  },
  {
    "es": "Congo",
    "en": "Congo",
    "iso2": "CG",
    "iso3": "COG",
    "phoneCode": "242"
  },
  {
    "es": "Congo",
    "en": "Congo",
    "iso2": "CD",
    "iso3": "COD",
    "phoneCode": "243"
  },
  {
    "es": "Corea del Norte",
    "en": "North Korea",
    "iso2": "KP",
    "iso3": "PRK",
    "phoneCode": "850"
  },
  {
    "es": "Corea del Sur",
    "en": "South Korea",
    "iso2": "KR",
    "iso3": "KOR",
    "phoneCode": "82"
  },
  {
    "es": "Costa de Marfil",
    "en": "Ivory Coast",
    "iso2": "CI",
    "iso3": "CIV",
    "phoneCode": "225"
  },
  {
    "es": "Costa Rica",
    "en": "Costa Rica",
    "iso2": "CR",
    "iso3": "CRI",
    "phoneCode": "506"
  },
  {
    "es": "Croacia",
    "en": "Croatia",
    "iso2": "HR",
    "iso3": "HRV",
    "phoneCode": "385"
  },
  {
    "es": "Cuba",
    "en": "Cuba",
    "iso2": "CU",
    "iso3": "CUB",
    "phoneCode": "53"
  },
  {
    "es": "Dinamarca",
    "en": "Denmark",
    "iso2": "DK",
    "iso3": "DNK",
    "phoneCode": "45"
  },
  {
    "es": "Dominica",
    "en": "Dominica",
    "iso2": "DM",
    "iso3": "DMA",
    "phoneCode": "1 767"
  },
  {
    "es": "Ecuador",
    "en": "Ecuador",
    "iso2": "EC",
    "iso3": "ECU",
    "phoneCode": "593"
  },
  {
    "es": "Egipto",
    "en": "Egypt",
    "iso2": "EG",
    "iso3": "EGY",
    "phoneCode": "20"
  },
  {
    "es": "El Salvador",
    "en": "El Salvador",
    "iso2": "SV",
    "iso3": "SLV",
    "phoneCode": "503"
  },
  {
    "es": "Emiratos Árabes Unidos",
    "en": "United Arab Emirates",
    "iso2": "AE",
    "iso3": "ARE",
    "phoneCode": "971"
  },
  {
    "es": "Eritrea",
    "en": "Eritrea",
    "iso2": "ER",
    "iso3": "ERI",
    "phoneCode": "291"
  },
  {
    "es": "Escocia",
    "en": "Scotland",
    "iso2": "GB",
    "iso3": "",
    "phoneCode": "44"
  },
  {
    "es": "Eslovaquia",
    "en": "Slovakia",
    "iso2": "SK",
    "iso3": "SVK",
    "phoneCode": "421"
  },
  {
    "es": "Eslovenia",
    "en": "Slovenia",
    "iso2": "SI",
    "iso3": "SVN",
    "phoneCode": "386"
  },
  {
    "es": "España",
    "en": "Spain",
    "iso2": "ES",
    "iso3": "ESP",
    "phoneCode": "34"
  },
  {
    "es": "Estados Unidos de América",
    "en": "United States of America",
    "iso2": "US",
    "iso3": "USA",
    "phoneCode": "1"
  },
  {
    "es": "Estonia",
    "en": "Estonia",
    "iso2": "EE",
    "iso3": "EST",
    "phoneCode": "372"
  },
  {
    "es": "Etiopía",
    "en": "Ethiopia",
    "iso2": "ET",
    "iso3": "ETH",
    "phoneCode": "251"
  },
  {
    "es": "Filipinas",
    "en": "Philippines",
    "iso2": "PH",
    "iso3": "PHL",
    "phoneCode": "63"
  },
  {
    "es": "Finlandia",
    "en": "Finland",
    "iso2": "FI",
    "iso3": "FIN",
    "phoneCode": "358"
  },
  {
    "es": "Fiyi",
    "en": "Fiji",
    "iso2": "FJ",
    "iso3": "FJI",
    "phoneCode": "679"
  },
  {
    "es": "Francia",
    "en": "France",
    "iso2": "FR",
    "iso3": "FRA",
    "phoneCode": "33"
  },
  {
    "es": "Gabón",
    "en": "Gabon",
    "iso2": "GA",
    "iso3": "GAB",
    "phoneCode": "241"
  },
  {
    "es": "Gales",
    "en": "Wales",
    "iso2": "GB",
    "iso3": "",
    "phoneCode": "44"
  },
  {
    "es": "Gambia",
    "en": "Gambia",
    "iso2": "GM",
    "iso3": "GMB",
    "phoneCode": "220"
  },
  {
    "es": "Georgia",
    "en": "Georgia",
    "iso2": "GE",
    "iso3": "GEO",
    "phoneCode": "995"
  },
  {
    "es": "Ghana",
    "en": "Ghana",
    "iso2": "GH",
    "iso3": "GHA",
    "phoneCode": "233"
  },
  {
    "es": "Gibraltar",
    "en": "Gibraltar",
    "iso2": "GI",
    "iso3": "GIB",
    "phoneCode": "350"
  },
  {
    "es": "Granada",
    "en": "Grenada",
    "iso2": "GD",
    "iso3": "GRD",
    "phoneCode": "1 473"
  },
  {
    "es": "Grecia",
    "en": "Greece",
    "iso2": "GR",
    "iso3": "GRC",
    "phoneCode": "30"
  },
  {
    "es": "Groenlandia",
    "en": "Greenland",
    "iso2": "GL",
    "iso3": "GRL",
    "phoneCode": "299"
  },
  {
    "es": "Guam",
    "en": "Guam",
    "iso2": "GU",
    "iso3": "GUM",
    "phoneCode": "1 671"
  },
  {
    "es": "Guatemala",
    "en": "Guatemala",
    "iso2": "GT",
    "iso3": "GTM",
    "phoneCode": "502"
  },
  {
    "es": "Guinea",
    "en": "Guinea",
    "iso2": "GN",
    "iso3": "GIN",
    "phoneCode": "224"
  },
  {
    "es": "Guinea Ecuatorial",
    "en": "Equatorial Guinea",
    "iso2": "GQ",
    "iso3": "GNQ",
    "phoneCode": "240"
  },
  {
    "es": "Guinea-Bissau",
    "en": "Guinea-Bissau",
    "iso2": "GW",
    "iso3": "GNB",
    "phoneCode": "245"
  },
  {
    "es": "Guyana",
    "en": "Guyana",
    "iso2": "GY",
    "iso3": "GUY",
    "phoneCode": "592"
  },
  {
    "es": "Haití",
    "en": "Haiti",
    "iso2": "HT",
    "iso3": "HTI",
    "phoneCode": "509"
  },
  {
    "es": "Honduras",
    "en": "Honduras",
    "iso2": "HN",
    "iso3": "HND",
    "phoneCode": "504"
  },
  
  {
    "es": "Hong kong",
    "en": "Hong Kong",
    "iso2": "HK",
    "iso3": "HKG",
    "phoneCode": "852"
  },
  {
    "es": "Hungría",
    "en": "Hungary",
    "iso2": "HU",
    "iso3": "HUN",
    "phoneCode": "36"
  },
  {
    "es": "India",
    "en": "India",
    "iso2": "IN",
    "iso3": "IND",
    "phoneCode": "91"
  },
  {
    "es": "Indonesia",
    "en": "Indonesia",
    "iso2": "ID",
    "iso3": "IDN",
    "phoneCode": "62"
  },
  {
    "es": "Inglaterra",
    "en": "England",
    "iso2": "GB",
    "iso3": "",
    "phoneCode": "44"
  },
  {
    "es": "Irak",
    "en": "Iraq",
    "iso2": "IQ",
    "iso3": "IRQ",
    "phoneCode": "964"
  },
  {
    "es": "Irán",
    "en": "Iran",
    "iso2": "IR",
    "iso3": "IRN",
    "phoneCode": "98"
  },
  {
    "es": "Irlanda",
    "en": "Ireland",
    "iso2": "IE",
    "iso3": "IRL",
    "phoneCode": "353"
  },
  {
    "es": "Irlanda del Norte",
    "en": "Northern Irland",
    "iso2": "GB",
    "iso3": "",
    "phoneCode": "44"
  },
 
  {
    "es": "Isla de Man",
    "en": "Isle of Man",
    "iso2": "IM",
    "iso3": "IMN",
    "phoneCode": "44"
  },
  {
    "es": "Isla de Navidad",
    "en": "Christmas Island",
    "iso2": "CX",
    "iso3": "CXR",
    "phoneCode": "61"
  },
 
  {
    "es": "Islandia",
    "en": "Iceland",
    "iso2": "IS",
    "iso3": "ISL",
    "phoneCode": "354"
  },
  {
    "es": "Islas Bermudas",
    "en": "Bermuda Islands",
    "iso2": "BM",
    "iso3": "BMU",
    "phoneCode": "1 441"
  },
  {
    "es": "Islas Caimán",
    "en": "Cayman Islands",
    "iso2": "KY",
    "iso3": "CYM",
    "phoneCode": "1 345"
  },
  {
    "es": "Islas Cocos (Keeling)",
    "en": "Cocos (Keeling) Islands",
    "iso2": "CC",
    "iso3": "CCK",
    "phoneCode": "61"
  },
  {
    "es": "Islas Cook",
    "en": "Cook Islands",
    "iso2": "CK",
    "iso3": "COK",
    "phoneCode": "682"
  },
 
  {
    "es": "Islas Feroe",
    "en": "Faroe Islands",
    "iso2": "FO",
    "iso3": "FRO",
    "phoneCode": "298"
  },
 
 
  {
    "es": "Islas Maldivas",
    "en": "Maldives",
    "iso2": "MV",
    "iso3": "MDV",
    "phoneCode": "960"
  },
  {
    "es": "Islas Malvinas",
    "en": "Falkland Islands (Malvinas)",
    "iso2": "FK",
    "iso3": "FLK",
    "phoneCode": "500"
  },
  {
    "es": "Islas Marianas del Norte",
    "en": "Northern Mariana Islands",
    "iso2": "MP",
    "iso3": "MNP",
    "phoneCode": "1 670"
  },
  {
    "es": "Islas Marshall",
    "en": "Marshall Islands",
    "iso2": "MH",
    "iso3": "MHL",
    "phoneCode": "692"
  },
  {
    "es": "Islas Pitcairn",
    "en": "Pitcairn Islands",
    "iso2": "PN",
    "iso3": "PCN",
    "phoneCode": "870"
  },
  {
    "es": "Islas Salomón",
    "en": "Solomon Islands",
    "iso2": "SB",
    "iso3": "SLB",
    "phoneCode": "677"
  },
  {
    "es": "Sint Maarten (parte neerlandesa)",
    "en": "Sint Maarten (Dutch part)",
    "iso2": "SXM",
    "iso3": "SX",
    "phoneCode": "+1"
  },
  {
    "es": "Islas Turcas y Caicos",
    "en": "Turks and Caicos Islands",
    "iso2": "TC",
    "iso3": "TCA",
    "phoneCode": "1 649"
  },
 
  {
    "es": "Islas Vírgenes Británicas",
    "en": "Virgin Islands",
    "iso2": "VG",
    "iso3": "VG",
    "phoneCode": "1 284"
  },
  {
    "es": "Islas Vírgenes de los Estados Unidos",
    "en": "United States Virgin Islands",
    "iso2": "VI",
    "iso3": "VIR",
    "phoneCode": "1 340"
  },
  {
    "es": "Israel",
    "en": "Israel",
    "iso2": "IL",
    "iso3": "ISR",
    "phoneCode": "972"
  },
  {
    "es": "Italia",
    "en": "Italy",
    "iso2": "IT",
    "iso3": "ITA",
    "phoneCode": "39"
  },
  {
    "es": "Jamaica",
    "en": "Jamaica",
    "iso2": "JM",
    "iso3": "JAM",
    "phoneCode": "1 876"
  },
  {
    "es": "Japón",
    "en": "Japan",
    "iso2": "JP",
    "iso3": "JPN",
    "phoneCode": "81"
  },
 
  {
    "es": "Jordania",
    "en": "Jordan",
    "iso2": "JO",
    "iso3": "JOR",
    "phoneCode": "962"
  },
  {
    "es": "Kazajistán",
    "en": "Kazakhstan",
    "iso2": "KZ",
    "iso3": "KAZ",
    "phoneCode": "7"
  },
  {
    "es": "Kenia",
    "en": "Kenya",
    "iso2": "KE",
    "iso3": "KEN",
    "phoneCode": "254"
  },
  {
    "es": "Kirgizstán",
    "en": "Kyrgyzstan",
    "iso2": "KG",
    "iso3": "KGZ",
    "phoneCode": "996"
  },
  {
    "es": "Kiribati",
    "en": "Kiribati",
    "iso2": "KI",
    "iso3": "KIR",
    "phoneCode": "686"
  },
  {
    "es": "Kuwait",
    "en": "Kuwait",
    "iso2": "KW",
    "iso3": "KWT",
    "phoneCode": "965"
  },
  {
    "es": "Laos",
    "en": "Laos",
    "iso2": "LA",
    "iso3": "LAO",
    "phoneCode": "856"
  },
  {
    "es": "Lesoto",
    "en": "Lesotho",
    "iso2": "LS",
    "iso3": "LSO",
    "phoneCode": "266"
  },
  {
    "es": "Letonia",
    "en": "Latvia",
    "iso2": "LV",
    "iso3": "LVA",
    "phoneCode": "371"
  },
  {
    "es": "Líbano",
    "en": "Lebanon",
    "iso2": "LB",
    "iso3": "LBN",
    "phoneCode": "961"
  },
  {
    "es": "Liberia",
    "en": "Liberia",
    "iso2": "LR",
    "iso3": "LBR",
    "phoneCode": "231"
  },
  {
    "es": "Libia",
    "en": "Libya",
    "iso2": "LY",
    "iso3": "LBY",
    "phoneCode": "218"
  },
  {
    "es": "Liechtenstein",
    "en": "Liechtenstein",
    "iso2": "LI",
    "iso3": "LIE",
    "phoneCode": "423"
  },
  {
    "es": "Lituania",
    "en": "Lithuania",
    "iso2": "LT",
    "iso3": "LTU",
    "phoneCode": "370"
  },
  {
    "es": "Luxemburgo",
    "en": "Luxembourg",
    "iso2": "LU",
    "iso3": "LUX",
    "phoneCode": "352"
  },
  {
    "es": "Macao",
    "en": "Macao",
    "iso2": "MO",
    "iso3": "MAC",
    "phoneCode": "853"
  },
  {
    "es": "Macedônia",
    "en": "Macedonia",
    "iso2": "MK",
    "iso3": "MKD",
    "phoneCode": "389"
  },
  {
    "es": "Madagascar",
    "en": "Madagascar",
    "iso2": "MG",
    "iso3": "MDG",
    "phoneCode": "261"
  },
  {
    "es": "Malasia",
    "en": "Malaysia",
    "iso2": "MY",
    "iso3": "MYS",
    "phoneCode": "60"
  },
  {
    "es": "Malawi",
    "en": "Malawi",
    "iso2": "MW",
    "iso3": "MWI",
    "phoneCode": "265"
  },
  {
    "es": "Mali",
    "en": "Mali",
    "iso2": "ML",
    "iso3": "MLI",
    "phoneCode": "223"
  },
  {
    "es": "Malta",
    "en": "Malta",
    "iso2": "MT",
    "iso3": "MLT",
    "phoneCode": "356"
  },
  {
    "es": "Marruecos",
    "en": "Morocco",
    "iso2": "MA",
    "iso3": "MAR",
    "phoneCode": "212"
  },
 
  {
    "es": "Mauricio",
    "en": "Mauritius",
    "iso2": "MU",
    "iso3": "MUS",
    "phoneCode": "230"
  },
  {
    "es": "Mauritania",
    "en": "Mauritania",
    "iso2": "MR",
    "iso3": "MRT",
    "phoneCode": "222"
  },
  {
    "es": "Mayotte",
    "en": "Mayotte",
    "iso2": "YT",
    "iso3": "MYT",
    "phoneCode": "262"
  },
  {
    "es": "México",
    "en": "Mexico",
    "iso2": "MX",
    "iso3": "MEX",
    "phoneCode": "52"
  },
  {
    "es": "Micronesia",
    "en": "Micronesia",
    "iso2": "FM",
    "iso3": "FSM",
    "phoneCode": "691"
  },
  {
    "es": "Moldavia",
    "en": "Moldova",
    "iso2": "MD",
    "iso3": "MDA",
    "phoneCode": "373"
  },
  {
    "es": "Mónaco",
    "en": "Monaco",
    "iso2": "MC",
    "iso3": "MCO",
    "phoneCode": "377"
  },
  {
    "es": "Mongolia",
    "en": "Mongolia",
    "iso2": "MN",
    "iso3": "MNG",
    "phoneCode": "976"
  },
  {
    "es": "Montenegro",
    "en": "Montenegro",
    "iso2": "ME",
    "iso3": "MNE",
    "phoneCode": "382"
  },
  {
    "es": "Montserrat",
    "en": "Montserrat",
    "iso2": "MS",
    "iso3": "MSR",
    "phoneCode": "1 664"
  },
  {
    "es": "Mozambique",
    "en": "Mozambique",
    "iso2": "MZ",
    "iso3": "MOZ",
    "phoneCode": "258"
  },
  {
    "es": "Namibia",
    "en": "Namibia",
    "iso2": "NA",
    "iso3": "NAM",
    "phoneCode": "264"
  },
  {
    "es": "Nauru",
    "en": "Nauru",
    "iso2": "NR",
    "iso3": "NRU",
    "phoneCode": "674"
  },
  {
    "es": "Nepal",
    "en": "Nepal",
    "iso2": "NP",
    "iso3": "NPL",
    "phoneCode": "977"
  },
  {
    "es": "Nicaragua",
    "en": "Nicaragua",
    "iso2": "NI",
    "iso3": "NIC",
    "phoneCode": "505"
  },
  {
    "es": "Niger",
    "en": "Niger",
    "iso2": "NE",
    "iso3": "NER",
    "phoneCode": "227"
  },
  {
    "es": "Nigeria",
    "en": "Nigeria",
    "iso2": "NG",
    "iso3": "NGA",
    "phoneCode": "234"
  },
  {
    "es": "Niue",
    "en": "Niue",
    "iso2": "NU",
    "iso3": "NIU",
    "phoneCode": "683"
  },
  {
    "es": "Noruega",
    "en": "Norway",
    "iso2": "NO",
    "iso3": "NOR",
    "phoneCode": "47"
  },
  {
    "es": "Nueva Caledonia",
    "en": "New Caledonia",
    "iso2": "NC",
    "iso3": "NCL",
    "phoneCode": "687"
  },
  {
    "es": "Nueva Zelanda",
    "en": "New Zealand",
    "iso2": "NZ",
    "iso3": "NZL",
    "phoneCode": "64"
  },
  {
    "es": "Omán",
    "en": "Oman",
    "iso2": "OM",
    "iso3": "OMN",
    "phoneCode": "968"
  },
  {
    "es": "Países Bajos",
    "en": "Netherlands",
    "iso2": "NL",
    "iso3": "NLD",
    "phoneCode": "31"
  },
  {
    "es": "Curazao",
    "en": "Curaçao",
    "iso2": "CW",
    "iso3": "CUW",
    "phoneCode": "599"
  },
  {
    "es": "Pakistán",
    "en": "Pakistan",
    "iso2": "PK",
    "iso3": "PAK",
    "phoneCode": "92"
  },
  {
    "es": "Palau",
    "en": "Palau",
    "iso2": "PW",
    "iso3": "PLW",
    "phoneCode": "680"
  },

  {
    "es": "Palestina",
    "en": "Palestine",
    "iso2": "PS",
    "iso3": "PSE",
    "phoneCode": "+970"
  },
 
  {
    "es": "Panamá",
    "en": "Panama",
    "iso2": "PA",
    "iso3": "PAN",
    "phoneCode": "507"
  },
  {
    "es": "Papúa Nueva Guinea",
    "en": "Papua New Guinea",
    "iso2": "PG",
    "iso3": "PNG",
    "phoneCode": "675"
  },
  {
    "es": "Paraguay",
    "en": "Paraguay",
    "iso2": "PY",
    "iso3": "PRY",
    "phoneCode": "595"
  },
  {
    "es": "Perú",
    "en": "Peru",
    "iso2": "PE",
    "iso3": "PER",
    "phoneCode": "51"
  },
  {
    "es": "Polinesia Francesa",
    "en": "French Polynesia",
    "iso2": "PF",
    "iso3": "PYF",
    "phoneCode": "689"
  },
  {
    "es": "Polonia",
    "en": "Poland",
    "iso2": "PL",
    "iso3": "POL",
    "phoneCode": "48"
  },
  {
    "es": "Portugal",
    "en": "Portugal",
    "iso2": "PT",
    "iso3": "PRT",
    "phoneCode": "351"
  },
  {
    "es": "Puerto Rico",
    "en": "Puerto Rico",
    "iso2": "PR",
    "iso3": "PRI",
    "phoneCode": "1"
  },
  {
    "es": "Qatar",
    "en": "Qatar",
    "iso2": "QA",
    "iso3": "QAT",
    "phoneCode": "974"
  },
  {
    "es": "Reino Unido",
    "en": "United Kingdom",
    "iso2": "GB",
    "iso3": "GBR",
    "phoneCode": "44"
  },
  {
    "es": "República Centroafricana",
    "en": "Central African Republic",
    "iso2": "CF",
    "iso3": "CAF",
    "phoneCode": "236"
  },
  {
    "es": "República Checa",
    "en": "Czech Republic",
    "iso2": "CZ",
    "iso3": "CZE",
    "phoneCode": "420"
  },
  {
    "es": "República Dominicana",
    "en": "Dominican Republic",
    "iso2": "DO",
    "iso3": "DOM",
    "phoneCode": "1 809"
  },
 
  {
    "es": "Ruanda",
    "en": "Rwanda",
    "iso2": "RW",
    "iso3": "RWA",
    "phoneCode": "250"
  },
  {
    "es": "Rumanía",
    "en": "Romania",
    "iso2": "RO",
    "iso3": "ROU",
    "phoneCode": "40"
  },
  {
    "es": "Rusia",
    "en": "Russia",
    "iso2": "RU",
    "iso3": "RUS",
    "phoneCode": "7"
  },
 
  {
    "es": "Samoa",
    "en": "Samoa",
    "iso2": "WS",
    "iso3": "WSM",
    "phoneCode": "685"
  },
  {
    "es": "Samoa Americana",
    "en": "American Samoa",
    "iso2": "AS",
    "iso3": "ASM",
    "phoneCode": "1 684"
  },
  {
    "es": "San Bartolomé",
    "en": "Saint Barthélemy",
    "iso2": "BL",
    "iso3": "BLM",
    "phoneCode": "590"
  },
  {
    "es": "San Cristóbal y Nieves",
    "en": "Saint Kitts and Nevis",
    "iso2": "KN",
    "iso3": "KNA",
    "phoneCode": "1 869"
  },
  {
    "es": "San Marino",
    "en": "San Marino",
    "iso2": "SM",
    "iso3": "SMR",
    "phoneCode": "378"
  },
  {
    "es": "San Martín (Francia)",
    "en": "Saint Martin (French part)",
    "iso2": "MF",
    "iso3": "MAF",
    "phoneCode": "1 599"
  },
  {
    "es": "San Pedro y Miquelón",
    "en": "Saint Pierre and Miquelon",
    "iso2": "PM",
    "iso3": "SPM",
    "phoneCode": "508"
  },
  {
    "es": "San Vicente y las Granadinas",
    "en": "Saint Vincent and the Grenadines",
    "iso2": "VC",
    "iso3": "VCT",
    "phoneCode": "1 784"
  },
  {
    "es": "Santa Elena",
    "en": "Ascensión y Tristán de Acuña",
    "iso2": "SH",
    "iso3": "SHN",
    "phoneCode": "290"
  },
  {
    "es": "Santa Lucía",
    "en": "Saint Lucia",
    "iso2": "LC",
    "iso3": "LCA",
    "phoneCode": "1 758"
  },
  {
    "es": "Santo Tomé y Príncipe",
    "en": "Sao Tome and Principe",
    "iso2": "ST",
    "iso3": "STP",
    "phoneCode": "239"
  },
  {
    "es": "Senegal",
    "en": "Senegal",
    "iso2": "SN",
    "iso3": "SEN",
    "phoneCode": "221"
  },
  {
    "es": "Serbia",
    "en": "Serbia",
    "iso2": "RS",
    "iso3": "SRB",
    "phoneCode": "381"
  },
  {
    "es": "Seychelles",
    "en": "Seychelles",
    "iso2": "SC",
    "iso3": "SYC",
    "phoneCode": "248"
  },
  {
    "es": "Sierra Leona",
    "en": "Sierra Leone",
    "iso2": "SL",
    "iso3": "SLE",
    "phoneCode": "232"
  },
  {
    "es": "Singapur",
    "en": "Singapore",
    "iso2": "SG",
    "iso3": "SGP",
    "phoneCode": "65"
  },
  {
    "es": "Siria",
    "en": "Syria",
    "iso2": "SY",
    "iso3": "SYR",
    "phoneCode": "963"
  },
  {
    "es": "Somalia",
    "en": "Somalia",
    "iso2": "SO",
    "iso3": "SOM",
    "phoneCode": "252"
  },
  {
    "es": "Sri lanka",
    "en": "Sri Lanka",
    "iso2": "LK",
    "iso3": "LKA",
    "phoneCode": "94"
  },
  {
    "es": "Sudáfrica",
    "en": "South Africa",
    "iso2": "ZA",
    "iso3": "ZAF",
    "phoneCode": "27"
  },
  {
    "es": "Sudán",
    "en": "Sudan",
    "iso2": "SD",
    "iso3": "SDN",
    "phoneCode": "249"
  },
  {
    "es": "Sudán del sur",
    "en": "South Sudan",
    "iso2": "SS",
    "iso3": "SSD",
    "phoneCode": "211"
  },
  {
    "es": "Suecia",
    "en": "Sweden",
    "iso2": "SE",
    "iso3": "SWE",
    "phoneCode": "46"
  },
  {
    "es": "Suiza",
    "en": "Switzerland",
    "iso2": "CH",
    "iso3": "CHE",
    "phoneCode": "41"
  },
  {
    "es": "Surinám",
    "en": "Suriname",
    "iso2": "SR",
    "iso3": "SUR",
    "phoneCode": "597"
  },
 
  {
    "es": "Swazilandia",
    "en": "Swaziland",
    "iso2": "SZ",
    "iso3": "SWZ",
    "phoneCode": "268"
  },
  {
    "es": "Tadjikistán",
    "en": "Tajikistan",
    "iso2": "TJ",
    "iso3": "TJK",
    "phoneCode": "992"
  },
  {
    "es": "Tailandia",
    "en": "Thailand",
    "iso2": "TH",
    "iso3": "THA",
    "phoneCode": "66"
  },
  {
    "es": "Taiwán",
    "en": "Taiwan",
    "iso2": "TW",
    "iso3": "TWN",
    "phoneCode": "886"
  },
  {
    "es": "Tanzania",
    "en": "Tanzania",
    "iso2": "TZ",
    "iso3": "TZA",
    "phoneCode": "255"
  },
 
 
  {
    "es": "Timor Oriental",
    "en": "East Timor",
    "iso2": "TL",
    "iso3": "TLS",
    "phoneCode": "670"
  },
  {
    "es": "Togo",
    "en": "Togo",
    "iso2": "TG",
    "iso3": "TGO",
    "phoneCode": "228"
  },
  {
    "es": "Tokelau",
    "en": "Tokelau",
    "iso2": "TK",
    "iso3": "TKL",
    "phoneCode": "690"
  },
  {
    "es": "Tonga",
    "en": "Tonga",
    "iso2": "TO",
    "iso3": "TON",
    "phoneCode": "676"
  },
  {
    "es": "Trinidad y Tobago",
    "en": "Trinidad and Tobago",
    "iso2": "TT",
    "iso3": "TTO",
    "phoneCode": "1 868"
  },
  {
    "es": "Tunez",
    "en": "Tunisia",
    "iso2": "TN",
    "iso3": "TUN",
    "phoneCode": "216"
  },
  {
    "es": "Turkmenistán",
    "en": "Turkmenistan",
    "iso2": "TM",
    "iso3": "TKM",
    "phoneCode": "993"
  },
  {
    "es": "Turquía",
    "en": "Turkey",
    "iso2": "TR",
    "iso3": "TUR",
    "phoneCode": "90"
  },
  {
    "es": "Tuvalu",
    "en": "Tuvalu",
    "iso2": "TV",
    "iso3": "TUV",
    "phoneCode": "688"
  },
  {
    "es": "Ucrania",
    "en": "Ukraine",
    "iso2": "UA",
    "iso3": "UKR",
    "phoneCode": "380"
  },
  {
    "es": "Uganda",
    "en": "Uganda",
    "iso2": "UG",
    "iso3": "UGA",
    "phoneCode": "256"
  },
  {
    "es": "Uruguay",
    "en": "Uruguay",
    "iso2": "UY",
    "iso3": "URY",
    "phoneCode": "598"
  },
  {
    "es": "Uzbekistán",
    "en": "Uzbekistan",
    "iso2": "UZ",
    "iso3": "UZB",
    "phoneCode": "998"
  },
  {
    "es": "Vanuatu",
    "en": "Vanuatu",
    "iso2": "VU",
    "iso3": "VUT",
    "phoneCode": "678"
  },
  {
    "es": "Venezuela",
    "en": "Venezuela",
    "iso2": "VE",
    "iso3": "VEN",
    "phoneCode": "58"
  },
  {
    "es": "Vietnam",
    "en": "Vietnam",
    "iso2": "VN",
    "iso3": "VNM",
    "phoneCode": "84"
  },
  {
    "es": "Wallis y Futuna",
    "en": "Wallis and Futuna",
    "iso2": "WF",
    "iso3": "WLF",
    "phoneCode": "681"
  },
  {
    "es": "Yemen",
    "en": "Yemen",
    "iso2": "YE",
    "iso3": "YEM",
    "phoneCode": "967"
  },
  {
    "es": "Yibuti",
    "en": "Djibouti",
    "iso2": "DJ",
    "iso3": "DJI",
    "phoneCode": "253"
  },
  {
    "es": "Zambia",
    "en": "Zambia",
    "iso2": "ZM",
    "iso3": "ZMB",
    "phoneCode": "260"
  },
  {
    "es": "Zimbabue",
    "en": "Zimbabwe",
    "iso2": "ZW",
    "iso3": "ZWE",
    "phoneCode": "263"
  }
 ]

export default countries;