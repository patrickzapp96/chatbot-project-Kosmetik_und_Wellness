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
            "titel": "Termin",
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
    ]
}

def find_faq_answer(message):
    message_lower = message.lower()
    for faq in faq_db["fragen"]:
        for keyword in faq["keywords"]:
            if keyword in message_lower:
                return faq["antwort"]
    return None

def send_appointment_request(data):
    try:
        sender_email = os.getenv("SENDER_EMAIL")
        sender_password = os.getenv("SENDER_PASSWORD")
        receiver_email = os.getenv("RECEIVER_EMAIL")
        
        msg = EmailMessage()
        msg['Subject'] = f"Neue Terminanfrage von {data['name']} über den Chat"
        msg['From'] = sender_email
        msg['To'] = receiver_email
        
        email_text = f"""
        Hallo Team,

        eine neue Terminanfrage wurde über Ihre Webseite gestellt:

        Name: {data['name']}
        E-Mail: {data['email']}
        Gewünschte Behandlung: {data['service']}
        Gewünschte Zeit: {data['date_time']}

        Bitte kontaktieren Sie den Kunden, um den Termin zu bestätigen.
        
        Mit freundlichen Grüßen,
        Ihr automatisierter Assistent
        """
        
        msg.set_content(email_text)
        
        # Kalendereintrag erstellen
        cal = Calendar()
        cal.add('prodid', '-//Terminanfrage//Wellness Studio//DE')
        cal.add('version', '2.0')

        event = Event()
        event.add('summary', f'Termin {data["service"]} für {data["name"]}')
        event.add('dtstart', datetime.strptime(data['date_time'], '%d.%m.%Y %H:%M'))
        event.add('dtend', datetime.strptime(data['date_time'], '%d.%m.%Y %H:%M'))
        event.add('dtstamp', datetime.now())
        event.add('description', f"Kontakt: {data['email']}\nBehandlung: {data['service']}")
        event.add('location', 'Ihre Studio-Adresse, 12345 Musterstadt')
        
        cal.add_component(event)
        
        msg.add_attachment(cal.to_ical(), maintype='text', subtype='calendar', filename='termin.ics')

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        
        return True

    except Exception as e:
        print(f"Fehler beim Senden der E-Mail: {e}")
        return False

@app.route("/api/chat", methods=["POST"])
def chat_handler():
    try:
        user_message = request.json.get("message").lower().strip()
        user_ip = request.remote_addr
        
        # Initialisiere den Status für neue Benutzer
        if user_ip not in user_states:
            user_states[user_ip] = {"state": "initial", "data": {}}

        current_state = user_states[user_ip]["state"]
        response_text = ""

        # Suchen nach einer FAQ-Antwort, wenn nicht im Terminbuchungs-Flow
        if current_state == "initial":
            faq_answer = find_faq_answer(user_message)
            if faq_answer:
                response_text = faq_answer
            elif "termin vereinbaren" in user_message or "termin" in user_message:
                user_states[user_ip]["state"] = "waiting_for_service"
                response_text = "Alles klar. Welchen Service möchten Sie buchen (z.B. Massage, Gesichtsbehandlung, Maniküre)?"
            else:
                response_text = "Ich habe Sie nicht verstanden. Bitte stellen Sie Ihre Frage anders oder rufen Sie uns an unter 030-987654."
        
        elif current_state == "waiting_for_service":
            user_states[user_ip]["data"]["service"] = user_message.title()
            user_states[user_ip]["state"] = "waiting_for_datetime"
            response_text = "Für wann möchten Sie den Termin vereinbaren? Bitte geben Sie das Datum und die Uhrzeit im Format 'tt.mm.jjjj hh:mm' an, z.B. 25.12.2025 10:30."

        elif current_state == "waiting_for_datetime":
            # Validierung des Datumsformats
            datetime_pattern = r"\d{2}\.\d{2}\.\d{4}\s\d{2}:\d{2}"
            if re.match(datetime_pattern, user_message):
                user_states[user_ip]["data"]["date_time"] = user_message
                user_states[user_ip]["state"] = "waiting_for_name"
                response_text = "Vielen Dank. Wie lautet Ihr vollständiger Name?"
            else:
                response_text = "Das Datumsformat ist ungültig. Bitte versuchen Sie es erneut im Format 'tt.mm.jjjj hh:mm'."

        elif current_state == "waiting_for_name":
            user_states[user_ip]["data"]["name"] = user_message.title()
            user_states[user_ip]["state"] = "waiting_for_email"
            response_text = "Perfekt. Und wie lautet Ihre E-Mail-Adresse?"
            
        elif current_state == "waiting_for_email":
            # Validierung der E-Mail-Adresse
            email_pattern = r"[^@]+@[^@]+\.[^@]+"
            if re.match(email_pattern, user_message):
                user_states[user_ip]["data"]["email"] = user_message.lower()
                user_states[user_ip]["state"] = "confirmation"
                
                request_data = user_states[user_ip]["data"]
                response_text = (f"Bitte bestätigen Sie Ihre Angaben: Service: {request_data.get('service')}, "
                                 f"Zeit: {request_data.get('date_time')}, Name: {request_data.get('name')}, "
                                 f"E-Mail: {request_data.get('email')}. Ist das korrekt? (Ja/Nein)")
            else:
                response_text = "Das ist keine gültige E-Mail-Adresse. Bitte geben Sie Ihre E-Mail-Adresse erneut ein."

        elif current_state == "confirmation":
            if user_message in ["ja", "j", "yes"]:
                request_data = {
                    "name": user_states[user_ip]["data"].get("name", "N/A"),
                    "email": user_states[user_ip]["data"].get("email", "N/A"),
                    "service": user_states[user_ip]["data"].get("service", "N/A"),
                    "date_time": user_states[user_ip]["data"].get("date_time", "N/A"),
                }
                
                if send_appointment_request(request_data):
                    response_text = "Vielen Dank! Ihre Terminanfrage wurde erfolgreich übermittelt. Wir werden uns in Kürze bei Ihnen melden."
                else:
                    response_text = "Entschuldigung, es gab ein Problem beim Senden Ihrer Anfrage. Bitte rufen Sie uns direkt an unter 030-987654."
                
                user_states[user_ip]["state"] = "initial"
            
            elif user_message in ["nein", "abbrechen", "falsch"]:
                response_text = "Die Terminanfrage wurde abgebrochen. Falls Sie die Eingabe korrigieren möchten, beginnen Sie bitte erneut mit 'Termin vereinbaren'."
                user_states[user_ip]["state"] = "initial"
            
            else:
                response_text = "Bitte antworten Sie mit 'Ja' oder 'Nein'."
        
        return jsonify({"reply": response_text})

    except Exception as e:
        print(f"Ein Fehler ist aufgetreten: {e}")
        return jsonify({"error": "Ein interner Fehler ist aufgetreten."}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)

