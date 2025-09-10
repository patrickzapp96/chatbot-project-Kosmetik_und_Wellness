# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import smtplib
from email.message import EmailMessage
import re
from icalendar import Calendar, Event
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# Globale Variable zur Speicherung des Konversationsstatus pro Benutzer-IP
user_states = {}

# FAQ-Datenbank für das Wellness- und Kosmetikstudio
faq_db = {
    "fragen": [
        {
            "id": 1,
            "kategorie": "Öffnungszeiten",
            "titel": "Öffnungszeiten",
            "keywords": ["öffnungszeiten", "wann", "geöffnet", "offen", "arbeitszeit"],
            "antwort": "Wir sind Montag bis Samstag von 9:00 bis 19:00 Uhr für Sie da. Sonntag ist Ruhetag."
        },
        {
            "id": 2,
            "kategorie": "Terminbuchung",
            "titel": "Termin vereinbaren",
            "keywords": ["termin buchen", "termin vereinbaren", "termin ausmachen", "buchen", "vereinbaren", "ausmachen", "reservieren"],
            "antwort": "Wenn Sie einen Termin vereinbaren möchten, geben Sie bitte zuerst Ihren vollständigen Namen ein."
        },
        {
            "id": 3,
            "kategorie": "Behandlungen",
            "titel": "Behandlungen",
            "keywords": ["behandlungen", "services", "was bieten sie an", "was machen sie", "angebot"],
            "antwort": "Wir bieten eine Vielzahl von Behandlungen an, darunter Gesichtsbehandlungen, Massagen, Maniküre und Pediküre. Wenn Sie eine bestimmte Behandlung buchen möchten, geben Sie dies bitte an."
        },
        {
            "id": 4,
            "kategorie": "Kontakt",
            "titel": "Kontakt",
            "keywords": ["adresse", "wo", "anschrift", "finden", "lage"],
            "antwort": "Unsere Adresse lautet: Wohlfühlstraße 7, 12345 Berlin. Sie finden uns direkt am Marktplatz."
        },
    ],
    "services": [
        "Gesichtsbehandlung", "Massage", "Maniküre", "Pediküre"
    ]
}

# Funktion zum Erstellen der iCal-Datei
def create_ical_event(summary, start_time_str, duration_minutes, description):
    """
    Creates an iCalendar event (.ics file).
    """
    cal = Calendar()
    event = Event()

    # The format of the incoming date_time string is expected to be "YYYY-MM-DD HH:MM"
    dt_format = "%Y-%m-%d %H:%M"
    start_time = datetime.strptime(start_time_str, dt_format)
    end_time = start_time + timedelta(minutes=duration_minutes)

    event.add('summary', summary)
    event.add('dtstart', start_time)
    event.add('dtend', end_time)
    event.add('description', description)

    cal.add_component(event)
    return cal.to_ical()

# Funktion zum Senden der E-Mail mit iCal-Anhang
def send_appointment_request(data):
    """
    Sends an appointment request email with an iCal attachment.
    NOTE: Replace the placeholder values with your own email credentials.
    """
    try:
        sender_email = "your_email@example.com"  # Ersetze dies mit deiner E-Mail-Adresse
        sender_password = "your_app_password"  # Ersetze dies mit deinem App-Passwort
        recipient_email = "studio_owner@example.com"  # Ersetze dies mit der E-Mail-Adresse des Studioinhabers

        msg = EmailMessage()
        msg['Subject'] = f"Terminanfrage für {data['service']} von {data['name']}"
        msg['From'] = sender_email
        msg['To'] = recipient_email

        body = (
            f"Neue Terminanfrage:\n\n"
            f"Name: {data['name']}\n"
            f"E-Mail: {data['email']}\n"
            f"Behandlung: {data['service']}\n"
            f"Datum und Uhrzeit: {data['date_time']}\n\n"
            f"Bitte prüfen Sie die Verfügbarkeit und bestätigen Sie den Termin manuell."
        )
        msg.set_content(body)

        # Create the iCal event and attach it to the email
        ical_content = create_ical_event(
            summary=f"Termin mit {data['name']} für {data['service']}",
            start_time_str=data['date_time'],
            duration_minutes=60, # Standard-Dauer von 60 Minuten
            description=f"Termin für {data['service']} mit {data['name']} ({data['email']})"
        )
        msg.add_attachment(ical_content, maintype='text', subtype='calendar', filename='termin.ics')

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print(f"Fehler beim Senden der E-Mail: {e}")
        return False

# Haupt-Chat-Endpunkt
@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Main chat endpoint to handle user messages.
    """
    user_ip = request.remote_addr
    user_message = request.json.get('message', '').strip().lower()

    if user_ip not in user_states:
        user_states[user_ip] = {"state": "initial", "name": "", "email": "", "service": "", "date_time": ""}

    current_state = user_states[user_ip]["state"]
    response_text = ""

    try:
        if current_state == "initial":
            if any(k in user_message for k in faq_db["fragen"][1]["keywords"]):
                user_states[user_ip]["state"] = "awaiting_name"
                response_text = faq_db["fragen"][1]["antwort"]
            else:
                found_faq = False
                for faq in faq_db["fragen"]:
                    if any(k in user_message for k in faq["keywords"]):
                        response_text = faq["antwort"]
                        found_faq = True
                        break
                if not found_faq:
                    response_text = "Entschuldigung, das habe ich nicht verstanden. Ich kann Ihnen bei der Terminvereinbarung oder bei Fragen zu Öffnungszeiten und Behandlungen helfen."

        elif current_state == "awaiting_name":
            if len(user_message.split()) >= 2:
                user_states[user_ip]["name"] = user_message.title()
                user_states[user_ip]["state"] = "awaiting_email"
                response_text = "Vielen Dank! Bitte geben Sie nun Ihre E-Mail-Adresse ein."
            else:
                response_text = "Bitte geben Sie Ihren vollständigen Namen (Vor- und Nachname) ein."

        elif current_state == "awaiting_email":
            if re.match(r"[^@]+@[^@]+\.[^@]+", user_message):
                user_states[user_ip]["email"] = user_message
                user_states[user_ip]["state"] = "awaiting_service"
                services = ", ".join(faq_db["services"])
                response_text = f"Perfekt. Welche Behandlung wünschen Sie? Wir bieten an: {services}."
            else:
                response_text = "Das scheint keine gültige E-Mail-Adresse zu sein. Bitte versuchen Sie es erneut."

        elif current_state == "awaiting_service":
            matched_service = next((s for s in faq_db["services"] if s.lower() in user_message), None)
            if matched_service:
                user_states[user_ip]["service"] = matched_service
                user_states[user_ip]["state"] = "awaiting_date_time"
                response_text = "Alles klar. Wann möchten Sie den Termin vereinbaren? Bitte geben Sie Datum und Uhrzeit im Format 'JJJJ-MM-TT HH:MM' ein (z.B. 2024-10-27 15:30)."
            else:
                response_text = "Diese Behandlung kenne ich leider nicht. Bitte wählen Sie aus Gesichtsbehandlung, Massage, Maniküre oder Pediküre."
        
        elif current_state == "awaiting_date_time":
            try:
                date_time = datetime.strptime(user_message, "%Y-%m-%d %H:%M")
                user_states[user_ip]["date_time"] = user_message
                user_states[user_ip]["state"] = "awaiting_confirmation"
                
                confirmation_text = (
                    f"Bitte bestätigen Sie Ihre Angaben:\n"
                    f"Name: {user_states[user_ip]['name']}\n"
                    f"E-Mail: {user_states[user_ip]['email']}\n"
                    f"Behandlung: {user_states[user_ip]['service']}\n"
                    f"Datum & Uhrzeit: {user_states[user_ip]['date_time']}\n"
                    f"Ist das korrekt? (Ja/Nein)"
                )
                response_text = confirmation_text
            except ValueError:
                response_text = "Das Datums- oder Zeitformat ist ungültig. Bitte verwenden Sie das Format 'JJJJ-MM-TT HH:MM' (z.B. 2024-10-27 15:30)."

        elif current_state == "awaiting_confirmation":
            if user_message in ["ja", "bestätigen", "korrekt"]:
                request_data = {
                    "name": user_states[user_ip].get("name", "N/A"),
                    "email": user_states[user_ip].get("email", "N/A"),
                    "service": user_states[user_ip].get("service", "N/A"),
                    "date_time": user_states[user_ip].get("date_time", "N/A"),
                }
                
                if send_appointment_request(request_data):
                    response_text = "Vielen Dank! Ihre Terminanfrage wurde erfolgreich übermittelt. Wir werden uns in Kürze bei Ihnen melden."
                else:
                    response_text = "Entschuldigung, es gab ein Problem beim Senden Ihrer Anfrage. Bitte rufen Sie uns direkt an."
                
                user_states[user_ip]["state"] = "initial"
            
            elif user_message in ["nein", "abbrechen", "falsch"]:
                response_text = "Die Terminanfrage wurde abgebrochen. Falls Sie die Eingabe korrigieren möchten, beginnen Sie bitte erneut mit 'Termin vereinbaren'."
                user_states[user_ip]["state"] = "initial"
            
            else:
                response_text = "Bitte antworten Sie mit 'Ja' oder 'Nein'."
    
    except Exception as e:
        print(f"Ein Fehler ist aufgetreten: {e}")
        response_text = "Ein unerwarteter Fehler ist aufgetreten. Bitte versuchen Sie es später erneut."
        user_states[user_ip]["state"] = "initial"
    
    return jsonify({"reply": response_text})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
