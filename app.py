import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import requests
import json
import time
import threading
import os
import uuid
import html
import re
import pyotp
import random
from datetime import datetime

# ============================================
# --- STYLE & BULLETPROOF COPY BUTTON PATCH ---
# ============================================
_old_inline_dict = InlineKeyboardButton.to_dict
def _new_inline_dict(self):
    d = _old_inline_dict(self)
    if hasattr(self, 'style'): 
        d['style'] = self.style
        
    if hasattr(self, 'custom_copy_text') and self.custom_copy_text:
        d['copy_text'] = {'text': str(self.custom_copy_text)}
        if 'callback_data' in d:
            del d['callback_data']
            
    return d
InlineKeyboardButton.to_dict = _new_inline_dict

_old_kb_dict = KeyboardButton.to_dict
def _new_kb_dict(self):
    d = _old_kb_dict(self)
    if hasattr(self, 'style'): d['style'] = self.style
    return d
KeyboardButton.to_dict = _new_kb_dict

# Helper functions to easily create colorful buttons
def ibtn(text, callback_data=None, url=None, style=None, copy_text_str=None):
    kwargs = {'text': text}
    
    if copy_text_str:
        kwargs['callback_data'] = "fake_copy_btn"
    else:
        if callback_data: kwargs['callback_data'] = callback_data
        if url: kwargs['url'] = url
            
    b = InlineKeyboardButton(**kwargs)
    if style: b.style = style
    
    if copy_text_str:
        b.custom_copy_text = copy_text_str
        
    return b

def rbtn(text, style=None):
    b = KeyboardButton(text=text)
    if style: b.style = style
    return b
# ============================================


# --- CONFIGURATION ---
TOKEN = "8141092190:AAF9aEv_K4eBbN1PILQScSfYdu0I8qGL2ug"
ADMIN_ID = 7787062914 # আপনার এডমিন আইডি দিন
BASE_URL = "http://185.190.142.81"
NEXA_API_KEY = "nxa_dbdde3ace678dd4563924461eea4a9e8a8801e98"

# বটের স্পিড রকেটের মতো ফাস্ট করার জন্য থ্রেড লিমিট ১০০ করা হলো
bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=100)
DATA_FILE = "dxa_bot_premium_data_v4.json"

active_polls = {}
user_states = {}
traffic_cooldowns = {}
data_lock = threading.RLock()
menu_message_id = {}
two_fa_message_id = {}
MAX_NUMBERS = 3  # Maximum 3 numbers per request

# --- Bangladesh Names Database ---
BD_MALE_FIRST = ["Md", "Mohammad", "Rahul", "Shakib", "Tamim", "Mushfiq", "Rakib", "Hasan", "Arif", "Sohel", "Rasel", "Rana", "Shanto", "Sakib", "Rifat", "Fahim", "Nayeem", "Tanvir", "Mahmud", "Riyad", "Mahadi", "Shamim", "Rashed", "Imran", "Nadim", "Sabbir", "Robiul", "Rakibul", "Saiful", "Kamal"]
BD_MALE_LAST = ["Hossain", "Rahman", "Hasan", "Islam", "Ahmed", "Khan", "Sheikh", "Mia", "Uddin", "Ali", "Akter", "Sarker", "Mondol", "Biswas", "Mahmud", "Chowdhury", "Haque", "Talukder", "Mollah", "Kazi"]
BD_FEMALE_FIRST = ["Fatema", "Ayesha", "Nusrat", "Jannat", "Sumaiya", "Sanjida", "Tasnim", "Sadia", "Rima", "Nadia", "Sharmin", "Farzana", "Mitu", "Priya", "Munni", "Rokeya", "Shanta", "Lamia", "Tamanna", "Roksana", "Mousumi", "Nasrin", "Rupa", "Shima", "Liza", "Sonali", "Jannatul", "Umme", "Halima"]
BD_FEMALE_LAST = ["Khatun", "Begum", "Akter", "Islam", "Sultana", "Parvin", "Jahan", "Ara", "Banu", "Nahar", "Yesmin", "Rahman", "Hossain", "Siddique", "Monir", "Jahanara", "Ferdous", "Nasrin", "Chowdhury", "Haque"]

# ============================================
# INTERNAL API SYSTEM - 4 API Keys
# ============================================
def __get_all_api_keys():
    """Main API + 3 Backup APIs"""
    keys = [NEXA_API_KEY]  # Main
    backup1 = "nxa_8d0eba994ba3094177d4dc1441af4cfc65455368"
    backup2 = "nxa_9ad17cea99f85040fde8eb4fabdbff6f47f1e613"
    backup3 = "nxa_7367a7ca4fb9e3ec44c574f668714df61a813162"
    
    for backup in [backup1, backup2, backup3]:
        if backup and backup not in keys:
            keys.append(backup)
    return keys

# --- ENHANCED LANGUAGE DETECTION ---
def detect_language(text):
    if not text: return "EN"
    text_str = str(text)
    
    # Arabic script detection
    if any('\u0600' <= c <= '\u06ff' for c in text_str):
        if any(w in text_str.lower() for w in ["كود", "رمز", "تحقق", "التحقق", "تأكيد", "واتساب"]): return "AR"
        if any(w in text_str.lower() for w in ["کوڈ", "رمز", "تصدیق", "واٹس"]): return "UR"
        if any(w in text_str.lower() for w in ["کد", "رمز", "تأیید", "واتس"]): return "FA"
        if any(w in text_str.lower() for w in ["پاسه", "رمز", "کوډ"]): return "PS"
        return "AR"
    
    # South Asian scripts
    if any('\u0980' <= c <= '\u09ff' for c in text_str): return "BN"
    if any('\u0900' <= c <= '\u097f' for c in text_str): return "HI"
    if any('\u0b80' <= c <= '\u0bff' for c in text_str): return "TA"
    if any('\u0c00' <= c <= '\u0c7f' for c in text_str): return "TE"
    if any('\u0c80' <= c <= '\u0cff' for c in text_str): return "KN"
    if any('\u0d00' <= c <= '\u0d7f' for c in text_str): return "ML"
    if any('\u0d80' <= c <= '\u0dff' for c in text_str): return "SI"
    
    # Southeast Asian scripts
    if any('\u1000' <= c <= '\u109f' for c in text_str): return "MY"
    if any('\u1780' <= c <= '\u17ff' for c in text_str): return "KM"
    if any('\u0e80' <= c <= '\u0eff' for c in text_str):
        if not any('\u0e00' <= c <= '\u0e7f' for c in text_str): return "LO"
    if any('\u0e00' <= c <= '\u0e7f' for c in text_str): return "TH"
    
    # East Asian scripts
    if any('\u4e00' <= c <= '\u9fff' for c in text_str): return "ZH"
    if any('\u3040' <= c <= '\u309f' for c in text_str): return "JA"
    if any('\u30a0' <= c <= '\u30ff' for c in text_str): return "JA"
    if any('\uac00' <= c <= '\ud7af' for c in text_str): return "KO"
    if any('\u1100' <= c <= '\u11ff' for c in text_str): return "KO"
    
    # European scripts
    if any('\u0400' <= c <= '\u04ff' for c in text_str): return "RU"
    if any('\u10a0' <= c <= '\u10ff' for c in text_str): return "KA"
    if any('\u0530' <= c <= '\u058f' for c in text_str): return "HY"
    if any('\u0370' <= c <= '\u03ff' for c in text_str): return "EL"
    if any('\u0590' <= c <= '\u05ff' for c in text_str): return "HE"
    if any('\u1200' <= c <= '\u137f' for c in text_str): return "AM"
    if any('\u0f00' <= c <= '\u0fff' for c in text_str): return "BO"
    
    # Vietnamese characters
    if any(c in 'ăâđêôơưàảãáạằẳẵắặầẩẫấậèẻẽéẹềểễếệìỉĩíịòỏõóọồổỗốộờởỡớợùủũúụừửữứựỳỷỹýỵ' for c in text_str): return "VN"
    
    # Latin script keyword detection
    text_lower = text_str.lower()
    if any(w in text_lower for w in ["código", "contraseña", "verificación", "clave", "acceso"]): return "ES"
    if any(w in text_lower for w in ["code secret", "vérification", "mot de passe", "confirmation", "votre code"]): return "FR"
    if any(w in text_lower for w in ["código de", "senha de", "verificação", "chave", "acesso"]): return "PT"
    if any(w in text_lower for w in ["doğrulama", "şifre", "kod", "giriş", "onay", "parola"]): return "TR"
    if any(w in text_lower for w in ["kode verifikasi", "pengesahan", "kata laluan", "kod", "sahkan"]): return "ID"
    if any(w in text_lower for w in ["bestätigungscode", "sicherheitscode", "passwort", "zugangscode", "verifizierung"]): return "DE"
    if any(w in text_lower for w in ["codice di", "verifica", "password", "conferma", "accesso"]): return "IT"
    if any(w in text_lower for w in ["verificatiecode", "bevestigingscode", "toegangscode", "wachtwoord"]): return "NL"
    if any(w in text_lower for w in ["kod weryfikacyjny", "hasło", "potwierdzenie", "dostęp", "klucz"]): return "PL"
    if any(w in text_lower for w in ["cod de", "parola", "confirmare", "verificare", "acces"]): return "RO"
    if any(w in text_lower for w in ["ověřovací kód", "heslo", "přístup", "potvrzení"]): return "CS"
    if any(w in text_lower for w in ["overovací kód", "heslo", "prístup", "potvrdenie"]): return "SK"
    if any(w in text_lower for w in ["megerősítő kód", "jelszó", "hozzáférés", "ellenőrzés"]): return "HU"
    if any(w in text_lower for w in ["verifieringskod", "lösenord", "bekräftelse", "åtkomst"]): return "SV"
    if any(w in text_lower for w in ["verifiseringskode", "passord", "bekreftelse", "tilgang"]): return "NO"
    if any(w in text_lower for w in ["bekræftelseskode", "adgangskode", "verifikation", "bekræft"]): return "DA"
    if any(w in text_lower for w in ["vahvistuskoodi", "salasana", "tunnus", "varmennus"]): return "FI"
    if any(w in text_lower for w in ["potvrdni kod", "lozinka", "pristup", "verifikacija"]): return "HR"
    if any(w in text_lower for w in ["potrditvena koda", "geslo", "dostop", "preverjanje"]): return "SL"
    if any(w in text_lower for w in ["patvirtinimo kodas", "slaptažodis", "prieiga", "patikrinimas"]): return "LT"
    if any(w in text_lower for w in ["apstiprinājuma kods", "parole", "piekļuve", "verifikācija"]): return "LV"
    if any(w in text_lower for w in ["kinnituskood", "parool", "juurdepääs", "kontroll"]): return "ET"
    if any(w in text_lower for w in ["code ng", "password", "pagpapatunay", "access", "kumpirmasyon"]): return "TL"
    
    return "EN"

# --- ENHANCED SERVICE DETECTION ---
SERVICE_SMS_KEYWORDS = {
    "whatsapp": ["whatsapp", "wa", "wap", "w/a", "whatsapp business", "whatsapp code", "whatsapp verification", "whatsapp kod"],
    "facebook": ["facebook", "fb", "meta", "fbook", "fb code", "facebook code", "fb confirmation"],
    "instagram": ["instagram", "insta", "ig", "ig code", "instagram code"],
    "telegram": ["telegram", "tg", "tele", "telegram code", "tg code"],
    "google": ["google", "gmail", "youtube", "g-", "google voice", "google verification"],
    "tiktok": ["tiktok", "tik tok", "tikvideo", "tiktok code", "tik code"],
    "snapchat": ["snapchat", "snap", "snap code", "snapchat code"],
    "twitter": ["twitter", "x.com", "x code", "your x confirmation", "twitter code"],
    "binance": ["binance", "bnb", "binances", "binance verification"],
    "melbet": ["melbet", "mel", "melbet code"],
    "bkash": ["bkash", "b-kash", "bkash code"],
    "nagad": ["nagad", "nagad code"],
    "imo": ["imo", "imo code", "imo verification"],
    "microsoft": ["microsoft", "ms", "outlook", "microsoft account", "ms code"],
    "apple": ["apple", "icloud", "itunes", "apple id", "apple code"],
    "paypal": ["paypal", "pay pal", "paypal code"],
    "uber": ["uber", "uber code", "uber verification"],
    "amazon": ["amazon", "amzn", "amazon code"],
    "netflix": ["netflix", "netflix code"],
    "discord": ["discord", "discord code"],
    "spotify": ["spotify", "spotify code"],
    "linkedin": ["linkedin", "linked in", "linkedin code"],
    "yahoo": ["yahoo", "yahoo code"],
    "viber": ["viber", "viber code"],
    "line": ["line", "line code", "line verification"],
    "wechat": ["wechat", "we chat", "wechat code"],
    "signal": ["signal", "signal code"],
}

def detect_service_from_sms(sms_text, app_name=""):
    if not sms_text and not app_name:
        return "Unknown"
    
    sms_lower = str(sms_text).lower() if sms_text else ""
    app_lower = str(app_name).lower() if app_name else ""
    
    if any(w in sms_lower for w in ["whatsapp", "wa ", " w/a", "whatsapp code", "whatsapp kod", "whatsapp verification"]):
        return "Whatsapp"
    
    for service, keywords in SERVICE_SMS_KEYWORDS.items():
        for kw in keywords:
            if kw in sms_lower:
                return service.title()
    
    if app_lower and app_lower != "custom search":
        for service, keywords in SERVICE_SMS_KEYWORDS.items():
            for kw in keywords:
                if kw in app_lower or app_lower in service:
                    return service.title()
        return app_name.title()
    
    return "Unknown"

# --- ALL 240+ COUNTRY FLAGS ---
COUNTRY_FLAGS = {
    "afghanistan": "🇦🇫", "albania": "🇦🇱", "algeria": "🇩🇿", "andorra": "🇦🇩", "angola": "🇦🇴",
    "antigua and barbuda": "🇦🇬", "argentina": "🇦🇷", "armenia": "🇦🇲", "australia": "🇦🇺",
    "austria": "🇦🇹", "azerbaijan": "🇦🇿", "bahamas": "🇧🇸", "bahrain": "🇧🇭",
    "bangladesh": "🇧🇩", "barbados": "🇧🇧", "belarus": "🇧🇾", "belgium": "🇧🇪", "belize": "🇧🇿",
    "benin": "🇧🇯", "bhutan": "🇧🇹", "bolivia": "🇧🇴", "bosnia and herzegovina": "🇧🇦",
    "botswana": "🇧🇼", "brazil": "🇧🇷", "brunei": "🇧🇳", "bulgaria": "🇧🇬",
    "burkina faso": "🇧🇫", "burundi": "🇧🇮", "cambodia": "🇰🇭", "cameroon": "🇨🇲",
    "canada": "🇨🇦", "cape verde": "🇨🇻", "central african republic": "🇨🇫", "chad": "🇹🇩",
    "chile": "🇨🇱", "china": "🇨🇳", "colombia": "🇨🇴", "comoros": "🇰🇲", "congo": "🇨🇬",
    "costa rica": "🇨🇷", "cote d'ivoire": "🇨🇮", "ivory coast": "🇨🇮",
    "croatia": "🇭🇷", "cuba": "🇨🇺", "cyprus": "🇨🇾", "czech republic": "🇨🇿",
    "denmark": "🇩🇰", "djibouti": "🇩🇯", "dominica": "🇩🇲", "dominican republic": "🇩🇴",
    "drc": "🇨🇩", "ecuador": "🇪🇨", "egypt": "🇪🇬", "el salvador": "🇸🇻",
    "equatorial guinea": "🇬🇶", "eritrea": "🇪🇷", "estonia": "🇪🇪", "eswatini": "🇸🇿",
    "ethiopia": "🇪🇹", "fiji": "🇫🇯", "finland": "🇫🇮", "france": "🇫🇷",
    "gabon": "🇬🇦", "gambia": "🇬🇲", "georgia": "🇬🇪", "germany": "🇩🇪", "ghana": "🇬🇭",
    "greece": "🇬🇷", "grenada": "🇬🇩", "guatemala": "🇬🇹", "guinea": "🇬🇳",
    "guinea bissau": "🇬🇼", "guyana": "🇬🇾", "haiti": "🇭🇹", "honduras": "🇭🇳",
    "hong kong": "🇭🇰", "hungary": "🇭🇺", "iceland": "🇮🇸", "india": "🇮🇳",
    "indonesia": "🇮🇩", "iran": "🇮🇷", "iraq": "🇮🇶", "ireland": "🇮🇪", "israel": "🇮🇱",
    "italy": "🇮🇹", "jamaica": "🇯🇲", "japan": "🇯🇵", "jordan": "🇯🇴", "kazakhstan": "🇰🇿",
    "kenya": "🇰🇪", "kiribati": "🇰🇮", "kosovo": "🇽🇰", "kuwait": "🇰🇼", "kyrgyzstan": "🇰🇬",
    "laos": "🇱🇦", "latvia": "🇱🇻", "lebanon": "🇱🇧", "lesotho": "🇱🇸", "liberia": "🇱🇷",
    "libya": "🇱🇾", "liechtenstein": "🇱🇮", "lithuania": "🇱🇹", "luxembourg": "🇱🇺",
    "macau": "🇲🇴", "madagascar": "🇲🇬", "malawi": "🇲🇼", "malaysia": "🇲🇾", "maldives": "🇲🇻",
    "mali": "🇲🇱", "malta": "🇲🇹", "marshall islands": "🇲🇭", "mauritania": "🇲🇷",
    "mauritius": "🇲🇺", "mexico": "🇲🇽", "micronesia": "🇫🇲", "moldova": "🇲🇩",
    "monaco": "🇲🇨", "mongolia": "🇲🇳", "montenegro": "🇲🇪", "morocco": "🇲🇦",
    "mozambique": "🇲🇿", "myanmar": "🇲🇲", "namibia": "🇳🇦", "nauru": "🇳🇷", "nepal": "🇳🇵",
    "netherlands": "🇳🇱", "new zealand": "🇳🇿", "nicaragua": "🇳🇮", "niger": "🇳🇪",
    "nigeria": "🇳🇬", "north korea": "🇰🇵", "north macedonia": "🇲🇰", "norway": "🇳🇴",
    "oman": "🇴🇲", "pakistan": "🇵🇰", "palau": "🇵🇼", "palestine": "🇵🇸", "panama": "🇵🇦",
    "papua new guinea": "🇵🇬", "paraguay": "🇵🇾", "peru": "🇵🇪", "philippines": "🇵🇭",
    "poland": "🇵🇱", "portugal": "🇵🇹", "qatar": "🇶🇦", "romania": "🇷🇴", "russia": "🇷🇺",
    "rwanda": "🇷🇼", "saint kitts and nevis": "🇰🇳", "saint lucia": "🇱🇨",
    "saint vincent and the grenadines": "🇻🇨", "samoa": "🇼🇸", "san marino": "🇸🇲",
    "sao tome and principe": "🇸🇹", "saudi arabia": "🇸🇦", "senegal": "🇸🇳", "serbia": "🇷🇸",
    "seychelles": "🇸🇨", "sierra leone": "🇸🇱", "singapore": "🇸🇬", "slovakia": "🇸🇰",
    "slovenia": "🇸🇮", "solomon islands": "🇸🇧", "somalia": "🇸🇴", "south africa": "🇿🇦",
    "south korea": "🇰🇷", "south sudan": "🇸🇸", "spain": "🇪🇸", "sri lanka": "🇱🇰",
    "sudan": "🇸🇩", "suriname": "🇸🇷", "sweden": "🇸🇪", "switzerland": "🇨🇭", "syria": "🇸🇾",
    "taiwan": "🇹🇼", "tajikistan": "🇹🇯", "tanzania": "🇹🇿", "thailand": "🇹🇭",
    "timor leste": "🇹🇱", "togo": "🇹🇬", "tonga": "🇹🇴", "trinidad and tobago": "🇹🇹",
    "tunisia": "🇹🇳", "turkey": "🇹🇷", "turkmenistan": "🇹🇲", "tuvalu": "🇹🇻",
    "uganda": "🇺🇬", "ukraine": "🇺🇦", "uae": "🇦🇪", "united arab emirates": "🇦🇪",
    "united kingdom": "🇬🇧", "uk": "🇬🇧", "usa": "🇺🇸", "united states": "🇺🇸",
    "uruguay": "🇺🇾", "uzbekistan": "🇺🇿", "vanuatu": "🇻🇺", "vatican city": "🇻🇦",
    "venezuela": "🇻🇪", "vietnam": "🇻🇳", "yemen": "🇾🇪", "zambia": "🇿🇲", "zimbabwe": "🇿🇼",
    "anguilla": "🇦🇮", "aruba": "🇦🇼", "bermuda": "🇧🇲", "british virgin islands": "🇻🇬",
    "cayman islands": "🇰🇾", "curacao": "🇨🇼", "falkland islands": "🇫🇰",
    "french guiana": "🇬🇫", "greenland": "🇬🇱", "guadeloupe": "🇬🇵",
    "guam": "🇬🇺", "martinique": "🇲🇶", "mayotte": "🇾🇹", "montserrat": "🇲🇸",
    "new caledonia": "🇳🇨", "niue": "🇳🇺", "norfolk island": "🇳🇫",
    "northern mariana islands": "🇲🇵", "pitcairn islands": "🇵🇳", "puerto rico": "🇵🇷",
    "reunion": "🇷🇪", "saint helena": "🇸🇭", "tokelau": "🇹🇰",
    "turks and caicos islands": "🇹🇨", "us virgin islands": "🇻🇮",
    "wallis and futuna": "🇼🇫", "western sahara": "🇪🇭", "cook islands": "🇨🇰",
    "french polynesia": "🇵🇫", "gibraltar": "🇬🇮", "faroe islands": "🇫🇴",
    "svalbard and jan mayen": "🇸🇯", "aland islands": "🇦🇽", "jersey": "🇯🇪",
    "guernsey": "🇬🇬", "isle of man": "🇮🇲", "saint pierre and miquelon": "🇵🇲",
    "sint maarten": "🇸🇽", "bonaire": "🇧🇶"
}

COUNTRY_ISO = {
    "afghanistan": "AF", "albania": "AL", "algeria": "DZ", "andorra": "AD", "angola": "AO",
    "antigua and barbuda": "AG", "argentina": "AR", "armenia": "AM", "australia": "AU",
    "austria": "AT", "azerbaijan": "AZ", "bahamas": "BS", "bahrain": "BH", "bangladesh": "BD",
    "barbados": "BB", "belarus": "BY", "belgium": "BE", "belize": "BZ", "benin": "BJ",
    "bhutan": "BT", "bolivia": "BO", "bosnia and herzegovina": "BA", "botswana": "BW",
    "brazil": "BR", "brunei": "BN", "bulgaria": "BG", "burkina faso": "BF", "burundi": "BI",
    "cambodia": "KH", "cameroon": "CM", "canada": "CA", "cape verde": "CV",
    "central african republic": "CF", "chad": "TD", "chile": "CL", "china": "CN",
    "colombia": "CO", "comoros": "KM", "congo": "CG", "costa rica": "CR", "cote d'ivoire": "CI",
    "ivory coast": "CI", "croatia": "HR", "cuba": "CU", "cyprus": "CY", "czech republic": "CZ",
    "denmark": "DK", "djibouti": "DJ", "dominica": "DM", "dominican republic": "DO",
    "drc": "CD", "ecuador": "EC", "egypt": "EG", "el salvador": "SV", "equatorial guinea": "GQ",
    "eritrea": "ER", "estonia": "EE", "eswatini": "SZ", "ethiopia": "ET", "fiji": "FJ",
    "finland": "FI", "france": "FR", "gabon": "GA", "gambia": "GM", "georgia": "GE",
    "germany": "DE", "ghana": "GH", "greece": "GR", "grenada": "GD", "guatemala": "GT",
    "guinea": "GN", "guinea bissau": "GW", "guyana": "GY", "haiti": "HT", "honduras": "HN",
    "hong kong": "HK", "hungary": "HU", "iceland": "IS", "india": "IN", "indonesia": "ID",
    "iran": "IR", "iraq": "IQ", "ireland": "IE", "israel": "IL", "italy": "IT",
    "jamaica": "JM", "japan": "JP", "jordan": "JO", "kazakhstan": "KZ", "kenya": "KE",
    "kiribati": "KI", "kosovo": "XK", "kuwait": "KW", "kyrgyzstan": "KG", "laos": "LA",
    "latvia": "LV", "lebanon": "LB", "lesotho": "LS", "liberia": "LR", "libya": "LY",
    "liechtenstein": "LI", "lithuania": "LT", "luxembourg": "LU", "macau": "MO",
    "madagascar": "MG", "malawi": "MW", "malaysia": "MY", "maldives": "MV", "mali": "ML",
    "malta": "MT", "marshall islands": "MH", "mauritania": "MR", "mauritius": "MU",
    "mexico": "MX", "micronesia": "FM", "moldova": "MD", "monaco": "MC", "mongolia": "MN",
    "montenegro": "ME", "morocco": "MA", "mozambique": "MZ", "myanmar": "MM", "namibia": "NA",
    "nauru": "NR", "nepal": "NP", "netherlands": "NL", "new zealand": "NZ", "nicaragua": "NI",
    "niger": "NE", "nigeria": "NG", "north korea": "KP", "north macedonia": "MK", "norway": "NO",
    "oman": "OM", "pakistan": "PK", "palau": "PW", "palestine": "PS", "panama": "PA",
    "papua new guinea": "PG", "paraguay": "PY", "peru": "PE", "philippines": "PH", "poland": "PL",
    "portugal": "PT", "qatar": "QA", "romania": "RO", "russia": "RU", "rwanda": "RW",
    "saint kitts and nevis": "KN", "saint lucia": "LC", "saint vincent and the grenadines": "VC",
    "samoa": "WS", "san marino": "SM", "sao tome and principe": "ST", "saudi arabia": "SA",
    "senegal": "SN", "serbia": "RS", "seychelles": "SC", "sierra leone": "SL", "singapore": "SG",
    "slovakia": "SK", "slovenia": "SI", "solomon islands": "SB", "somalia": "SO",
    "south africa": "ZA", "south korea": "KR", "south sudan": "SS", "spain": "ES",
    "sri lanka": "LK", "sudan": "SD", "suriname": "SR", "sweden": "SE", "switzerland": "CH",
    "syria": "SY", "taiwan": "TW", "tajikistan": "TJ", "tanzania": "TZ", "thailand": "TH",
    "timor leste": "TL", "togo": "TG", "tonga": "TO", "trinidad and tobago": "TT",
    "tunisia": "TN", "turkey": "TR", "turkmenistan": "TM", "tuvalu": "TV", "uganda": "UG",
    "ukraine": "UA", "uae": "AE", "united arab emirates": "AE", "united kingdom": "GB", "uk": "GB",
    "usa": "US", "united states": "US", "uruguay": "UY", "uzbekistan": "UZ", "vanuatu": "VU",
    "vatican city": "VA", "venezuela": "VE", "vietnam": "VN", "yemen": "YE", "zambia": "ZM", "zimbabwe": "ZW",
    "anguilla": "AI", "aruba": "AW", "bermuda": "BM", "cayman islands": "KY", "curacao": "CW",
    "greenland": "GL", "guam": "GU", "puerto rico": "PR", "reunion": "RE", "western sahara": "EH"
}

PHONE_TO_COUNTRY = {
    "1": "United States", "7": "Russia", "20": "Egypt", "27": "South Africa",
    "30": "Greece", "31": "Netherlands", "32": "Belgium", "33": "France",
    "34": "Spain", "36": "Hungary", "39": "Italy", "40": "Romania",
    "41": "Switzerland", "43": "Austria", "44": "United Kingdom", "45": "Denmark",
    "46": "Sweden", "47": "Norway", "48": "Poland", "49": "Germany",
    "51": "Peru", "52": "Mexico", "53": "Cuba", "54": "Argentina",
    "55": "Brazil", "56": "Chile", "57": "Colombia", "58": "Venezuela",
    "60": "Malaysia", "61": "Australia", "62": "Indonesia", "63": "Philippines",
    "64": "New Zealand", "65": "Singapore", "66": "Thailand", "81": "Japan",
    "82": "South Korea", "84": "Vietnam", "86": "China", "90": "Turkey",
    "91": "India", "92": "Pakistan", "93": "Afghanistan", "94": "Sri Lanka",
    "95": "Myanmar", "98": "Iran", "211": "South Sudan", "212": "Morocco",
    "213": "Algeria", "216": "Tunisia", "218": "Libya", "220": "Gambia",
    "221": "Senegal", "222": "Mauritania", "223": "Mali", "224": "Guinea",
    "225": "Cote d'Ivoire", "226": "Burkina Faso", "227": "Niger", "228": "Togo",
    "229": "Benin", "230": "Mauritius", "231": "Liberia", "232": "Sierra Leone",
    "233": "Ghana", "234": "Nigeria", "235": "Chad", "236": "Central African Republic",
    "237": "Cameroon", "238": "Cape Verde", "239": "Sao Tome and Principe", "240": "Equatorial Guinea",
    "241": "Gabon", "242": "Congo", "243": "DRC", "244": "Angola", "245": "Guinea Bissau",
    "249": "Sudan", "250": "Rwanda", "251": "Ethiopia", "252": "Somalia", "253": "Djibouti",
    "254": "Kenya", "255": "Tanzania", "256": "Uganda", "257": "Burundi",
    "258": "Mozambique", "260": "Zambia", "261": "Madagascar", "262": "Reunion",
    "263": "Zimbabwe", "264": "Namibia", "265": "Malawi", "266": "Lesotho",
    "267": "Botswana", "268": "Eswatini", "269": "Comoros", "291": "Eritrea",
    "350": "Gibraltar", "351": "Portugal", "352": "Luxembourg", "353": "Ireland",
    "354": "Iceland", "355": "Albania", "356": "Malta", "357": "Cyprus",
    "358": "Finland", "359": "Bulgaria", "370": "Lithuania", "371": "Latvia",
    "372": "Estonia", "373": "Moldova", "374": "Armenia", "375": "Belarus",
    "376": "Andorra", "377": "Monaco", "378": "San Marino", "379": "Vatican City",
    "380": "Ukraine", "381": "Serbia", "382": "Montenegro", "383": "Kosovo",
    "385": "Croatia", "386": "Slovenia", "387": "Bosnia and Herzegovina",
    "389": "North Macedonia", "420": "Czech Republic", "421": "Slovakia",
    "423": "Liechtenstein", "501": "Belize", "502": "Guatemala", "503": "El Salvador",
    "504": "Honduras", "505": "Nicaragua", "506": "Costa Rica", "507": "Panama",
    "509": "Haiti", "591": "Bolivia", "592": "Guyana", "593": "Ecuador",
    "595": "Paraguay", "597": "Suriname", "598": "Uruguay", "670": "Timor Leste",
    "673": "Brunei", "674": "Nauru", "675": "Papua New Guinea",
    "676": "Tonga", "677": "Solomon Islands", "678": "Vanuatu", "679": "Fiji",
    "680": "Palau", "685": "Samoa", "686": "Kiribati", "687": "New Caledonia",
    "688": "Tuvalu", "689": "French Polynesia", "691": "Micronesia",
    "692": "Marshall Islands", "850": "North Korea", "852": "Hong Kong",
    "853": "Macau", "855": "Cambodia", "856": "Laos", "880": "Bangladesh",
    "886": "Taiwan", "960": "Maldives", "961": "Lebanon", "962": "Jordan",
    "963": "Syria", "964": "Iraq", "965": "Kuwait", "966": "Saudi Arabia",
    "967": "Yemen", "968": "Oman", "970": "Palestine", "971": "UAE",
    "972": "Israel", "973": "Bahrain", "974": "Qatar", "975": "Bhutan",
    "976": "Mongolia", "977": "Nepal", "992": "Tajikistan", "993": "Turkmenistan",
    "994": "Azerbaijan", "995": "Georgia", "996": "Kyrgyzstan", "998": "Uzbekistan"
}

SERVICE_SHORTS = {
    "whatsapp": "WA", "facebook": "FB", "instagram": "IG", "telegram": "TG",
    "twitter": "TW", "google": "GO", "gmail": "GM", "youtube": "YT",
    "apple": "AP", "microsoft": "MS", "tiktok": "TT", "snapchat": "SC",
    "binance": "BN", "melbet": "MB", "bkash": "BK", "nagad": "NG",
    "imo": "IMO", "paypal": "PP", "uber": "UB", "amazon": "AMZ",
    "netflix": "NF", "discord": "DC", "spotify": "SP", "linkedin": "LI",
    "yahoo": "YH", "viber": "VB", "line": "LN", "wechat": "WC", "signal": "SG"
}

EMOJI_COLLECTION = {
    "whatsapp": "💚", "facebook": "📘", "instagram": "📷", "telegram": "✈️",
    "twitter": "𝕏", "google": "🔍", "gmail": "📧", "youtube": "🎬",
    "apple": "🍎", "microsoft": "💻", "tiktok": "🎵", "snapchat": "👻",
    "binance": "💰", "melbet": "🎰", "bkash": "💳", "nagad": "📲",
    "imo": "💭", "paypal": "💵", "uber": "🚗", "amazon": "📦",
    "netflix": "🎬", "discord": "💬", "spotify": "🎧", "linkedin": "💼",
    "yahoo": "📧", "viber": "💜", "line": "💚", "wechat": "💚", "signal": "🔒"
}

def get_country_flag(country_name):
    if not country_name: return "🌍"
    name = str(country_name).lower().strip()
    if name in COUNTRY_FLAGS: return COUNTRY_FLAGS[name]
    for country, flag in COUNTRY_FLAGS.items():
        if len(country) >= 4 and (country in name or name in country): return flag
    return "🌍"

def get_iso_code(country_name):
    name = str(country_name).lower().strip()
    if name in COUNTRY_ISO: return COUNTRY_ISO[name]
    for country, iso in COUNTRY_ISO.items():
        if country in name or name in country: return iso
    return name[:2].upper() if len(name) >= 2 else "UN"

def emo(keyword, default="✨"):
    if not keyword: return default
    kw = str(keyword).lower().strip()
    if kw in EMOJI_COLLECTION: return EMOJI_COLLECTION[kw]
    for key, emoji in EMOJI_COLLECTION.items():
        if len(key) >= 3 and key in kw: return emoji
    flag = get_country_flag(kw)
    if flag != "🌍": return flag
    return default

def get_short_service(service_name):
    name = str(service_name).lower().strip()
    if name in SERVICE_SHORTS: return SERVICE_SHORTS[name]
    return name[:2].upper() if len(name) >= 2 else "SV"

def mask_number(phone):
    phone_str = str(phone).replace('+', '')
    if len(phone_str) >= 6:
        return f"{phone_str[:3]}XXX{phone_str[-3:]}"
    return phone_str

def get_country_from_number(phone_number):
    number = str(phone_number).replace('+', '').strip()
    for code_len in [3, 2, 1]:
        if len(number) >= code_len:
            code = number[:code_len]
            if code in PHONE_TO_COUNTRY: return PHONE_TO_COUNTRY[code]
    return "Unknown"

def generate_bd_name(gender):
    if gender == "MALE":
        first = random.choice(BD_MALE_FIRST)
        last = random.choice(BD_MALE_LAST)
    else:
        first = random.choice(BD_FEMALE_FIRST)
        last = random.choice(BD_FEMALE_LAST)
    return first, last

def format_url(url):
    url = url.strip()
    if url and not url.startswith(('http://', 'https://', 'tg://')): return 'https://' + url
    return url

def extract_channel_username(url):
    if "t.me/" in url:
        parts = url.split("t.me/")
        if len(parts) > 1:
            username = parts[1].split("/")[0].split("?")[0]
            if not username.startswith("@"): username = "@" + username
            return username
    return ""

def clean_html_tags(text):
    text = re.sub(r'<tg-emoji[^>]*>', '', text)
    text = re.sub(r'</tg-emoji>', '', text)
    return text

def safe_edit(chat_id, text, reply_markup=None, message_id=None):
    clean_text = clean_html_tags(text)
    target_msg_id = message_id if message_id else (menu_message_id.get(chat_id))
    if target_msg_id:
        try:
            return bot.edit_message_text(clean_text, chat_id=chat_id, message_id=target_msg_id, parse_mode="HTML", reply_markup=reply_markup)
        except Exception as e:
            if "message is not modified" in str(e).lower(): return None # মেসেজ সেম থাকলে এডিট স্কিপ করবে
    try:
        msg = bot.send_message(chat_id, clean_text, parse_mode="HTML", reply_markup=reply_markup)
        if msg: menu_message_id[chat_id] = msg.message_id
        return msg
    except: return None

def safe_edit_2fa(chat_id, text, reply_markup=None):
    try:
        clean_text = clean_html_tags(text)
        if chat_id in two_fa_message_id:
            return bot.edit_message_text(clean_text, chat_id=chat_id, message_id=two_fa_message_id[chat_id], parse_mode="HTML", reply_markup=reply_markup)
        else:
            msg = bot.send_message(chat_id, clean_text, parse_mode="HTML", reply_markup=reply_markup)
            if msg:
                two_fa_message_id[chat_id] = msg.message_id
            return msg
    except:
        return None

def safe_send(chat_id, text, reply_markup=None, reply_to=None):
    try:
        clean_text = clean_html_tags(text)
        msg = bot.send_message(chat_id, clean_text, parse_mode="HTML", reply_markup=reply_markup, reply_to_message_id=reply_to)
        if msg:
            menu_message_id[chat_id] = msg.message_id
        return msg
    except:
        return None

def load_data():
    with data_lock:
        if not os.path.exists(DATA_FILE):
            default_data = {
                "users": [], "services_data": {}, "forward_groups": [],
                "main_otp_link": "https://t.me/", "watermark": "DXA UNIVERSE",
                "force_join_enabled": False, "force_join_channels": [],
                "traffic_group_link": "https://t.me/+aBpN_vJ4QYYxM2Yy",
                "otp_counts": {}, "leaderboard": {},
                "balances": {}, "refers": {}, "withdrawals": [],
                "settings": {
                    "withdraw_status": True, "min_withdraw": 50, "otp_reward": 5, 
                    "refer_reward": 10, "withdraw_group": "", "cooldown": 60,
                    "num_per_request": 3, "support_link": "https://t.me/ADMIN_ASIK",
                    "withdraw_methods": ["bKash", "Nagad"]
                },
                "api_keys": [], "extra_admins": [], "banned_users": []
            }
            with open(DATA_FILE, "w", encoding='utf-8') as f: json.dump(default_data, f, indent=4)
            return default_data
        with open(DATA_FILE, "r", encoding='utf-8') as f:
            data = json.load(f)
            if "force_join_enabled" not in data: data["force_join_enabled"] = False
            if "force_join_channels" not in data: data["force_join_channels"] = []
            if "traffic_group_link" not in data: data["traffic_group_link"] = "https://t.me/+aBpN_vJ4QYYxM2Yy"
            if "otp_counts" not in data: data["otp_counts"] = {}
            if "leaderboard" not in data: data["leaderboard"] = {}
            if "balances" not in data: data["balances"] = {}
            if "refers" not in data: data["refers"] = {}
            if "withdrawals" not in data: data["withdrawals"] = []
            if "settings" not in data: 
                data["settings"] = {
                    "withdraw_status": True, "min_withdraw": 50, "otp_reward": 5, 
                    "refer_reward": 10, "withdraw_group": "", "cooldown": 60,
                    "num_per_request": 3, "support_link": "https://t.me/ADMIN_ASIK",
                    "withdraw_methods": ["bKash", "Nagad"]
                }
            if "api_keys" not in data: data["api_keys"] = []
            if "extra_admins" not in data: data["extra_admins"] = []
            if "banned_users" not in data: data["banned_users"] = []
            return data

def save_data(data):
    with data_lock:
        with open(DATA_FILE, "w", encoding='utf-8') as f: json.dump(data, f, indent=4)

def add_user(user_id):
    data = load_data()
    if user_id not in data.get("users", []):
        data.setdefault("users", []).append(user_id)
        save_data(data)

def update_leaderboard(user_id, first_name):
    data = load_data()
    user_id_str = str(user_id)
    if "otp_counts" not in data: data["otp_counts"] = {}
    if "leaderboard" not in data: data["leaderboard"] = {}
    if user_id_str not in data["otp_counts"]: data["otp_counts"][user_id_str] = 0
    data["otp_counts"][user_id_str] += 1
    data["leaderboard"][user_id_str] = {"name": first_name or f"User{user_id}", "count": data["otp_counts"][user_id_str]}
    save_data(data)

def get_total_ranges():
    data = load_data()
    count = 0
    for srv in data.get("services_data", {}).values():
        for cnt in srv.get("countries", {}).values():
            count += len(cnt.get("ranges", {}))
    return count

def check_force_join(user_id):
    if user_id == ADMIN_ID: return True
    data = load_data()
    if not data.get("force_join_enabled"): return True
    for link in data.get("force_join_channels", []):
        chat_username = extract_channel_username(link)
        if not chat_username: continue
        try:
            member = bot.get_chat_member(chat_username, user_id)
            if member.status not in ['member', 'administrator', 'creator']: return False
        except: pass
    return True

# ==================== MENU MARKUPS ====================

def get_main_menu(user_id):
    data = load_data()
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(rbtn("📱 GET NUMBER", "primary"), rbtn("📊 TRAFFIC", "success"))
    markup.add(rbtn("💰 BALANCE", "primary"), rbtn("💸 WITHDRAWAL", "success"))
    markup.add(rbtn("🎁 REFER", "primary"), rbtn("🛠️ SUPPORT", "success"))
    markup.add(rbtn("🔐 2FA ONLINE", "primary"), rbtn("👤 FAKE INFO", "success"))
    markup.add(rbtn("🏆 LEADERBOARD", "primary"))
    if user_id == ADMIN_ID or user_id in data.get("extra_admins", []): 
        markup.add(rbtn("⚙️ ADMIN PANEL", "danger"))
    return markup

def get_2fa_menu():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(ibtn("🔐 GENERATE 2FA CODE", callback_data="2fa_generate", style="success"),
               ibtn("🔙 BACK TO MAIN MENU", callback_data="2fa_back", style="danger"))
    return markup

def get_fake_info_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(ibtn("👨 MALE", callback_data="fake_male", style="primary"),
               ibtn("👩 FEMALE", callback_data="fake_female", style="success"))
    markup.add(ibtn("🔙 BACK", callback_data="fake_back", style="danger"))
    return markup

def get_leaderboard_menu():
    markup = InlineKeyboardMarkup()
    markup.add(ibtn("🔄 REFRESH", callback_data="refresh_leaderboard", style="success"))
    markup.add(ibtn("❌ CLOSE", callback_data="close_menu", style="danger"))
    return markup

def get_admin_menu(user_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(ibtn("⚙️ SYSTEM", callback_data="admin_system", style="primary"),
               ibtn("👤 USER VIEW", callback_data="admin_user_view", style="success"))
    markup.add(ibtn("🛠️ MANAGE SERVICES", callback_data="admin_manage_service", style="primary"),
               ibtn("📢 BROADCAST", callback_data="admin_broadcast", style="success"))
    markup.add(ibtn("🔗 GROUP SETTINGS", callback_data="admin_group_settings", style="primary"),
               ibtn("📊 TRAFFIC GROUP", callback_data="admin_traffic_group", style="success"))
    markup.add(ibtn("📣 FORCE JOIN", callback_data="admin_force_join", style="primary"),
               ibtn("💎 WATERMARK", callback_data="admin_set_watermark", style="success"))
    
    if user_id == ADMIN_ID:
        markup.add(ibtn("🔑 API MANAGEMENT", callback_data="admin_api_manage", style="primary"),
                   ibtn("👮 MANAGE ADMIN", callback_data="admin_manage_admins", style="success"))
    return markup

def get_force_join_menu():
    data = load_data()
    is_enabled = data.get("force_join_enabled", False)
    channels = data.get("force_join_channels", [])
    status_text = "🟢 ENABLED" if is_enabled else "🔴 DISABLED"
    status_style = "success" if is_enabled else "danger"
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(ibtn(f"TOGGLE: {status_text}", callback_data="toggle_force_join", style=status_style))
    for idx, link in enumerate(channels):
        markup.add(ibtn(f"❌ REMOVE: {link}", callback_data=f"delfjc_{idx}", style="danger"))
    markup.add(ibtn("➕ ADD CHANNEL", callback_data="add_fjc", style="success"))
    markup.add(ibtn("🔙 BACK", callback_data="back_to_admin", style="primary"))
    return markup

def get_group_settings_menu():
    data = load_data()
    markup = InlineKeyboardMarkup(row_width=1)
    otp_link = data.get("main_otp_link", "")
    markup.add(ibtn("🔗 SET OTP GROUP LINK", callback_data="set_main_otp_link", style="primary"))
    if otp_link and otp_link != "https://t.me/":
        markup.add(ibtn("🗑️ REMOVE OTP LINK", callback_data="del_main_otp_link", style="danger"))
    markup.add(ibtn("➕ ADD FORWARD GROUP", callback_data="add_fwd_group", style="success"))
    fwd_groups = data.get("forward_groups", [])
    if fwd_groups:
        for grp in fwd_groups:
            btn_count = len(grp.get('buttons', []))
            markup.add(ibtn(f"⚙️ {grp['chat_id']} [{btn_count} BTNS]", callback_data=f"editgrp_{grp['chat_id']}", style="primary"))
    markup.add(ibtn("🔙 BACK", callback_data="back_to_admin", style="danger"))
    return markup

def get_traffic_group_menu():
    data = load_data()
    current_link = data.get("traffic_group_link", "https://t.me/+aBpN_vJ4QYYxM2Yy")
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(ibtn("✏️ EDIT LINK", callback_data="edit_traffic_link", style="primary"))
    markup.add(ibtn("🗑️ REMOVE LINK", callback_data="del_traffic_link", style="danger"))
    markup.add(ibtn("🔙 BACK", callback_data="back_to_admin", style="primary"))
    return current_link, markup

def show_edit_group_menu(chat_id, grp_id, message_id=None):
    data = load_data()
    grp = next((g for g in data.get("forward_groups", []) if str(g["chat_id"]) == str(grp_id)), None)
    if not grp:
        safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 🔗 GROUP SETTINGS 》", get_group_settings_menu())
        return
    text = f"━━━━━━━━━━━━━━━\n《 ⚙️ MANAGE GROUP 》\n━━━━━━━━━━━━━━━\n📱 ID: <code>{grp_id}</code>\n🔘 BUTTONS: {len(grp.get('buttons', []))}"
    markup = InlineKeyboardMarkup(row_width=1)
    for idx, btn in enumerate(grp.get("buttons", [])):
        markup.add(ibtn(f"❌ {btn['name']}", callback_data=f"delgrpbtn_{grp_id}_{idx}", style="danger"))
    markup.add(ibtn("➕ ADD BUTTON", callback_data=f"addgrpbtn_{grp_id}", style="success"))
    markup.add(ibtn("🗑️ DELETE GROUP", callback_data=f"delfwd_{grp_id}", style="danger"))
    markup.add(ibtn("🔙 BACK", callback_data="admin_group_settings", style="primary"))
    safe_edit(chat_id, text, markup, message_id)

def show_admin_services(chat_id, message_id=None):
    data = load_data()
    markup = InlineKeyboardMarkup(row_width=2)
    for srv_id, srv in data.get("services_data", {}).items():
        markup.add(ibtn(text=f"📁 {srv['name'].upper()}", callback_data=f"adm_s|{srv_id}", style="primary"))
    markup.add(ibtn("➕ ADD SERVICE", callback_data="add_srv", style="success"))
    markup.add(ibtn("🔙 BACK", callback_data="back_to_admin", style="danger"))
    text = f"━━━━━━━━━━━━━━━\n《 🛠️ SERVICES 》\n━━━━━━━━━━━━━━━\nSELECT A SERVICE:"
    safe_edit(chat_id, text, markup, message_id)

def show_admin_countries(chat_id, srv_id, message_id=None):
    data = load_data()
    srv_data = data.get("services_data", {}).get(srv_id)
    if not srv_data: return
    markup = InlineKeyboardMarkup(row_width=2)
    for cnt_id, cnt in srv_data.get("countries", {}).items():
        flag = get_country_flag(cnt['name'])
        markup.add(ibtn(text=f"{flag} {cnt['name'].upper()}", callback_data=f"adm_c|{srv_id}|{cnt_id}", style="primary"))
    markup.add(ibtn("➕ ADD COUNTRY", callback_data=f"add_cnt|{srv_id}", style="success"))
    markup.add(ibtn("🗑️ DELETE SERVICE", callback_data=f"del_srv|{srv_id}", style="danger"))
    markup.add(ibtn("🔙 BACK", callback_data="admin_manage_service", style="primary"))
    text = f"━━━━━━━━━━━━━━━\n《 🌍 COUNTRIES 》\n━━━━━━━━━━━━━━━\n{html.escape(srv_data['name'].upper())}\nSELECT COUNTRY:"
    safe_edit(chat_id, text, markup, message_id)

def show_admin_ranges(chat_id, srv_id, cnt_id, message_id=None):
    data = load_data()
    srv_data = data.get("services_data", {}).get(srv_id)
    cnt_data = srv_data.get("countries", {}).get(cnt_id) if srv_data else None
    if not cnt_data: return
    flag = get_country_flag(cnt_data['name'])
    markup = InlineKeyboardMarkup(row_width=1)
    for rng_id, rng_val in cnt_data.get("ranges", {}).items():
        markup.add(ibtn(text=f"❌ {rng_val}", callback_data=f"del_rng|{srv_id}|{cnt_id}|{rng_id}", style="danger"))
    markup.add(ibtn("➕ ADD RANGE", callback_data=f"add_rng|{srv_id}|{cnt_id}", style="success"))
    markup.add(ibtn("🗑️ DELETE COUNTRY", callback_data=f"del_cnt|{srv_id}|{cnt_id}", style="danger"))
    markup.add(ibtn("🔙 BACK", callback_data=f"adm_s|{srv_id}", style="primary"))
    text = f"{flag} → {html.escape(srv_data['name'].upper())} → {html.escape(cnt_data['name'].upper())}\n━━━━━━━━━━━━━━━\nTAP TO DELETE:"
    safe_edit(chat_id, text, markup, message_id)

# ==================== HANDLERS ====================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.chat.type != 'private':
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    bot.clear_step_handler_by_chat_id(chat_id)
    
    # 🎁 Referral Checking
    data = load_data()
    if len(message.text.split()) > 1:
        ref_id = message.text.split()[1]
        if ref_id.isdigit() and int(ref_id) != user_id and user_id not in data.get("users", []):
            reward = data.get("settings", {}).get("refer_reward", 10)
            data["refers"][ref_id] = data.get("refers", {}).get(ref_id, 0) + 1
            data["balances"][ref_id] = data.get("balances", {}).get(ref_id, 0) + reward
            try: 
                ref_msg = f"━━━━━━━━━━━━━━━\n《 🎁 REFER BONUS 》\n━━━━━━━━━━━━━━━\n🎉 SOMEONE JOINED USING YOUR LINK!\n\n💰 BONUS: <b>+{reward} ৳</b>\n💵 NEW BALANCE: <b>{data['balances'][ref_id]} ৳</b>\n━━━━━━━━━━━━━━━"
                safe_send(ref_id, ref_msg)
            except: pass
            save_data(data)
            
    add_user(user_id)
    if not check_force_join(user_id):
        show_force_join_message(chat_id, message.message_id)
        return
    show_main_menu(chat_id, message.from_user.first_name, message.message_id)

def show_force_join_message(chat_id, reply_to=None):
    data = load_data()
    channels = data.get("force_join_channels", [])
    text = f"━━━━━━━━━━━━━━━\n《 ⚠️ ACCESS DENIED 》\n━━━━━━━━━━━━━━━\n📢 JOIN OUR CHANNELS TO USE THIS BOT\n\nCLICK JOINED AFTER JOINING"
    markup = InlineKeyboardMarkup()
    for link in channels:
        markup.add(ibtn(text="📢 JOIN CHANNEL", url=link, style="primary"))
    markup.add(ibtn(text="✅ JOINED ✅", callback_data="check_join", style="success"))
    safe_send(chat_id, text, markup, reply_to=reply_to)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if message.chat.type != 'private':
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text
    
    # Delete User Message for Clean UI
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    # মেইন মেনুর বাটনে (যেমন GET NUMBER) চাপলে পুরোনো মেসেজ মুছে নতুন মেসেজ নিচে আসবে
    try:
        if chat_id in menu_message_id:
            bot.delete_message(chat_id, menu_message_id[chat_id])
            del menu_message_id[chat_id]
    except: pass
    
    bot.clear_step_handler_by_chat_id(chat_id)
    add_user(user_id)
    
    data = load_data()
    if user_id in data.get("banned_users", []):
        safe_send(chat_id, "━━━━━━━━━━━━━━━\n《 🚫 ACCOUNT BANNED 》\n━━━━━━━━━━━━━━━\nYOU ARE BANNED BY ADMIN!")
        return
    
    if not check_force_join(user_id):
        show_force_join_message(chat_id)
        return

    if "GET NUMBER" in text or "📱" in text: show_user_services(chat_id)
    elif "TRAFFIC" in text or "📊" in text: show_traffic_info(chat_id)
    elif "BALANCE" in text or "💰" in text: show_balance(chat_id)
    elif "WITHDRAWAL" in text or "💸" in text: show_withdraw(chat_id)
    elif "REFER" in text or "🎁" in text: show_refer(chat_id)
    elif "SUPPORT" in text or "🛠️" in text: show_support(chat_id, message.from_user.first_name)
    elif "2FA ONLINE" in text or "🔐" in text: show_2fa_menu_display(chat_id)
    elif "FAKE INFO" in text or "👤" in text: show_fake_info(chat_id)
    elif "LEADERBOARD" in text or "🏆" in text: show_leaderboard(chat_id)
    elif ("ADMIN PANEL" in text or "⚙️" in text) and (user_id == ADMIN_ID or user_id in data.get("extra_admins", [])): show_admin_panel(chat_id)

# ==================== DISPLAY FUNCTIONS ====================

def show_main_menu(chat_id, first_name=None, reply_to=None):
    if not first_name:
        try: first_name = bot.get_chat(chat_id).first_name
        except: first_name = "VIP User"
    data = load_data()
    watermark = data.get("watermark", "DXA UNIVERSE")
    text = (
        f"━━━━━━━━━━━━━━━\n"
        f"《 👑 NUMBER BOT 》\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👋 WELCOME, <a href='tg://user?id={chat_id}'>{html.escape(first_name)}</a>!\n\n"
        f"📱 GET NUMBER - OTP SERVICE\n"
        f"📊 TRAFFIC - CHECK TRAFFIC\n"
        f"🔐 2FA ONLINE - AUTHENTICATOR\n"
        f"👤 FAKE INFO - BD NAME\n"
        f"🏆 LEADERBOARD - TOP USERS\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🚀 POWERED BY {html.escape(watermark)}"
    )
    msg = safe_send(chat_id, text, get_main_menu(chat_id), reply_to=reply_to)
    if msg: menu_message_id[chat_id] = msg.message_id

def show_user_services(chat_id):
    data = load_data()
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = []
    for srv_id, srv in data.get("services_data", {}).items():
        has_ranges = any(len(cnt.get("ranges", {})) > 0 for cnt in srv.get("countries", {}).values())
        if has_ranges:
            buttons.append(ibtn(text=f"{emo(srv['name'])} {srv['name'].upper()}", callback_data=f"usr_s|{srv_id}", style="primary"))
    if buttons: markup.add(*buttons)
    markup.add(ibtn("🔍 CUSTOM SEARCH", callback_data="find_number", style="success"))
    text = f"━━━━━━━━━━━━━━━\n《 ⭐ SERVICES 》\n━━━━━━━━━━━━━━━\n🔍 CHOOSE YOUR SERVICE BELOW\n━━━━━━━━━━━━━━━\n⚡ FAST • SECURE • RELIABLE"
    safe_edit(chat_id, text, markup)

def show_user_countries(chat_id, srv_id, message_id=None):
    data = load_data()
    srv_data = data.get("services_data", {}).get(srv_id)
    if not srv_data: return
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = []
    for cnt_id, cnt in srv_data.get("countries", {}).items():
        if len(cnt.get("ranges", {})) > 0:
            flag = get_country_flag(cnt['name'])
            buttons.append(ibtn(text=f"{flag} {cnt['name'].upper()}", callback_data=f"usr_c|{srv_id}|{cnt_id}", style="primary"))
    markup.add(*buttons)
    markup.add(ibtn("🔙 BACK", callback_data="back_to_user_services", style="danger"))
    text = f"━━━━━━━━━━━━━━━\n《 🌍 COUNTRY 》\n━━━━━━━━━━━━━━━\n📱 SERVICE: <code>{html.escape(srv_data['name'].upper())}</code>\n\nCHOOSE YOUR COUNTRY"
    safe_edit(chat_id, text, markup, message_id)

def show_user_ranges(chat_id, srv_id, cnt_id, message_id=None):
    data = load_data()
    srv_data = data.get("services_data", {}).get(srv_id)
    cnt_data = srv_data.get("countries", {}).get(cnt_id) if srv_data else None
    if not cnt_data: return
    markup = InlineKeyboardMarkup(row_width=2)
    flag = get_country_flag(cnt_data['name'])
    buttons = [ibtn(text=f"📱 {rng_val}", callback_data=f"usr_r|{srv_id}|{cnt_id}|{rng_id}", style="success") for rng_id, rng_val in cnt_data.get("ranges", {}).items()]
    markup.add(*buttons)
    markup.add(ibtn("🔙 BACK", callback_data=f"usr_s|{srv_id}", style="danger"))
    text = f"━━━━━━━━━━━━━━━\n《 📱 RANGE 》\n━━━━━━━━━━━━━━━\n{emo(srv_data['name'])} SERVICE: <code>{html.escape(srv_data['name'].upper())}</code>\n{flag} COUNTRY: <code>{html.escape(cnt_data['name'].upper())}</code>\n\nCHOOSE YOUR RANGE"
    safe_edit(chat_id, text, markup, message_id)

def show_2fa_menu_display(chat_id):
    text = f"━━━━━━━━━━━━━━━\n《 🔐 2FA AUTHENTICATOR 》\n━━━━━━━━━━━━━━━\n🔐 GENERATE SECURE 2FA CODES\n📱 ENTER YOUR SECRET KEY\n\nCLICK GENERATE 2FA CODE BELOW"
    safe_edit(chat_id, text, get_2fa_menu())

def show_fake_info(chat_id, message_id=None):
    text = f"━━━━━━━━━━━━━━━\n《 👤 FAKE INFO 》\n━━━━━━━━━━━━━━━\nSELECT GENDER TO GENERATE\nBANGLADESHI NAME\n\n🇧🇩 FIRST NAME + LAST NAME"
    safe_edit(chat_id, text, get_fake_info_menu(), message_id)

def show_traffic_info(chat_id):
    data = load_data()
    traffic_link = data.get("traffic_group_link", "https://t.me/+aBpN_vJ4QYYxM2Yy")
    markup = InlineKeyboardMarkup()
    markup.add(ibtn("📊 JOIN TRAFFIC GROUP", url=traffic_link, style="primary"))
    markup.add(ibtn("❌ CLOSE", callback_data="close_menu", style="danger"))
    text = f"━━━━━━━━━━━━━━━\n《 📊 TRAFFIC CHECK 》\n━━━━━━━━━━━━━━━\n🔍 JOIN OUR TRAFFIC GROUP\n📈 GET LIVE OTP UPDATES\n\nCLICK BELOW TO JOIN"
    safe_edit(chat_id, text, markup)

def show_balance(chat_id):
    data = load_data()
    bal = data.get("balances", {}).get(str(chat_id), 0)
    text = f"━━━━━━━━━━━━━━━\n《 💰 MY BALANCE 》\n━━━━━━━━━━━━━━━\n\n💵 CURRENT BALANCE: <b>{bal} ৳</b>\n\n━━━━━━━━━━━━━━━\n🚀 POWERED BY {data.get('watermark', 'DXA UNIVERSE')}"
    markup = InlineKeyboardMarkup().add(ibtn("💸 WITHDRAW", callback_data="req_withdraw", style="success"), ibtn("❌ CLOSE", callback_data="close_menu", style="danger"))
    safe_edit(chat_id, text, markup)

def show_refer(chat_id):
    data = load_data()
    ref_count = data.get("refers", {}).get(str(chat_id), 0)
    reward = data.get("settings", {}).get("refer_reward", 10)
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={chat_id}"
    
    text = f"━━━━━━━━━━━━━━━\n《 🎁 REFER & EARN 》\n━━━━━━━━━━━━━━━\n\n🔗 YOUR LINK:\n<code>{ref_link}</code>\n\n👥 TOTAL REFERS: <b>{ref_count}</b>\n💰 PER REFER: <b>{reward} ৳</b>\n\n━━━━━━━━━━━━━━━"
    markup = InlineKeyboardMarkup().add(ibtn("📋 COPY LINK", copy_text_str=ref_link, style="success"), ibtn("❌ CLOSE", callback_data="close_menu", style="danger"))
    safe_edit(chat_id, text, markup)

def show_withdraw(chat_id):
    data = load_data()
    bal = data.get("balances", {}).get(str(chat_id), 0)
    min_w = data.get("settings", {}).get("min_withdraw", 50)
    methods = data.get("settings", {}).get("withdraw_methods", ["bKash", "Nagad"])
    status = data.get("settings", {}).get("withdraw_status", True)
    
    if not status:
        markup = InlineKeyboardMarkup().add(ibtn("❌ CLOSE", callback_data="close_menu", style="danger"))
        safe_edit(chat_id, f"━━━━━━━━━━━━━━━\n《 💸 WITHDRAWAL 》\n━━━━━━━━━━━━━━━\n\n⚠️ WITHDRAWAL IS CURRENTLY DISABLED BY ADMIN.\n\n━━━━━━━━━━━━━━━", markup)
        return
        
    text = f"━━━━━━━━━━━━━━━\n《 💸 WITHDRAWAL 》\n━━━━━━━━━━━━━━━\n\n💵 BALANCE: <b>{bal} ৳</b>\n📉 MINIMUM: <b>{min_w} ৳</b>\n\nSELECT METHOD:"
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = []
    for m in methods:
        buttons.append(ibtn(m, callback_data=f"withm_{m}", style="primary"))
    markup.add(*buttons)
    markup.add(ibtn("❌ CLOSE", callback_data="close_menu", style="danger"))
    safe_edit(chat_id, text, markup)

def show_support(chat_id, first_name):
    data = load_data()
    sup_link = data.get("settings", {}).get("support_link", "https://t.me/ADMIN_ASIK")
    
    text = (
        f"┏━━━━━━━ 🌙 ━━━━━━━┓\n"
        f"═《 𝗦𝗨𝗣𝗣𝗢𝗥𝗧 》═\n"
        f"━━━━━━━━━━━━━\n"
        f"👋 𝗛𝗘𝗟𝗟𝗢, <a href='tg://user?id={chat_id}'>{html.escape(first_name)}</a>!\n"
        f"💬 𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗧𝗢 𝗦𝗨𝗣𝗣𝗢𝗥𝗧 𝗣𝗔𝗡𝗘𝗟\n"
        f"➤ 𝗧𝗘𝗟𝗟 𝗠𝗘 𝗛𝗢𝗪 𝗖𝗔𝗡 𝗜 𝗛𝗘𝗟𝗣 𝗬𝗢𝗨\n"
        f"➤ 𝗧𝗔𝗣 𝗦𝗨𝗣𝗣𝗢𝗥𝗧 𝗕𝗨𝗧𝗧𝗢𝗡\n"
        f"➤ 𝗧𝗢 𝗖𝗢𝗡𝗧𝗔𝗖𝗧 𝗔𝗗𝗠𝗜𝗡!\n"
        f"┗━━━━━━━ ⚡ ━━━━━━━┛"
    )
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(ibtn("🎧 SUPPORT", url=sup_link, style="primary"), ibtn("🔙 BACK", callback_data="close_menu", style="danger"))
    safe_edit(chat_id, text, markup)

def show_leaderboard(chat_id, message_id=None):
    data = load_data()
    leaderboard = data.get("leaderboard", {})
    text = "━━━━━━━━━━━━━━━\n《 🏆 LEADERBOARD 》\n━━━━━━━━━━━━━━━\n\n"
    if not leaderboard:
        text += "⚠️ NO DATA YET\n\nBE THE FIRST TO GET OTP!"
    else:
        sorted_lb = sorted(leaderboard.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
        stylish_nums = ["➊", "➋", "➌", "➍", "➎", "➏", "➐", "➑", "➒", "➓"]
        for idx, (uid, udata) in enumerate(sorted_lb):
            name = html.escape(udata.get("name", "User"))
            count = udata.get("count", 0)
            mention = f"<a href='tg://user?id={uid}'>{name}</a>"
            text += f"{stylish_nums[idx]}  {mention}  —  {count} OTP\n"
            text += "━━━━━━━━━━━━━━━\n"
    text += "\n🚀 POWERED BY DXA UNIVERSE\n━━━━━━━━━━━━━━━"
    safe_edit(chat_id, text, get_leaderboard_menu(), message_id)

def show_admin_panel(chat_id, message_id=None):
    data = load_data()
    text = (
        f"━━━━━━━━━━━━━━━\n"
        f"《 👑 ADMIN PANEL 》\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📊 DATABASE STATS\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 TOTAL USERS: <code>{len(data.get('users', []))}</code>\n"
        f"📱 TOTAL RANGES: <code>{get_total_ranges()}</code>\n"
        f"💸 WITHDRAWALS: <code>{len(data.get('withdrawals', []))}</code>\n"
        f"🌍 COUNTRIES: <code>240+</code>\n"
        f"━━━━━━━━━━━━━━━"
    )
    safe_edit(chat_id, text, get_admin_menu(chat_id))

def show_admin_system(chat_id, message_id=None):
    data = load_data()
    st = data.get("settings", {})
    markup = InlineKeyboardMarkup(row_width=2)
    status_btn = "🟢 ON" if st.get("withdraw_status", True) else "🔴 OFF"
    
    markup.add(ibtn(f"💸 WITHDRAW: {status_btn}", callback_data="sys_tog_w", style="primary"))
    markup.add(ibtn(f"📉 MIN WITHDRAW: {st.get('min_withdraw', 50)}", callback_data="sys_min_w", style="success"),
               ibtn(f"💰 OTP REWARD: {st.get('otp_reward', 5)}", callback_data="sys_otp_r", style="primary"))
    markup.add(ibtn(f"🎁 REFER REWARD: {st.get('refer_reward', 10)}", callback_data="sys_ref_r", style="success"),
               ibtn(f"⏳ COOLDOWN: {st.get('cooldown', 60)}s", callback_data="sys_cool", style="primary"))
    markup.add(ibtn(f"📱 NUM/REQ: {st.get('num_per_request', 3)}", callback_data="sys_num_req", style="success"),
               ibtn("🛠️ SUPPORT LINK", callback_data="sys_sup", style="primary"))
    markup.add(ibtn("💳 W. METHODS", callback_data="sys_w_meth", style="success"),
               ibtn("🔗 W. GROUP", callback_data="sys_w_grp", style="primary"))
    markup.add(ibtn("🔙 BACK", callback_data="back_to_admin", style="danger"))
    
    safe_edit(chat_id, "━━━━━━━━━━━━━━━\n《 ⚙️ SYSTEM SETTINGS 》\n━━━━━━━━━━━━━━━\nMANAGE BOT ECONOMY & SYSTEM:", markup, message_id)

def show_withdraw_methods(chat_id, message_id=None):
    data = load_data()
    methods = data.get("settings", {}).get("withdraw_methods", ["bKash", "Nagad"])
    markup = InlineKeyboardMarkup(row_width=1)
    for idx, m in enumerate(methods):
        markup.add(ibtn(f"❌ DELETE: {m}", callback_data=f"delwmeth_{idx}", style="danger"))
    markup.add(ibtn("➕ ADD METHOD", callback_data="add_wmeth", style="success"))
    markup.add(ibtn("🔙 BACK", callback_data="admin_system", style="primary"))
    safe_edit(chat_id, f"━━━━━━━━━━━━━━━\n《 💳 W. METHODS 》\n━━━━━━━━━━━━━━━\nTOTAL METHODS: {len(methods)}", markup, message_id)

def process_add_wmeth(message, msg_id):
    if message.text == '/cancel': return show_withdraw_methods(message.chat.id)
    data = load_data()
    data["settings"].setdefault("withdraw_methods", []).append(message.text.strip())
    save_data(data)
    safe_send(message.chat.id, "✅ METHOD ADDED!")
    time.sleep(1); show_withdraw_methods(message.chat.id)

def show_user_view(chat_id, message_id=None):
    data = load_data()
    users = len(data.get("users", []))
    verified = len(data.get("otp_counts", {}).keys())
    banned = len(data.get("banned_users", []))
    
    text = (
        f"━━━━━━━━━━━━━━━\n"
        f"《 👤 USER VIEW 》\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📊 LIVE STATISTICS:\n\n"
        f"👥 TOTAL USERS: <b>{users}</b>\n"
        f"✅ VERIFIED USERS: <b>{verified}</b>\n"
        f"🚫 BANNED USERS: <b>{banned}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🕒 UPDATED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(ibtn("💰 MANAGE BALANCE", callback_data="uv_bal", style="primary"),
               ibtn("🚫 BAN / UNBAN", callback_data="uv_ban", style="danger"))
    markup.add(ibtn("🔙 BACK", callback_data="back_to_admin", style="danger"))
    safe_edit(chat_id, text, markup)

# ==================== CALLBACK HANDLER ====================

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    bot.clear_step_handler_by_chat_id(call.message.chat.id)

    user_id = call.from_user.id
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    data = load_data()

    if call.data == "ignore": return

    # Fake Info
    if call.data == "fake_male":
        first, last = generate_bd_name("MALE")
        text = f"━━━━━━━━━━━━━━━\n《 👤 FAKE INFO 》\n━━━━━━━━━━━━━━━\n👨 GENDER: MALE\n━━━━━━━━━━━━━━━\n🇧🇩 FIRST NAME: {html.escape(first)}\n🇧🇩 LAST NAME: {html.escape(last)}\n━━━━━━━━━━━━━━━\n🚀 POWERED BY DXA UNIVERSE"
        safe_edit(chat_id, text, get_fake_info_menu(), msg_id)
        return
    elif call.data == "fake_female":
        first, last = generate_bd_name("FEMALE")
        text = f"━━━━━━━━━━━━━━━\n《 👤 FAKE INFO 》\n━━━━━━━━━━━━━━━\n👩 GENDER: FEMALE\n━━━━━━━━━━━━━━━\n🇧🇩 FIRST NAME: {html.escape(first)}\n🇧🇩 LAST NAME: {html.escape(last)}\n━━━━━━━━━━━━━━━\n🚀 POWERED BY DXA UNIVERSE"
        safe_edit(chat_id, text, get_fake_info_menu(), msg_id)
        return
    elif call.data == "fake_back": show_main_menu(chat_id); return
    elif call.data == "refresh_leaderboard": show_leaderboard(chat_id, msg_id); return

    # 2FA
    if call.data == "2fa_back": show_main_menu(chat_id); return
    elif call.data == "2fa_refresh":
        key = user_states.get(chat_id, {}).get('2fa_key')
        if key: process_2fa_refresh_logic(chat_id, key)
        else: bot.answer_callback_query(call.id, "❌ NO KEY FOUND!", show_alert=True)
        return
    elif call.data == "2fa_generate":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="2fa_back", style="danger"))
        text = f"━━━━━━━━━━━━━━━\n《 🔑 ENTER 2FA KEY 》\n━━━━━━━━━━━━━━━\n📝 SEND YOUR 2FA SECRET KEY\n\nEXAMPLE: <code>JBSWY3DPEHPK3PXP</code>\n\nSEND /cancel TO STOP"
        safe_edit(chat_id, text, markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_2fa_code)
        return
    elif call.data == "2fa_new_key":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="2fa_back", style="danger"))
        text = f"━━━━━━━━━━━━━━━\n《 🔑 ENTER NEW 2FA KEY 》\n━━━━━━━━━━━━━━━\n📝 SEND YOUR NEW SECRET KEY\n\nEXAMPLE: <code>JBSWY3DPEHPK3PXP</code>\n\nSEND /cancel TO STOP"
        safe_edit_2fa(chat_id, text, markup)
        bot.register_next_step_handler_by_chat_id(chat_id, process_2fa_code)
        return

    if call.data == "check_join":
        if check_force_join(user_id):
            bot.answer_callback_query(call.id, "✅ Welcome to DXA UNIVERSE!", show_alert=True)
            show_main_menu(chat_id)
        else:
            bot.answer_callback_query(call.id, "❌ Please join the channel first!", show_alert=True)
        return

    if call.data == "close_menu":
        try: bot.delete_message(chat_id, msg_id)
        except: pass
        show_main_menu(chat_id)
        return

    # User Withdraw Callbacks
    if call.data == "req_withdraw": show_withdraw(chat_id, msg_id); return
    elif call.data.startswith("withm_"):
        method = call.data.split("_")[1]
        markup = InlineKeyboardMarkup().add(ibtn("🔙 BACK", callback_data="req_withdraw", style="danger"))
        safe_edit(chat_id, f"━━━━━━━━━━━━━━━\n《 💸 WITHDRAWAL 》\n━━━━━━━━━━━━━━━\n🏦 METHOD: {method}\n\n💰 ENTER AMOUNT TO WITHDRAW:\n\nSEND /cancel TO CANCEL", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_withdraw_amount, method)
        return


    # Admin check
    admin_restricted_cbs = ["adm_", "add_", "del_", "editgrp_", "admin_broadcast", "admin_group_settings", "admin_set_watermark", "admin_force_join", "admin_traffic_group", "edit_traffic_link", "del_traffic_link", "toggle_force_join", "add_fjc", "back_to_admin", "admin_manage_service", "admin_system", "admin_user_view"]
    if any(call.data.startswith(x) for x in ["adm_", "add_", "del_", "editgrp_"]) or call.data in admin_restricted_cbs:
        if user_id != ADMIN_ID and user_id not in data.get("extra_admins", []):
            return bot.answer_callback_query(call.id, "⚠️ ACCESS DENIED", show_alert=True)

    # Navigation
    if call.data == "back_to_admin": show_admin_panel(chat_id, msg_id)
    elif call.data == "admin_system": show_admin_system(chat_id, msg_id)
    elif call.data == "admin_user_view": show_user_view(chat_id, msg_id)
    elif call.data == "uv_bal":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="admin_user_view", style="danger"))
        safe_edit(chat_id, f"━━━━━━━━━━━━━━━\n《 💰 MANAGE BALANCE 》\n━━━━━━━━━━━━━━━\nFORMAT: <code>USER_ID AMOUNT</code>\n\nTO ADD: <code>12345 50</code>\nTO CUT: <code>12345 -50</code>", markup)
        bot.register_next_step_handler_by_chat_id(chat_id, process_manage_balance, msg_id)
    elif call.data == "uv_ban":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="admin_user_view", style="danger"))
        safe_edit(chat_id, f"━━━━━━━━━━━━━━━\n《 🚫 BAN / UNBAN 》\n━━━━━━━━━━━━━━━\nSEND USER ID TO BAN/UNBAN:", markup)
        bot.register_next_step_handler_by_chat_id(chat_id, process_ban_user, msg_id)
    elif call.data.startswith("w_app_") or call.data.startswith("w_rej_"):
        action = call.data[:5]
        req_id = call.data[6:]
        process_withdraw_action(chat_id, action, req_id, msg_id)
    elif call.data == "admin_api_manage":
        show_api_manage(chat_id, msg_id)
    elif call.data == "add_new_api":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="admin_api_manage", style="danger"))
        safe_edit(chat_id, f"━━━━━━━━━━━━━━━\n《 ➕ ADD API KEY 》\n━━━━━━━━━━━━━━━\nSEND NEW API KEY:", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_add_api, msg_id)
    elif call.data.startswith("delapi_"):
        idx = int(call.data.split("_")[1])
        if 0 <= idx < len(data.get("api_keys", [])):
            data["api_keys"].pop(idx); save_data(data)
        show_api_manage(chat_id, msg_id)
    elif call.data == "admin_manage_admins":
        show_manage_admins(chat_id, msg_id)
    elif call.data == "add_new_admin":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="admin_manage_admins", style="danger"))
        safe_edit(chat_id, f"━━━━━━━━━━━━━━━\n《 👮 ADD ADMIN 》\n━━━━━━━━━━━━━━━\nSEND USER ID:", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_add_admin, msg_id)
    elif call.data.startswith("deladm_"):
        adm_id = int(call.data.split("_")[1])
        if adm_id in data.get("extra_admins", []):
            data["extra_admins"].remove(adm_id); save_data(data)
        show_manage_admins(chat_id, msg_id)
    elif call.data == "sys_tog_w":
        data["settings"]["withdraw_status"] = not data["settings"].get("withdraw_status", True); save_data(data)
        show_admin_system(chat_id, msg_id)
    elif call.data == "sys_w_meth":
        show_withdraw_methods(chat_id, msg_id)
    elif call.data == "add_wmeth":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="sys_w_meth", style="danger"))
        safe_edit(chat_id, f"━━━━━━━━━━━━━━━\n《 ➕ ADD METHOD 》\n━━━━━━━━━━━━━━━\nSEND NEW METHOD NAME:", markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_add_wmeth, msg_id)
    elif call.data.startswith("delwmeth_"):
        idx = int(call.data.split("_")[1])
        methods = data.get("settings", {}).get("withdraw_methods", [])
        if 0 <= idx < len(methods):
            methods.pop(idx); save_data(data)
        show_withdraw_methods(chat_id, msg_id)
    elif call.data in ["sys_min_w", "sys_otp_r", "sys_ref_r", "sys_cool", "sys_num_req", "sys_sup", "sys_w_grp"]:
        action_map = {
            "sys_min_w": ("MIN WITHDRAW", "amount"), "sys_otp_r": ("OTP REWARD", "amount"),
            "sys_ref_r": ("REFER REWARD", "amount"), "sys_cool": ("COOLDOWN (Seconds)", "seconds"),
            "sys_num_req": ("NUMBER PER REQUEST", "count"), "sys_sup": ("SUPPORT LINK", "link"),
            "sys_w_grp": ("WITHDRAW GROUP ID", "group ID")
        }
        title, hint = action_map[call.data]
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="admin_system", style="danger"))
        safe_edit(chat_id, f"━━━━━━━━━━━━━━━\n《 ⚙️ {title} 》\n━━━━━━━━━━━━━━━\nSEND NEW {hint.upper()}:", markup)
        bot.register_next_step_handler_by_chat_id(chat_id, process_system_setting, call.data, msg_id)
    elif call.data == "back_to_user_services":
        if str(chat_id) in active_polls: active_polls[str(chat_id)] = False
        show_user_services(chat_id)
    elif call.data.startswith("usr_s|"): show_user_countries(chat_id, call.data.split("|")[1], msg_id)
    elif call.data.startswith("usr_c|"):
        _, srv_id, cnt_id = call.data.split("|")
        show_user_ranges(chat_id, srv_id, cnt_id, msg_id)
    elif call.data == "find_number":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_user_services", style="danger"))
        text = f"━━━━━━━━━━━━━━━\n《 📝 CUSTOM RANGE 》\n━━━━━━━━━━━━━━━\nEXAMPLE: 99298XXX or 8801\n\nSEND /cancel TO STOP"
        safe_edit(chat_id, text, markup, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_custom_range, msg_id)
    elif call.data.startswith("chgc|") or call.data.startswith("usr_r|") or call.data.startswith("chg_r|"):
        is_custom = call.data.startswith("chgc|")
        if is_custom:
            custom_input = call.data.split("|")[1]
            service_info = {'id': f"custom_{custom_input}", 'service_name': "Custom Search", 'country_name': 'Universal', 'range': custom_input, 'srv_id': None, 'cnt_id': None}
        else:
            _, srv_id, cnt_id, rng_id = call.data.split("|")
            srv_data = data.get("services_data", {}).get(srv_id)
            cnt_data = srv_data.get("countries", {}).get(cnt_id) if srv_data else None
            rng_val = cnt_data.get("ranges", {}).get(rng_id) if cnt_data else None
            if not rng_val: return
            service_info = {'id': rng_id, 'srv_id': srv_id, 'cnt_id': cnt_id, 'service_name': srv_data['name'], 'country_name': cnt_data['name'], 'range': rng_val}
        if str(chat_id) in active_polls: active_polls[str(chat_id)] = False
        fetch_numbers(chat_id, service_info, msg_id, is_custom)

    # Admin Services
    elif call.data == "admin_manage_service": show_admin_services(chat_id, msg_id)
    elif call.data == "add_srv":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="admin_manage_service", style="danger"))
        safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 📩 NEW SERVICE 》\n━━━━━━━━━━━━━━━\nSEND SERVICE NAME:", markup)
        bot.register_next_step_handler_by_chat_id(chat_id, process_add_srv, msg_id)
    elif call.data.startswith("adm_s|"): show_admin_countries(chat_id, call.data.split("|")[1], msg_id)
    elif call.data.startswith("add_cnt|"):
        srv_id = call.data.split("|")[1]
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data=f"adm_s|{srv_id}", style="danger"))
        safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 🌍 NEW COUNTRY 》\n━━━━━━━━━━━━━━━\nSEND COUNTRY NAME:", markup)
        bot.register_next_step_handler_by_chat_id(chat_id, process_add_cnt, srv_id, msg_id)
    elif call.data.startswith("adm_c|"):
        _, srv_id, cnt_id = call.data.split("|")
        show_admin_ranges(chat_id, srv_id, cnt_id, msg_id)
    elif call.data.startswith("add_rng|"):
        _, srv_id, cnt_id = call.data.split("|")
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data=f"adm_c|{srv_id}|{cnt_id}", style="danger"))
        safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 📱 NEW RANGE 》\n━━━━━━━━━━━━━━━\nSEND RANGE:", markup)
        bot.register_next_step_handler_by_chat_id(chat_id, process_add_rng, srv_id, cnt_id, msg_id)
    elif call.data.startswith("del_srv|"):
        srv_id = call.data.split("|")[1]
        if srv_id in data.get("services_data", {}): del data["services_data"][srv_id]; save_data(data)
        show_admin_services(chat_id, msg_id)
    elif call.data.startswith("del_cnt|"):
        _, srv_id, cnt_id = call.data.split("|")
        if srv_id in data["services_data"] and cnt_id in data["services_data"][srv_id]["countries"]:
            del data["services_data"][srv_id]["countries"][cnt_id]; save_data(data)
        show_admin_countries(chat_id, srv_id, msg_id)
    elif call.data.startswith("del_rng|"):
        _, srv_id, cnt_id, rng_id = call.data.split("|")
        if srv_id in data["services_data"] and cnt_id in data["services_data"][srv_id]["countries"] and rng_id in data["services_data"][srv_id]["countries"][cnt_id]["ranges"]:
            del data["services_data"][srv_id]["countries"][cnt_id]["ranges"][rng_id]; save_data(data)
        show_admin_ranges(chat_id, srv_id, cnt_id, msg_id)

    # Admin Groups
    elif call.data == "admin_group_settings": safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 🔗 GROUP SETTINGS 》", get_group_settings_menu())
    elif call.data == "admin_traffic_group":
        current_link, markup = get_traffic_group_menu()
        safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 📊 TRAFFIC GROUP 》\n━━━━━━━━━━━━━━━\n🔗 CURRENT LINK:\n<code>{current_link}</code>", markup)
    elif call.data == "edit_traffic_link":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="admin_traffic_group", style="danger"))
        safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 🔗 SET TRAFFIC LINK 》\n━━━━━━━━━━━━━━━\nSEND NEW LINK:", markup)
        bot.register_next_step_handler_by_chat_id(chat_id, process_traffic_link, msg_id)
    elif call.data == "del_traffic_link":
        data["traffic_group_link"] = ""; save_data(data)
        safe_send(chat_id, f"✅ LINK REMOVED!"); show_admin_panel(chat_id)
    elif call.data == "set_main_otp_link":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="admin_group_settings", style="danger"))
        safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 🔗 SET OTP LINK 》\n━━━━━━━━━━━━━━━\nSEND OTP GROUP URL:", markup)
        bot.register_next_step_handler_by_chat_id(chat_id, process_main_otp_link, msg_id)
    elif call.data == "del_main_otp_link":
        data["main_otp_link"] = "https://t.me/"; save_data(data)
        safe_send(chat_id, f"✅ LINK REMOVED!")
        time.sleep(1)
        safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 🔗 GROUP SETTINGS 》", get_group_settings_menu())
    elif call.data == "add_fwd_group":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="admin_group_settings", style="danger"))
        safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 ➕ ADD GROUP 》\n━━━━━━━━━━━━━━━\nSEND GROUP CHAT ID:", markup)
        bot.register_next_step_handler_by_chat_id(chat_id, step1_add_fwd_group, msg_id)
    elif call.data.startswith("editgrp_"): show_edit_group_menu(chat_id, call.data.split("_")[1], msg_id)
    elif call.data.startswith("addgrpbtn_"):
        grp_id = call.data.split("_")[1]
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data=f"editgrp_{grp_id}", style="danger"))
        safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 📝 BUTTON NAME 》\n━━━━━━━━━━━━━━━\nSEND NAME:", markup)
        bot.register_next_step_handler_by_chat_id(chat_id, step_addgrpbtn_name, grp_id, msg_id)
    elif call.data.startswith("delgrpbtn_"):
        parts = call.data.split("_"); grp_id, btn_idx = parts[1], int(parts[2])
        for g in data.get("forward_groups", []):
            if str(g['chat_id']) == str(grp_id):
                if 0 <= btn_idx < len(g.get("buttons", [])): g["buttons"].pop(btn_idx)
                break
        save_data(data); show_edit_group_menu(chat_id, grp_id, msg_id)
    elif call.data.startswith("delfwd_"):
        grp_id = call.data.split("_")[1]
        data["forward_groups"] = [g for g in data.get("forward_groups", []) if str(g['chat_id']) != grp_id]
        save_data(data)
        safe_send(chat_id, f"✅ GROUP DELETED!")
        time.sleep(1)
        safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 🔗 GROUP SETTINGS 》", get_group_settings_menu())

    # Force Join
    elif call.data == "admin_force_join": safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 📣 FORCE JOIN 》", get_force_join_menu())
    elif call.data == "toggle_force_join":
        data["force_join_enabled"] = not data.get("force_join_enabled", False); save_data(data)
        safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 📣 FORCE JOIN 》", get_force_join_menu())
    elif call.data == "add_fjc":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="admin_force_join", style="danger"))
        safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 🔗 NEW CHANNEL 》\n━━━━━━━━━━━━━━━\nSEND LINK:", markup)
        bot.register_next_step_handler_by_chat_id(chat_id, process_set_force_join_link, msg_id)
    elif call.data.startswith("delfjc_"):
        idx = int(call.data.split("_")[1])
        if 0 <= idx < len(data.get("force_join_channels", [])):
            data["force_join_channels"].pop(idx); save_data(data)
        safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 📣 FORCE JOIN 》", get_force_join_menu())

    # Watermark & Broadcast
    elif call.data == "admin_set_watermark":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 💎 WATERMARK 》\n━━━━━━━━━━━━━━━\nCURRENT: {data.get('watermark', 'DXA UNIVERSE')}\n\nSEND NEW:", markup)
        bot.register_next_step_handler_by_chat_id(chat_id, process_set_watermark, msg_id)
    elif call.data == "admin_broadcast":
        markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data="back_to_admin", style="danger"))
        safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 📢 BROADCAST 》\n━━━━━━━━━━━━━━━\nSEND MESSAGE:", markup)
        bot.register_next_step_handler_by_chat_id(chat_id, process_broadcast, msg_id)

# ==================== PROCESSING FUNCTIONS ====================

def process_2fa_code(message):
    if message.text == '/cancel': show_2fa_menu_display(message.chat.id); return
    
    # নতুন 2FA ক্লিনার লজিক: স্পেস, হাইফেন বা অন্য টেক্সট থাকলে অটোমেটিক ফিল্টার করে শুধু অরিজিনাল কি রাখবে
    raw_key = message.text.upper()
    secret_key = re.sub(r'[^A-Z2-7=]', '', raw_key)
    
    if len(secret_key) < 8:
        safe_send(message.chat.id, "━━━━━━━━━━━━━━━\n《 ❌ INVALID KEY 》\n━━━━━━━━━━━━━━━\nPlease send a valid 2FA secret key!\n\nExample: JBSWY3DPEHPK3PXP")
        return
    if message.chat.id not in user_states: user_states[message.chat.id] = {}
    user_states[message.chat.id]['2fa_key'] = secret_key
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass
    process_2fa_refresh_logic(message.chat.id, secret_key)

def process_2fa_refresh_logic(chat_id, secret_key):
    try:
        # Base32 Padding Fix
        padding = len(secret_key) % 8
        if padding != 0:
            secret_key += '=' * (8 - padding)

        totp = pyotp.TOTP(secret_key)
        code = totp.now()
        remaining = 30 - (int(time.time()) % 30)
        text = (
            f"━━━━━━━━━━━━━━━\n"
            f"《 🔐 2FA CODE 》\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🔐 CODE: <code>{code}</code>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⏰ EXPIRES IN: <b>{remaining}s</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🚀 POWERED BY SN BOT CREATOR"
        )
        markup = InlineKeyboardMarkup(row_width=1)
        
        markup.add(ibtn(f"📋 COPY: {code}", copy_text_str=code, style="success"))
        
        markup.add(ibtn("🔄 REFRESH CODE", callback_data="2fa_refresh", style="primary"),
                   ibtn("🆕 NEW CODE", callback_data="2fa_generate", style="success"),
                   ibtn("🔙 BACK", callback_data="2fa_back", style="danger"))
        safe_edit(chat_id, text, markup)
    except Exception as e:
        print(f"2FA Generation Error: {e}")
        safe_edit(chat_id, "━━━━━━━━━━━━━━━\n《 ❌ ERROR 》\n━━━━━━━━━━━━━━━\nINVALID 2FA KEY!")

def process_custom_range(message, msg_id):
    if message.text == '/cancel': show_user_services(message.chat.id); return
    custom_input = message.text.strip()
    if len(custom_input) < 3 or not re.match(r'^[0-9X]+$', custom_input, re.IGNORECASE):
        safe_send(message.chat.id, "━━━━━━━━━━━━━━━\n《 ❌ INVALID RANGE 》\n━━━━━━━━━━━━━━━\nPlease enter valid digits or X\n\nExample: 8801 or 99298XXX")
        return
    service_info = {'id': f"custom_{custom_input}", 'service_name': "Custom Search", 'country_name': 'Universal', 'range': custom_input, 'srv_id': None, 'cnt_id': None}
    if str(message.chat.id) in active_polls: active_polls[str(message.chat.id)] = False
    fetch_numbers(message.chat.id, service_info, msg_id, is_custom=True)

def process_traffic_link(message, msg_id):
    if message.text == '/cancel': show_admin_panel(message.chat.id); return
    data = load_data()
    data["traffic_group_link"] = format_url(message.text.strip()); save_data(data)
    safe_send(message.chat.id, f"✅ LINK UPDATED!")
    time.sleep(1); show_admin_panel(message.chat.id)

def process_set_force_join_link(message, msg_id):
    if message.text == '/cancel':
        safe_send(message.chat.id, f"━━━━━━━━━━━━━━━\n《 📣 FORCE JOIN 》", get_force_join_menu()); return
    data = load_data()
    data.setdefault("force_join_channels", []).append(format_url(message.text.strip())); save_data(data)
    safe_send(message.chat.id, f"✅ CHANNEL ADDED!")
    time.sleep(1); safe_send(message.chat.id, f"━━━━━━━━━━━━━━━\n《 📣 FORCE JOIN 》", get_force_join_menu())

def process_add_srv(message, msg_id):
    if message.text == '/cancel': return show_admin_services(message.chat.id, msg_id)
    data = load_data()
    srv_id = "s_" + str(uuid.uuid4())[:8]
    data.setdefault("services_data", {})[srv_id] = {"name": message.text.strip(), "countries": {}}; save_data(data)
    show_admin_services(message.chat.id, msg_id)

def process_add_cnt(message, srv_id, msg_id):
    if message.text == '/cancel': return show_admin_countries(message.chat.id, srv_id, msg_id)
    data = load_data()
    cnt_id = "c_" + str(uuid.uuid4())[:8]
    if srv_id in data.get("services_data", {}):
        data["services_data"][srv_id]["countries"][cnt_id] = {"name": message.text.strip(), "ranges": {}}; save_data(data)
    show_admin_countries(message.chat.id, srv_id, msg_id)

def process_add_rng(message, srv_id, cnt_id, msg_id):
    if message.text == '/cancel': return show_admin_ranges(message.chat.id, srv_id, cnt_id, msg_id)
    data = load_data()
    rng_id = "r_" + str(uuid.uuid4())[:8]
    try:
        data["services_data"][srv_id]["countries"][cnt_id]["ranges"][rng_id] = message.text.strip(); save_data(data)
    except: pass
    show_admin_ranges(message.chat.id, srv_id, cnt_id, msg_id)

def step1_add_fwd_group(message, msg_id):
    if message.text == '/cancel':
        safe_send(message.chat.id, f"━━━━━━━━━━━━━━━\n《 🔗 GROUP SETTINGS 》", get_group_settings_menu()); return
    data = load_data()
    data.setdefault("forward_groups", []).append({"chat_id": message.text.strip(), "buttons": []}); save_data(data)
    safe_send(message.chat.id, f"✅ GROUP ADDED!")
    time.sleep(1); safe_send(message.chat.id, f"━━━━━━━━━━━━━━━\n《 🔗 GROUP SETTINGS 》", get_group_settings_menu())

def step_addgrpbtn_name(message, grp_id, msg_id):
    if message.text == '/cancel': show_edit_group_menu(message.chat.id, grp_id, msg_id); return
    user_states[message.chat.id] = {'grp_id': grp_id, 'btn_name': message.text.strip()}
    markup = InlineKeyboardMarkup().add(ibtn("🔙 CANCEL", callback_data=f"editgrp_{grp_id}", style="danger"))
    safe_send(message.chat.id, f"━━━━━━━━━━━━━━━\n《 🔗 BUTTON URL 》\n━━━━━━━━━━━━━━━\nSEND URL:", markup)
    bot.register_next_step_handler_by_chat_id(message.chat.id, step_addgrpbtn_url, msg_id)

def step_addgrpbtn_url(message, msg_id):
    if message.text == '/cancel':
        grp_id = user_states.get(message.chat.id, {}).get('grp_id')
        if grp_id: show_edit_group_menu(message.chat.id, grp_id, msg_id); return
    state = user_states.get(message.chat.id, {})
    grp_id = state.get('grp_id'); btn_name = state.get('btn_name')
    btn_url = format_url(message.text.strip())
    data = load_data()
    for grp in data.get("forward_groups", []):
        if str(grp['chat_id']) == str(grp_id):
            grp.setdefault("buttons", []).append({"name": btn_name, "url": btn_url}); break
    save_data(data)
    safe_send(message.chat.id, f"✅ BUTTON ADDED!")
    time.sleep(1); show_edit_group_menu(message.chat.id, grp_id, msg_id)

def process_main_otp_link(message, msg_id):
    if message.text == '/cancel':
        safe_send(message.chat.id, f"━━━━━━━━━━━━━━━\n《 🔗 GROUP SETTINGS 》", get_group_settings_menu()); return
    data = load_data()
    data["main_otp_link"] = format_url(message.text.strip()); save_data(data)
    safe_send(message.chat.id, f"✅ LINK UPDATED!")
    time.sleep(1); safe_send(message.chat.id, f"━━━━━━━━━━━━━━━\n《 🔗 GROUP SETTINGS 》", get_group_settings_menu())

def process_set_watermark(message, msg_id):
    if message.text == '/cancel': return show_admin_panel(message.chat.id, msg_id)
    data = load_data()
    data["watermark"] = message.text.strip(); save_data(data)
    safe_send(message.chat.id, f"✅ WATERMARK UPDATED!")
    time.sleep(1); show_admin_panel(message.chat.id, msg_id)

def run_broadcast(chat_id, original_message, msg_id):
    data = load_data()
    users = data.get("users", [])
    success, failed = 0, 0
    for u in users:
        try:
            bot.copy_message(chat_id=u, from_chat_id=chat_id, message_id=original_message.message_id)
            success += 1; time.sleep(0.05)
        except: failed += 1
    markup = InlineKeyboardMarkup().add(ibtn("🔙 BACK", callback_data="back_to_admin", style="danger"))
    safe_send(chat_id, f"━━━━━━━━━━━━━━━\n《 📢 BROADCAST DONE 》\n━━━━━━━━━━━━━━━\n✅ SENT: {success}\n❌ FAILED: {failed}", markup)

def process_broadcast(message, msg_id):
    if message.text == '/cancel': return show_admin_panel(message.chat.id, msg_id)
    safe_send(message.chat.id, f"━━━━━━━━━━━━━━━\n《 🔄 BROADCASTING... 》")
    threading.Thread(target=run_broadcast, args=(message.chat.id, message, msg_id)).start()

def process_system_setting(message, action, msg_id):
    if message.text == '/cancel': return show_admin_system(message.chat.id)
    data = load_data()
    val = message.text.strip()
    
    try:
        if action == "sys_min_w": data["settings"]["min_withdraw"] = float(val)
        elif action == "sys_otp_r": data["settings"]["otp_reward"] = float(val)
        elif action == "sys_ref_r": data["settings"]["refer_reward"] = float(val)
        elif action == "sys_cool": data["settings"]["cooldown"] = int(val)
        elif action == "sys_num_req": data["settings"]["num_per_request"] = int(val)
        elif action == "sys_sup": data["settings"]["support_link"] = format_url(val)
        elif action == "sys_w_grp": data["settings"]["withdraw_group"] = val
        elif action == "sys_w_meth": data["settings"]["withdraw_methods"] = [m.strip() for m in val.split(",")]
    except ValueError:
        safe_send(message.chat.id, "❌ INVALID FORMAT! MUST BE A NUMBER.")
        return time.sleep(1) or show_admin_system(message.chat.id)
        
    save_data(data)
    safe_send(message.chat.id, "✅ SETTING UPDATED SUCCESSFULLY!")
    time.sleep(1)
    show_admin_system(message.chat.id)

def process_withdraw_amount(message, method):
    # ইউজারের পাঠানো টেক্সট মেসেজটি ডিলিট করে দেওয়া
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass

    if message.text == '/cancel': return show_withdraw(message.chat.id)
    data = load_data()
    uid = str(message.chat.id)
    bal = data.get("balances", {}).get(uid, 0)
    min_w = data.get("settings", {}).get("min_withdraw", 50)
    
    try:
        req_amount = float(message.text.strip())
        if req_amount < min_w:
            safe_send(message.chat.id, f"❌ MINIMUM WITHDRAW: {min_w} ৳")
            return show_withdraw(message.chat.id)
        if req_amount > bal:
            safe_send(message.chat.id, f"❌ INSUFFICIENT BALANCE! MAX: {bal} ৳")
            return show_withdraw(message.chat.id)
    except ValueError:
        safe_send(message.chat.id, "❌ INVALID AMOUNT FORMAT!")
        return show_withdraw(message.chat.id)
        
    user_states[message.chat.id] = {'w_amount': req_amount, 'w_method': method}
    markup = InlineKeyboardMarkup().add(ibtn("🔙 BACK", callback_data="req_withdraw", style="danger"))
    
    # safe_send এর জায়গায় safe_edit ব্যবহার করা হলো
    safe_edit(message.chat.id, f"━━━━━━━━━━━━━━━\n《 💸 WITHDRAWAL 》\n━━━━━━━━━━━━━━━\n🏦 METHOD: {method}\n💰 AMOUNT: {req_amount} ৳\n\n📱 SEND YOUR ACCOUNT NUMBER:\n\nSEND /cancel TO CANCEL", markup)
    bot.register_next_step_handler_by_chat_id(message.chat.id, process_withdraw_number)

def process_withdraw_number(message):
    # ইউজারের পাঠানো নাম্বারটি ডিলিট করে দেওয়া
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass

    if message.text == '/cancel': return show_withdraw(message.chat.id)
    
    uid = str(message.chat.id)
    state = user_states.get(message.chat.id, {})
    req_amount = state.get('w_amount')
    method = state.get('w_method')
    
    if not req_amount or not method:
        return show_withdraw(message.chat.id)
        
    acc_num = message.text.strip()
    data = load_data()
    bal = data.get("balances", {}).get(uid, 0)
    w_group = data.get("settings", {}).get("withdraw_group", "")
    
    if req_amount > bal:
         safe_send(message.chat.id, "❌ INSUFFICIENT BALANCE!")
         return show_withdraw(message.chat.id)
         
    req_id = f"W_{uuid.uuid4().hex[:6].upper()}"
    
    data["balances"][uid] = bal - req_amount
    data["withdrawals"].append({"req_id": req_id, "uid": uid, "method": method, "amount": req_amount, "account": acc_num, "status": "PENDING"})
    save_data(data)
    
    user_states.pop(message.chat.id, None)
    
    markup = InlineKeyboardMarkup().add(ibtn("❌ CLOSE", callback_data="close_menu", style="danger"))
    
    # safe_send এর জায়গায় safe_edit ব্যবহার করা হলো
    safe_edit(message.chat.id, f"━━━━━━━━━━━━━━━\n《 ✅ REQUEST SENT 》\n━━━━━━━━━━━━━━━\n💳 METHOD: {method}\n💰 AMOUNT: {req_amount} ৳\n📱 ACCOUNT: <code>{acc_num}</code>\n\nPLEASE WAIT FOR ADMIN APPROVAL.", markup)
    
    if w_group:
        first_name = html.escape(message.from_user.first_name or "User")
        w_text = (
            f"🔔 𝗡𝗘𝗪 𝗪𝗜𝗧𝗛𝗗𝗥𝗔𝗪𝗔𝗟 𝗥𝗘𝗤𝗨𝗘𝗦𝗧\n\n"
            f"👤 𝗨𝗦𝗘𝗥: <a href='tg://user?id={uid}'>{first_name}</a>\n\n"
            f"💸 𝗪𝗜𝗧𝗛𝗗𝗥𝗔𝗪𝗔𝗟: {req_amount} 𝗧𝗞\n\n"
            f"📱 𝗡𝗨𝗠𝗕𝗘𝗥: <code>{acc_num}</code>\n\n"
            f"🏦 𝗠𝗘𝗧𝗛𝗢𝗗: {method}\n\n"
            f"🔖 REQ ID: <code>{req_id}</code>"
        )
        w_markup = InlineKeyboardMarkup(row_width=2)
        w_markup.add(ibtn("✅ APPROVE", callback_data=f"w_app_{req_id}", style="success"),
                     ibtn("❌ REJECT", callback_data=f"w_rej_{req_id}", style="danger"))
        try: safe_send(w_group, w_text, w_markup)
        except: pass

def process_manage_balance(message, msg_id):
    if message.text == '/cancel': return show_user_view(message.chat.id)
    try:
        uid, amt = message.text.strip().split()
        amt = float(amt)
        data = load_data()
        data["balances"][uid] = data.get("balances", {}).get(uid, 0) + amt
        save_data(data)
        safe_send(message.chat.id, f"✅ SUCCESS! BALANCE UPDATED.")
    except:
        safe_send(message.chat.id, "❌ INVALID FORMAT!")
    time.sleep(1); show_user_view(message.chat.id)

def process_ban_user(message, msg_id):
    if message.text == '/cancel': return show_user_view(message.chat.id)
    try:
        uid = int(message.text.strip())
        data = load_data()
        if uid in data.get("banned_users", []):
            data["banned_users"].remove(uid)
            msg = "✅ UNBANNED!"
        else:
            data.setdefault("banned_users", []).append(uid)
            msg = "🚫 BANNED!"
        save_data(data)
        safe_send(message.chat.id, msg)
    except:
        safe_send(message.chat.id, "❌ INVALID ID!")
    time.sleep(1); show_user_view(message.chat.id)

def process_withdraw_action(chat_id, action, req_id, msg_id):
    data = load_data()
    withdrawals = data.get("withdrawals", [])
    req = next((r for r in withdrawals if r["req_id"] == req_id), None)
    
    if not req or req["status"] != "PENDING":
        safe_edit(chat_id, "❌ ALREADY PROCESSED OR NOT FOUND!", message_id=msg_id)
        return
        
    req["status"] = "APPROVED" if action == "w_app" else "REJECTED"
    
    if action == "w_rej":
        data["balances"][req["uid"]] = data.get("balances", {}).get(req["uid"], 0) + req["amount"]
    
    save_data(data)
    
    status_msg = "✅ APPROVED" if action == "w_app" else "❌ REJECTED"
    status_style = "success" if action == "w_app" else "danger"
    
    w_text = (
        f"🔔 𝗪𝗜𝗧𝗛𝗗𝗥𝗔𝗪𝗔𝗟 {status_msg}\n\n"
        f"👤 𝗨𝗦𝗘𝗥: <a href='tg://user?id={req['uid']}'>Profile</a>\n\n"
        f"💸 𝗪𝗜𝗧𝗛𝗗𝗥𝗔𝗪𝗔𝗟: {req['amount']} 𝗧𝗞\n\n"
        f"📱 𝗡𝗨𝗠𝗕𝗘𝗥: <code>{req['account']}</code>\n\n"
        f"🏦 𝗠𝗘𝗧𝗛𝗢𝗗: {req['method']}\n\n"
        f"🔖 REQ ID: <code>{req_id}</code>\n"
        f"👨‍⚖️ PROCESSED BY ADMIN"
    )
    markup = InlineKeyboardMarkup()
    markup.add(ibtn(status_msg, callback_data="ignore", style=status_style))
    safe_edit(chat_id, w_text, reply_markup=markup, message_id=msg_id)
    
    user_note = f"✅ YOUR WITHDRAWAL OF {req['amount']} ৳ HAS BEEN APPROVED!" if action == "w_app" else f"❌ YOUR WITHDRAWAL WAS REJECTED. BALANCE RETURNED."
    safe_send(req["uid"], f"━━━━━━━━━━━━━━━\n《 💸 WITHDRAWAL NOTICE 》\n━━━━━━━━━━━━━━━\n\n{user_note}")

def show_api_manage(chat_id, message_id=None):
    data = load_data()
    if not data.get("api_keys"):
        data["api_keys"] = [NEXA_API_KEY, "nxa_7367a7ca4fb9e3ec44c574f668714df61a813162", "nxa_9ad17cea99f85040fde8eb4fabdbff6f47f1e613", "nxa_8d0eba994ba3094177d4dc1441af4cfc65455368"]
        save_data(data)
    api_keys = data.get("api_keys", [])
    markup = InlineKeyboardMarkup(row_width=1)
    
    for idx, key in enumerate(api_keys):
        masked_key = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else key
        markup.add(ibtn(f"❌ DELETE: {masked_key}", callback_data=f"delapi_{idx}", style="danger"))
        
    markup.add(ibtn("➕ ADD NEW API", callback_data="add_new_api", style="success"))
    markup.add(ibtn("🔙 BACK", callback_data="back_to_admin", style="primary"))
    
    safe_edit(chat_id, f"━━━━━━━━━━━━━━━\n《 🔑 API MANAGEMENT 》\n━━━━━━━━━━━━━━━\nTOTAL APIS: {len(api_keys)}", markup, message_id)

def process_add_api(message, msg_id):
    if message.text == '/cancel': return show_api_manage(message.chat.id)
    data = load_data()
    data.setdefault("api_keys", []).append(message.text.strip())
    save_data(data)
    safe_send(message.chat.id, "✅ API ADDED!")
    time.sleep(1); show_api_manage(message.chat.id)

def show_manage_admins(chat_id, message_id=None):
    data = load_data()
    admins = data.get("extra_admins", [])
    markup = InlineKeyboardMarkup(row_width=1)
    
    for adm in admins:
        markup.add(ibtn(f"❌ REMOVE: {adm}", callback_data=f"deladm_{adm}", style="danger"))
        
    markup.add(ibtn("➕ ADD ADMIN", callback_data="add_new_admin", style="success"))
    markup.add(ibtn("🔙 BACK", callback_data="back_to_admin", style="primary"))
    
    safe_edit(chat_id, f"━━━━━━━━━━━━━━━\n《 👮 MANAGE ADMINS 》\n━━━━━━━━━━━━━━━\nTOTAL EXTRA ADMINS: {len(admins)}", markup, message_id)

def process_add_admin(message, msg_id):
    if message.text == '/cancel': return show_manage_admins(message.chat.id)
    try:
        adm_id = int(message.text.strip())
        data = load_data()
        if adm_id not in data.get("extra_admins", []):
            data.setdefault("extra_admins", []).append(adm_id)
            save_data(data)
            safe_send(message.chat.id, "✅ ADMIN ADDED!")
        else:
            safe_send(message.chat.id, "⚠️ ALREADY AN ADMIN!")
    except:
        safe_send(message.chat.id, "❌ INVALID ID!")
    time.sleep(1); show_manage_admins(message.chat.id)

# ==================== CORE OTP - IMPROVED API SYSTEM ====================

def fetch_numbers(chat_id, service_info, message_id, is_custom=False):
    data = load_data()
    watermark = data.get("watermark", "DXA UNIVERSE")
    main_link = format_url(data.get("main_otp_link", "https://t.me/"))
    
    # --- LOADING MESSAGE SYSTEM ---
    loading_text = f"━━━━━━━━━━━━━━━\n《 ⏳ PROCESSING 》\n━━━━━━━━━━━━━━━\n🔄 <b>PLEASE WAIT...</b>\n<i>FETCHING NUMBERS FROM SERVER...</i>\n━━━━━━━━━━━━━━━"
    
    # নাম্বার খোঁজার আগেই ইউজারকে ওয়েটিং মেসেজ পাঠিয়ে দেওয়া হচ্ছে
    if message_id:
        try: bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=loading_text, parse_mode="HTML")
        except: pass
    else:
        try: 
            msg = bot.send_message(chat_id, loading_text, parse_mode="HTML")
            message_id = msg.message_id
        except: pass
        
    # Dynamic API Management
    api_keys = data.get("api_keys", [])
    if NEXA_API_KEY not in api_keys: api_keys.append(NEXA_API_KEY)
    
    req_limit = data.get("settings", {}).get("num_per_request", 3)
    max_possible = min(len(api_keys), req_limit)
    if max_possible == 0: max_possible = 1

    active_polls[str(chat_id)] = False
    numbers_found = []
    lock = threading.Lock()
    
    def fetch_single(api_key):
        try:
            headers = {'X-API-Key': api_key}
            # টাইমআউট ১৫ থেকে কমিয়ে ৭ করা হলো, যাতে API স্লো থাকলে বট আটকে না থাকে
            # API সার্ভার স্লো হওয়ায় পর্যাপ্ত সময় দেওয়ার জন্য টাইমআউট ২৫ করা হলো
            response = requests.post(f"{BASE_URL}/api/v1/numbers/get", json={"range": service_info['range'], "format": "normal"}, headers=headers, timeout=25)
            res = response.json()
            
            # API সার্ভার আসল কী বলছে সেটা লগে দেখার জন্য প্রিন্ট
            print(f"[{api_key[:6]}...] API Response: {res}") 
            
            if res.get("success"):
                with lock:
                    if len(numbers_found) < max_possible:
                        numbers_found.append({"number": res.get("number"), "number_id": res.get("number_id"), "api_key": api_key, "status": "⏳ WAITING"})
            else:
                print(f"Failed to get number. API Error: {res}")
        except Exception as e:
            print(f"Connection/Timeout Error with API: {e}")
    
    # 🔥 AUTO-RETRY LOOP (3 Times Background Try) 🔥
    for attempt in range(3):
        random.shuffle(api_keys) # Randomly select APIs to balance load
        selected_keys = api_keys[:max_possible]
        
        threads_list = []
        for key in selected_keys:
            if len(numbers_found) >= max_possible: break
            t = threading.Thread(target=fetch_single, args=(key,))
            t.start(); threads_list.append(t)
        
        for t in threads_list: t.join(timeout=10)
        
        if numbers_found: break # Found numbers, exit loop!
        time.sleep(2) # Cooldown before retry
    
    if not numbers_found:
        markup = InlineKeyboardMarkup()
        if is_custom: markup.add(ibtn("❌ CLOSE", callback_data="close_menu", style="danger"))
        else: markup.add(ibtn("🔙 BACK", callback_data="back_to_user_services", style="danger"))
        safe_edit(chat_id, f"━━━━━━━━━━━━━━━\n《 ❌ ERROR 》\n━━━━━━━━━━━━━━━\nNUMBER OUT OF STOCK\nPLEASE TRY AGAIN LATER", markup, message_id)
        return
    
    if is_custom:
        service_info['country_name'] = get_country_from_number(numbers_found[0]['number'])
    
    flag = get_country_flag(service_info['country_name'])
    srv_emoji = emo(service_info['service_name'])
    srv_name_upper = service_info['service_name'].upper()
    country_name_upper = service_info['country_name'].upper()
    
    text = f"━━━━━━━━━━━━━━━\n《 ✅ NUMBERS ALLOCATED 》\n━━━━━━━━━━━━━━━\n📱 SERVICE  {srv_emoji} {srv_name_upper}\n🌎 COUNTRY  {flag} {country_name_upper}\n━━━━━━━━━━━━━━━\n"
    
    for i, num_data in enumerate(numbers_found):
        status = num_data.get("status", "⏳ WAITING")
        raw_num = str(num_data['number']).replace('+', '')
        detected_country = get_country_from_number(raw_num)
        country_code = ""
        for code, country in PHONE_TO_COUNTRY.items():
            if country.lower() == detected_country.lower():
                country_code = code
                break
        if country_code and not raw_num.startswith(country_code):
            full_num = f"+{country_code}{raw_num}"
        else:
            full_num = f"+{raw_num}" if not raw_num.startswith('+') else raw_num
            full_num = f"+{full_num}" if not full_num.startswith('+') else full_num
        num_data['number'] = full_num.replace('+', '')
        text += f"{i+1}️⃣ <code>{full_num}</code>  {status}\n"
    
    text += f"━━━━━━━━━━━━━━━\n🚀 POWERED BY {html.escape(watermark)}\n━━━━━━━━━━━━━━━\n📬 PLEASE WAIT FOR OTP...\n━━━━━━━━━━━━━━━"
    
    markup = InlineKeyboardMarkup(row_width=2)
    if is_custom:
        markup.add(ibtn("🔄 CHANGE", callback_data=f"chgc|{service_info['range']}", style="primary"), 
                   ibtn("📨 OTP GROUP", url=main_link, style="success"))
        markup.add(ibtn("❌ CLOSE", callback_data="close_menu", style="danger"))
    else:
        markup.add(ibtn("🔄 CHANGE", callback_data=f"chg_r|{service_info['srv_id']}|{service_info['cnt_id']}|{service_info['id']}", style="primary"), 
                   ibtn("📨 OTP GROUP", url=main_link, style="success"))
        markup.add(ibtn("🔙 BACK", callback_data=f"usr_c|{service_info['srv_id']}|{service_info['cnt_id']}", style="danger"))
    
    active_polls[str(chat_id)] = {"numbers": numbers_found, "service_info": service_info, "message_id": message_id, "is_custom": is_custom, "watermark": watermark, "main_link": main_link}
    
    safe_edit(chat_id, text, markup, message_id)
    
    for num_data in numbers_found:
        threading.Thread(target=poll_otp_with_status, args=(chat_id, num_data, service_info)).start()

def update_number_status(chat_id, number, status_text, emoji_status):
    if str(chat_id) not in active_polls or not active_polls[str(chat_id)]: return
    poll_data = active_polls[str(chat_id)]
    numbers = poll_data.get("numbers", [])
    message_id = poll_data.get("message_id")
    service_info = poll_data.get("service_info", {})
    watermark = poll_data.get("watermark", "DXA UNIVERSE")
    main_link = poll_data.get("main_link", "https://t.me/")
    is_custom = poll_data.get("is_custom", False)
    
    for num_data in numbers:
        if num_data["number"] == number:
            num_data["status"] = f"{emoji_status} {status_text}"; break
    
    flag = get_country_flag(service_info.get('country_name', ''))
    srv_emoji = emo(service_info.get('service_name', ''))
    srv_name_upper = service_info.get('service_name', '').upper()
    country_name_upper = service_info.get('country_name', '').upper()
    
    text = f"━━━━━━━━━━━━━━━\n《 ✅ NUMBERS ALLOCATED 》\n━━━━━━━━━━━━━━━\n📱 SERVICE  {srv_emoji} {srv_name_upper}\n🌎 COUNTRY  {flag} {country_name_upper}\n━━━━━━━━━━━━━━━\n"
    for i, num_data in enumerate(numbers):
        status = num_data.get("status", "⏳ WAITING")
        raw_num = str(num_data['number']).replace('+', '')
        if not raw_num.startswith('+'):
            raw_num = f"+{raw_num}"
        text += f"{i+1}️⃣ <code>{raw_num}</code>  {status}\n"
    text += f"━━━━━━━━━━━━━━━\n🚀 POWERED BY {html.escape(watermark)}\n━━━━━━━━━━━━━━━"
    
    markup = InlineKeyboardMarkup(row_width=2)
    if is_custom:
        markup.add(ibtn("🔄 CHANGE", callback_data=f"chgc|{service_info.get('range', '')}", style="primary"), 
                   ibtn("📨 OTP GROUP", url=main_link, style="success"))
        markup.add(ibtn("❌ CLOSE", callback_data="close_menu", style="danger"))
    else:
        markup.add(ibtn("🔄 CHANGE", callback_data=f"chg_r|{service_info.get('srv_id', '')}|{service_info.get('cnt_id', '')}|{service_info.get('id', '')}", style="primary"), 
                   ibtn("📨 OTP GROUP", url=main_link, style="success"))
        markup.add(ibtn("🔙 BACK", callback_data=f"usr_c|{service_info.get('srv_id', '')}|{service_info.get('cnt_id', '')}", style="danger"))
    
    try:
        clean_text = clean_html_tags(text)
        bot.edit_message_text(clean_text, chat_id=chat_id, message_id=message_id, parse_mode="HTML", reply_markup=markup)
    except: pass

def poll_otp_with_status(chat_id, num_data, service_info):
    number_id = num_data["number_id"]
    phone_number = num_data["number"]
    api_key = num_data["api_key"]
    headers = {'X-API-Key': api_key}
    timeout = 600
    start_time = time.time()
    original_range = service_info.get('range', '')
    
    if not service_info.get('country_name') or service_info.get('country_name') == 'Universal':
        service_info['country_name'] = get_country_from_number(phone_number)
    
    while time.time() - start_time < timeout:
        if str(chat_id) not in active_polls or not active_polls[str(chat_id)]: return
        try:
            res = requests.get(f"{BASE_URL}/api/v1/numbers/{number_id}/sms", headers=headers, timeout=15)
            s_data = res.json()
            if s_data.get("success") and s_data.get("otp"):
                otp_code = s_data.get("otp")
                full_sms = s_data.get("message", "") or s_data.get("sms", "")
                
                full_otp = str(otp_code)
                match1 = re.search(r'(?:code\D+)?(\d{3,6}[- ]\d{3,6})', full_sms, re.IGNORECASE)
                if match1:
                    full_otp = match1.group(1).strip()
                else:
                    match2 = re.search(r'(?:code|otp|kod)\D+(\d{4,8})', full_sms, re.IGNORECASE)
                    if match2:
                        full_otp = match2.group(1)
                    else:
                        match3 = re.search(r'(\d{4,8})', full_sms)
                        if match3:
                            full_otp = match3.group(1)
                
                if len(full_otp) > len(str(otp_code)):
                    otp_code = full_otp
                
                app_name_from_api = s_data.get("service", "") or s_data.get("app_name", service_info.get('service_name', ''))
                detected_service = detect_service_from_sms(full_sms, app_name_from_api)
                
                if detected_service == "Unknown" and app_name_from_api and app_name_from_api != service_info.get('service_name', ''):
                    detected_service = app_name_from_api.title()
                
                lang_code = detect_language(full_sms)
                update_number_status(chat_id, phone_number, "OTP RECEIVED", "✅")
                
                data = load_data()
                watermark = data.get("watermark", "DXA UNIVERSE")
                
                try:
                    chat = bot.get_chat(chat_id)
                    update_leaderboard(chat_id, chat.first_name)
                except: pass
                
                # --- OTP REWARD SYSTEM ---
                data = load_data()
                uid = str(chat_id)
                reward = float(data.get("settings", {}).get("otp_reward", 5.0))
                current_bal = float(data.get("balances", {}).get(uid, 0.0))
                new_bal = current_bal + reward
                data["balances"][uid] = new_bal
                save_data(data)
                # -------------------------
                
                clean_num = str(phone_number).replace('+', '')
                
                inbox_msg = (
                    f"━━━━━━━━━━━━━━━\n"
                    f"《 📩 NEW OTP 》\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"📱 NUMBER: <code>+{clean_num}</code>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"🔐 OTP: <code>{otp_code}</code>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"📱 SERVICE: {detected_service}\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"📝 FULL SMS:\n{html.escape(full_sms)}\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"💰 BONUS: <b>+{reward} ৳</b>\n"
                    f"💵 NEW BALANCE: <b>{new_bal} ৳</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"🚀 POWERED BY {html.escape(watermark)}"
                )
                safe_send(chat_id, inbox_msg)
                
                masked_num = mask_number(phone_number)
                srv_short = get_short_service(detected_service)
                flag = get_country_flag(service_info.get('country_name', ''))
                cc = get_iso_code(service_info.get('country_name', ''))
                srv_emoji = emo(detected_service)
                
                group_msg = (
                    f"╔═══════════════╗\n"
                    f"║ {srv_emoji} #{srv_short} {flag} #{cc} {masked_num} #{lang_code}\n"
                    f"╚═══════════════╝"
                )
                
                for grp in data.get("forward_groups", []):
                    try:
                        grp_markup = InlineKeyboardMarkup(row_width=1)
                        # গ্রুপের OTP ও Range বাটনগুলো রঙিন করা হলো
                        grp_markup.add(ibtn(f"📋 COPY: {otp_code}", copy_text_str=otp_code, style="success"))
                        grp_markup.add(ibtn(f"📱 RANGE: {original_range}", copy_text_str=original_range, style="primary"))
                        for btn in grp.get("buttons", []):
                            grp_markup.add(ibtn(btn['name'], url=btn['url'], style="primary"))
                        safe_send(grp['chat_id'], group_msg, grp_markup)
                    except: pass
                return
        except: pass
        time.sleep(3)
    
    update_number_status(chat_id, phone_number, "TIMEOUT", "⏰")

# ==================== GLOBAL SMS LISTENER ====================
forwarded_sms_ids = set()

def global_sms_listener():
    while True:
        try:
            data = load_data()
            api_keys = data.get("api_keys", [])
            if NEXA_API_KEY not in api_keys: api_keys.append(NEXA_API_KEY)
            
            for key in api_keys:
                headers = {'X-API-Key': key}
                try:
                    # Note: আপনার API এর ডকুমেন্টেশন অনুযায়ী যদি একসাথে সব মেসেজ পাওয়ার লিংক ভিন্ন হয়, তাহলে নিচের লিংকটি পরিবর্তন করে নিবেন।
                    res = requests.get(f"{BASE_URL}/api/v1/sms/latest", headers=headers, timeout=10)
                    s_data = res.json()
                    
                    if s_data.get("success"):
                        # 'messages' বা 'data' যে নামে এপিআই রেসপন্স দেয় সেটা ব্যবহার করতে হবে
                        messages_list = s_data.get("messages") or s_data.get("data", [])
                        
                        for msg in messages_list:
                            msg_id = msg.get("id") or msg.get("sms_id")
                            
                            if msg_id and msg_id not in forwarded_sms_ids:
                                forwarded_sms_ids.add(msg_id)
                                
                                number = msg.get("number", "Unknown")
                                sms_text = msg.get("sms", "") or msg.get("message", "")
                                otp_code = msg.get("otp", "")
                                app_name = msg.get("service", "") or msg.get("app_name", "")
                                
                                detected_service = detect_service_from_sms(sms_text, app_name)
                                lang_code = detect_language(sms_text)
                                masked_num = mask_number(number)
                                srv_short = get_short_service(detected_service)
                                
                                raw_num = str(number).replace('+', '')
                                detected_country = get_country_from_number(raw_num)
                                flag = get_country_flag(detected_country)
                                cc = get_iso_code(detected_country)
                                srv_emoji = emo(detected_service)
                                
                                # গ্রুপে পাঠানোর মেসেজ টেমপ্লেট
                                group_msg = (
                                    f"╔═══════════════╗\n"
                                    f"║ {srv_emoji} #{srv_short} {flag} #{cc} {masked_num} #{lang_code}\n"
                                    f"╚═══════════════╝"
                                )
                                
                                for grp in data.get("forward_groups", []):
                                    try:
                                        grp_markup = InlineKeyboardMarkup(row_width=1)
                                        if otp_code:
                                            grp_markup.add(ibtn(f"📋 COPY: {otp_code}", copy_text_str=otp_code, style="success"))
                                        for btn in grp.get("buttons", []):
                                            grp_markup.add(ibtn(btn['name'], url=btn['url'], style="primary"))
                                        safe_send(grp['chat_id'], group_msg, grp_markup)
                                    except: pass
                except: pass
        except Exception as e:
            pass
        
        # প্রতি ৫ সেকেন্ড পর পর চেক করবে (এপিআই স্প্যাম এড়াতে ৫-১০ সেকেন্ড রাখা ভালো)
        time.sleep(5)

if __name__ == "__main__":
    try:
        bot.set_my_commands([telebot.types.BotCommand("/start", "🚀 Start Number Bot")])
    except: pass
    
    # গ্লোবাল লিসেনার ব্যাকগ্রাউন্ড থ্রেড চালু করা হলো
    print("🔄 Starting Global SMS Listener...")
    threading.Thread(target=global_sms_listener, daemon=True).start()
    
    print("👑 DXA UNIVERSE - Bot Running with Custom Colorful Buttons! 👑")
    bot.infinity_polling()
