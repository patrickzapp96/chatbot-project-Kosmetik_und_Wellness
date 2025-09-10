from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import smtplib
from email.message import EmailMessage
import re
from icalendar import Calendar, Event
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Globale Variable zur Speicherung des Konversationsstatus
user_states = {}

# FAQ-Datenbank für ein Wellness- und Kosmetikstudio
faq_db = {
    "fragen": [
        {
            "id": 1,
            "kategorie": "Öffnungszeiten",
            "titel": "Öffnungszeiten",
            "keywords": ["öffnungszeiten", "wann", "geöffnet", "offen", "arbeitszeit"],
            "antwort": "Wir sind Montag–Freitag von 9:30 bis 19:00 Uhr und Samstag von 10:00 bis 16:00 Uhr für Sie da. Sonntag ist Ruhetag."
        },
        {
            "id": 2,
            "kategorie": "Terminbuchung",
            "titel": "Terminbuchung",
            "keywords": ["termin", "buchen", "vereinbaren", "ausmachen", "reservieren", "online"],
            "antwort": "Wenn Sie einen Termin vereinbaren möchten, geben Sie bitte 'termin vereinbaren' ein oder rufen sie uns an unter 030-987654."
        },
        {
            "id": 3,
            "kategorie": "Leistungen",
            "titel": "Massagen",
            "keywords": ["massage", "wellness", "entspannung", "rückenschmerzen"],
            "antwort": "Wir bieten verschiedene Massagen an, darunter klassische Ganzkörpermassagen, Aromaöl-Massagen und Hot-Stone-Massagen."
        },
        {
            "id": 4,
            "kategorie": "Leistungen",
            "titel": "Gesichtsbehandlungen",
            "keywords": ["gesichtsbehandlung", "kosmetik", "akne", "anti-aging"],
            "antwort": "Unsere Gesichtsbehandlungen reichen von klassischen Reinigungen über Anti-Aging-Therapien bis hin zu speziellen Behandlungen für Problemhaut. Eine individuelle Beratung ist vor jeder Behandlung möglich."
        },
        {
            "id": 5,
            "kategorie": "Leistungen",
            "titel": "Maniküre und Pediküre",
            "keywords": ["maniküre", "pediküre", "nägel", "hand", "fuß", "nagelpflege"],
            "antwort": "Wir bieten professionelle Maniküre und Pediküre an, inklusive Nagelformung, Pflege der Nagelhaut, Lackierung und entspannender Hand- bzw. Fußmassage."
        },
        {
            "id": 6,
            "kategorie": "Produkte",
            "titel": "Produkte",
            "keywords": ["produkte", "verkauf", "kaufen", "creme", "öl"],
            "antwort": "In unserem Studio führen wir hochwertige Pflegeprodukte verschiedener Marken, die Sie auch direkt bei uns erwerben können."
        }
    ],
    "fallback": "Das weiß ich leider nicht. Bitte rufen Sie uns direkt unter 030-123456 an, wir helfen Ihnen gerne persönlich weiter."
}

def send_appointment_request(request_data):
    """
    Diese Funktion sendet eine E-Mail mit der Terminanfrage und einem Kalenderanhang.
    """
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")
    receiver_email = os.environ.get("RECEIVER_EMAIL")

    if not all([sender_email, sender_password, receiver_email]):
        print("E-Mail-Konfiguration fehlt. E-Mail kann nicht gesendet werden.")
        return False

    msg = EmailMessage()
    msg['Subject'] = "Neue Terminanfrage"
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Reply-To'] = request_data.get('email', 'no-reply@example.com')

    # Text der E-Mail
    email_text = f"""
    Hallo Geschäftsführer,
    
    Sie haben eine neue Terminanfrage erhalten:
    
    Name: {request_data.get('name', 'N/A')}
    E-Mail: {request_data.get('email', 'N/A')}
    Service: {request_data.get('service', 'N/A')}
    Datum & Uhrzeit: {request_data.get('date_time', 'N/A')}
    
    Bitte bestätigen Sie diesen Termin manuell im Kalender oder kontaktieren Sie den Kunden direkt.
    """
    msg.set_content(email_text)

    # Erstelle den Kalendereintrag
    cal = Calendar()
    event = Event()

    try:
        start_time_str = request_data.get('date_time')
        # Annahme: request_data['date_time'] hat das Format 'DD.MM.YYYY HH:MM'
        start_time = datetime.strptime(start_time_str, '%d.%m.%Y %H:%M')
    except (ValueError, TypeError) as e:
        print(f"Fehler bei der Konvertierung des Datums: {e}")
        return False

    event.add('dtstart', start_time)
    event.add('summary', f"Termin mit {request_data.get('name', 'Kunde')}")
    event.add('description', f"Service: {request_data.get('service', 'N/A')}\nE-Mail: {request_data.get('email', 'N/A')}")
    event.add('location', 'Musterstraße 12, 10115 Berlin')
    
    cal.add_component(event)

    # Erstelle einen Anhang aus dem Kalenderobjekt
    ics_file = cal.to_ical()
    msg.add_attachment(ics_file, maintype='text', subtype='calendar', filename='Termin.ics')
    
    # Sende die E-Mail
    try:
        with smtplib.SMTP_SSL("smtp.web.de", 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print(f"Fehler beim Senden der E-Mail: {e}")
        return False

# Neue Funktion zum Protokollieren von nicht beantworteten Fragen
def log_unanswered_query(query):
    try:
        with open("unanswered_queries.log", "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] UNANSWERED: {query}\n")
    except Exception as e:
        print(f"Fehler beim Schreiben der Log-Datei: {e}")

@app.route('/api/chat', methods=['POST'])
def chat_handler():
    try:
        if not request.is_json:
            return jsonify({"error": "Fehlende JSON-Nachricht"}), 400

        user_message = request.json.get('message', '').lower()
        user_ip = request.remote_addr
        
        if user_ip not in user_states:
            user_states[user_ip] = {"state": "initial"}
            
        current_state = user_states[user_ip]["state"]
        response_text = faq_db['fallback']

        # Überprüfe den aktuellen Konversationsstatus
        if current_state == "initial":
            
            # WICHTIG: Prüfe zuerst auf Keywords für die Terminbuchung
            if any(keyword in user_message for keyword in ["termin vereinbaren"]):
                response_text = "Möchten Sie einen Termin vereinbaren? Bitte antworten Sie mit 'Ja' oder 'Nein'."
                user_states[user_ip] = {"state": "waiting_for_confirmation_appointment"}
            else:
                # Führe die einfache Keyword-Suche durch
                cleaned_message = re.sub(r'[^\w\s]', '', user_message)
                user_words = set(cleaned_message.split())
                best_match_score = 0
                
                for item in faq_db['fragen']:
                    keyword_set = set(item['keywords'])
                    intersection = user_words.intersection(keyword_set)
                    score = len(intersection)
                    
                    if score > best_match_score:
                        best_match_score = score
                        response_text = item['antwort']
                
                # Wenn kein Match gefunden wurde, logge die Anfrage
                if best_match_score == 0:
                    log_unanswered_query(user_message)

        elif current_state == "waiting_for_confirmation_appointment":
            if user_message in ["ja", "ja, das stimmt", "bestätigen", "ja bitte"]:
                response_text = "Gerne. Wie lautet Ihr vollständiger Name?"
                user_states[user_ip]["state"] = "waiting_for_name"
            elif user_message in ["nein", "abbrechen", "falsch"]:
                response_text = "Die Terminanfrage wurde abgebrochen. Falls Sie die Eingabe korrigieren möchten, beginnen Sie bitte erneut mit 'Termin vereinbaren'."
                user_states[user_ip]["state"] = "initial"
            else:
                response_text = "Bitte antworten Sie mit 'Ja' oder 'Nein'."
                
        elif current_state == "waiting_for_name":
            user_states[user_ip]["name"] = user_message
            response_text = "Vielen Dank. Wie lautet Ihre E-Mail-Adresse?"
            user_states[user_ip]["state"] = "waiting_for_email"

        elif current_state == "waiting_for_email":
            email_regex = r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'
            if re.match(email_regex, user_message):
                user_states[user_ip]["email"] = user_message
                response_text = "Alles klar. Welchen Service möchten Sie buchen (z.B. Massage, Gesichtsbehandlung, Maniküre)?"
                user_states[user_ip]["state"] = "waiting_for_service"
            else:
                response_text = "Das scheint keine gültige E-Mail-Adresse zu sein. Bitte geben Sie eine korrekte E-Mail-Adresse ein."
        
        elif current_state == "waiting_for_service":
            user_states[user_ip]["service"] = user_message
            response_text = "Wann würden Sie den Termin gerne wahrnehmen? Bitte geben Sie das Datum und die Uhrzeit im Format **TT.MM.JJJJ HH:MM** ein, z.B. **15.10.2025 14:00**."
            user_states[user_ip]["state"] = "waiting_for_datetime"

        elif current_state == "waiting_for_datetime":
            user_states[user_ip]["date_time"] = user_message
            
            data = user_states[user_ip]
            response_text = (
                f"Bitte überprüfen Sie Ihre Angaben:\n"
                f"Name: {data.get('name', 'N/A')}\n"
                f"E-Mail: {data.get('email', 'N/A')}\n"
                f"Service: {data.get('service', 'N/A')}\n"
                f"Datum und Uhrzeit: {data.get('date_time', 'N/A')}\n\n"
                f"Möchten Sie die Anfrage so absenden? Bitte antworten Sie mit 'Ja' oder 'Nein'."
            )
            user_states[user_ip]["state"] = "waiting_for_confirmation"
        
        elif current_state == "waiting_for_confirmation":
            if user_message in ["ja", "ja, das stimmt", "bestätigen", "ja bitte"]:
                request_data = {
                    "name": user_states[user_ip].get("name", "N/A"),
                    "email": user_states[user_ip].get("email", "N/A"),
                    "service": user_states[user_ip].get("service", "N/A"),
                    "date_time": user_states[user_ip].get("date_time", "N/A"),
                }
                
                if send_appointment_request(request_data):
                    response_text = "Vielen Dank! Ihre Terminanfrage wurde erfolgreich übermittelt. Wir werden uns in Kürze bei Ihnen melden."
                else:
                    response_text = "Entschuldigung, es gab ein Problem beim Senden Ihrer Anfrage. Bitte rufen Sie uns direkt an unter 030-123456."
                
                user_states[user_ip]["state"] = "initial"
            
            elif user_message in ["nein", "abbrechen", "falsch"]:
                response_text = "Die Terminanfrage wurde abgebrochen. Falls Sie die Eingabe korrigieren möchten, beginnen Sie bitte erneut mit 'Termin vereinbaren'."
                user_states[user_ip]["state"] = "initial"
            
            else:
                response_text = "Bitte antworten Sie mit 'Ja' oder 'Nein'."
        
        return jsonify({"reply": response_text})

    except Exception as e:
        print(f"Ein Fehler ist aufgetreten: {e}")
        return jsonify({"error": "Interner Serverfehler"}), 500

if __name__ == '__main__':
    app.run(debug=True)




