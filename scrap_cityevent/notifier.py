"""
Module for sending email notifications about newly found events.
This module handles both notification emails to the user and registration emails to event organizers.
"""
import os
import smtplib
import logging
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Union, Any

import html as html_module  # Rename the import to avoid conflict

logger = logging.getLogger(__name__)

class EmailNotifier:
    """
    Email notification handler for events.
    
    This class manages sending notification emails about new events to the user
    and provides functionality to generate registration emails to event organizers.
    """
    
    def __init__(
        self, 
        sender_email: str,
        receiver_email: str,
        smtp_server: str = "smtp.gmail.com",
        smtp_port: int = 587,
        city_email: Optional[str] = None,
        name: Optional[str] = None,
        phone: Optional[str] = None
    ):
        """
        Initialize the email notifier.
        
        Args:
            sender_email: The email address to send from
            receiver_email: The email address to send to
            smtp_server: The SMTP server to use
            smtp_port: The SMTP port to use
            city_email: The email address of the event organizer for registrations
            name: User's name for registration emails
            phone: User's phone number for registration emails
        """
        self.sender_email = sender_email
        self.receiver_email = receiver_email
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.city_email = city_email or os.environ.get("CITY_EMAIL", "")
        self.name = name or os.environ.get("NAME", "")
        self.phone = phone or os.environ.get("PHONE", "")
        
    def _create_registration_mailto_link(self, event: Dict[str, Any], use_html: bool = True) -> str:
        """
        Create a mailto link for registering to an event.
        
        Args:
            event: Event dictionary with details
            use_html: Whether to use HTML formatting in the email body
            
        Returns:
            A mailto link with pre-filled subject and body
        """
        # Extract event information
        event_title = event.get('title', 'Event')
        event_date = event.get('date', 'Unknown date')
        
        # Create subject line
        subject = f"Inscription: {event_title} - {event_date}"
        
        if use_html:
            # Create an HTML-formatted email body for desktop clients
            html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <p style="font-size: 16px; color: #444;">Bonjour,</p>
    
    <p>Je souhaite m'inscrire à l'<strong>{event_title}</strong> du <span style="font-weight: bold;">{event_date}</span>.</p>

    <p>Merci d'avance.</p>
    
    <p style="margin-top: 20px; color: #555;">
        Sincères Salutations,<br><br>
        <strong>{self.name}</strong><br>
        {f"Téléphone: {self.phone}" if self.phone else ""}
    </p>
</body>
</html>
"""
            # URL encode the subject and HTML body
            subject_encoded = urllib.parse.quote(subject)
            body_encoded = urllib.parse.quote(html_body)
            
            # Create the full mailto link with HTML content type
            return f"mailto:{self.city_email}?subject={subject_encoded}&body={body_encoded}&content-type=text/html"
        else:
            # Create a plain text email body for mobile clients
            plain_body = f"""
Bonjour,

Je souhaite m'inscrire à l'{event_title} du {event_date}.

Merci d'avance.

Sincères Salutations,
{self.name}
{f"Téléphone: {self.phone}" if self.phone else ""}
"""
            # URL encode the subject and plain text body
            subject_encoded = urllib.parse.quote(subject)
            body_encoded = urllib.parse.quote(plain_body)
            
            # Create the full mailto link with plain text
            return f"mailto:{self.city_email}?subject={subject_encoded}&body={body_encoded}"
    
    def send_notification(
        self, 
        event: Dict[str, Any],
        ask_to_register: bool = True,
        password: Optional[str] = None
    ) -> bool:
        """
        Send an email notification for a newly found event.
        
        Args:
            event: Event dictionary with details
            ask_to_register: Whether to include a registration button
            password: The email password (if not provided, will be read from environment)
            
        Returns:
            True if the email was sent successfully, False otherwise
        """
        if password is None:
            password = os.environ.get("EMAIL_PASSWORD")
            if not password:
                logger.error("No email password provided. Set EMAIL_PASSWORD environment variable or pass as argument.")
                return False
        
        # Extract event information
        event_title = event.get('title', 'Event')
        original_title = event.get('original_title', event_title)
        event_date = event.get('date', 'Unknown date')
        event_info = event.get('info', 'No details available')
        event_link = event.get('link', '#')
        event_found_at = event.get('found_at', '')
        matching_terms = event.get('matching_terms', [])
        
        # Create email
        message = MIMEMultipart("alternative")
        message["Subject"] = f"New Event Alert: {event_title} - {event_date}"
        message["From"] = self.sender_email
        message["To"] = self.receiver_email
        
        # Format the event info with proper line breaks for HTML
        info_html = html_module.escape(event_info).replace('\n', '<br>')
        
        # Create the registration mailto links if registration is enabled
        html_signup_link = ""
        plain_signup_link = ""
        if ask_to_register and self.city_email:
            html_signup_link = self._create_registration_mailto_link(event, use_html=True)
            plain_signup_link = self._create_registration_mailto_link(event, use_html=False)
        
        # Format matching terms if available
        matching_terms_html = ""
        if matching_terms and len(matching_terms) > 1:
            matching_terms_str = ', '.join(matching_terms)
            matching_terms_html = f"""
            <p><strong>🔍 Matched terms:</strong> {html_module.escape(matching_terms_str)}</p>
            """
        
        # Create the HTML version of the message
        event_type = matching_terms[0] if matching_terms else "Event"
        
        email_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; max-width: 650px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #5c85d6;">
                <h1 style="color: #3c4043; margin-top: 0;">New Event Found!</h1>
                <h2 style="color: #5c85d6;">{html_module.escape(event_title)} - {html_module.escape(event_date)}</h2>
                
                <div style="background-color: #ffffff; padding: 15px; border-radius: 4px; margin: 15px 0;">
                    <p><strong>📅 Date:</strong> {html_module.escape(event_date)}</p>
                    
                    {f'<p><strong>📝 Original Title:</strong> {html_module.escape(original_title)}</p>' if original_title != event_title else ''}
                    
                    <div style="margin-top: 15px;">
                        <strong>📋 Event Details:</strong><br>
                        <div style="margin-top: 10px; padding-left: 10px; border-left: 2px solid #eee;">{info_html}</div>
                    </div>
                    <p style="margin-top: 15px;"><strong>🔗 Link:</strong> <a href="{event_link}" style="color: #003092;">{event_link}</a></p>
                    
                    {f'''
                    <div style="margin-top: 20px; text-align: center;">
                        <div style="margin-bottom: 10px;">
                            <a href="{html_signup_link}" style="display: inline-block; background-color: #AC1754; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: bold;">
                                💻 S'inscrire (Ordinateur)
                            </a>
                        </div>
                        <div>
                            <a href="{plain_signup_link}" style="display: inline-block; background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: bold;">
                                📱 S'inscrire (Mobile)
                            </a>
                        </div>
                    </div>
                    ''' if html_signup_link else ''}
                </div>
                
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="color: #666; font-size: 0.9em;">This alert was generated at {event_found_at}</p>
            </div>
        """
        
        # Add information about the registration if available
        if html_signup_link:
            email_html += f"""
            <div style="margin-top: 20px; background-color: #e8f0fe; padding: 15px; border-radius: 8px;">
                <h3 style="color: #1a73e8; margin-top: 0;">Event Registration Information</h3>
                <p>
                    The "Sign Up" buttons will open a new email to <strong>{self.city_email}</strong> with pre-filled information about the event.
                    You can edit the email before sending to add any additional details.
                </p>
                <p>
                    <strong>Desktop vs Mobile:</strong> The desktop button creates an HTML-formatted email, while the mobile button 
                    creates a plain text email that works better on some mobile devices.
                </p>
                <p>
                    <strong>Note:</strong> Some email clients may require you to copy the link manually if the button doesn't work.
                </p>
            </div>
            """
        
        email_html += """
        </body>
        </html>
        """
        
        # Add HTML part to MIMEMultipart message
        message.attach(MIMEText(email_html, "html"))
        
        # Send email
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.ehlo()
                server.starttls()  # Secure the connection
                server.ehlo()
                
                # Try to log in
                try:
                    server.login(self.sender_email, password)
                except smtplib.SMTPAuthenticationError as auth_error:
                    if "Username and Password not accepted" in str(auth_error):
                        logger.error(
                            "Email authentication failed. For Gmail, you need to:\n"
                            "1. Enable 2-Step Verification in your Google Account\n"
                            "2. Create an App Password: Google Account > Security > App passwords\n"
                            "3. Use that App Password instead of your regular password"
                        )
                    raise auth_error
                
                server.sendmail(self.sender_email, self.receiver_email, message.as_string())
            
            logger.info(f"Email sent successfully to {self.receiver_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def send_contact_email(
        self, 
        event: Dict[str, Any],
        owner_email: str,
        message_text: str,
        password: Optional[str] = None
    ) -> bool:
        """
        Send an email to the event owner to sign up for the event.
        
        Args:
            event: Event dictionary with details
            owner_email: The email address of the event owner
            message_text: The message to send to the event owner
            password: The email password (if not provided, will be read from environment)
            
        Returns:
            True if the email was sent successfully, False otherwise
        """
        if password is None:
            password = os.environ.get("EMAIL_PASSWORD")
            if not password:
                logger.error("No email password provided. Set EMAIL_PASSWORD environment variable or pass as argument.")
                return False
        
        # Extract event information
        event_title = event.get('title', 'Event')
        event_date = event.get('date', 'Unknown date')
        event_type = event.get('matching_terms', ['Event'])[0] if event.get('matching_terms') else 'Event'
        
        # Create email
        message = MIMEMultipart("alternative")
        message["Subject"] = f"Registration: {event_title} - {event_date}"
        message["From"] = self.sender_email
        message["To"] = owner_email
        
        # Create the plain text version of your message
        text = f"""
        Hello,
        
        I'd like to register for the event: {event_title} on {event_date}.
        
        {message_text}
        
        Best regards,
        {self.name}
        {f"Phone: {self.phone}" if self.phone else ""}
        """
        
        # Create the HTML version of your message
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <p>Hello,</p>
            <p>I'd like to register for the event: <strong>{html_module.escape(event_title)}</strong> on <strong>{html_module.escape(event_date)}</strong>.</p>
            <p>{html_module.escape(message_text)}</p>
            <p>
                Best regards,<br>
                <strong>{html_module.escape(self.name)}</strong><br>
                {f"Phone: {html_module.escape(self.phone)}" if self.phone else ""}
            </p>
        </body>
        </html>
        """
        
        # Add both parts to the MIMEMultipart message
        message.attach(MIMEText(text, "plain"))
        message.attach(MIMEText(html, "html"))
        
        # Send email
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.ehlo()
                server.starttls()  # Secure the connection
                server.ehlo()
                
                # Try to log in
                try:
                    server.login(self.sender_email, password)
                except smtplib.SMTPAuthenticationError as auth_error:
                    if "Username and Password not accepted" in str(auth_error):
                        logger.error(
                            "Email authentication failed. For Gmail, you need to:\n"
                            "1. Enable 2-Step Verification in your Google Account\n"
                            "2. Create an App Password: Google Account > Security > App passwords\n"
                            "3. Use that App Password instead of your regular password"
                        )
                    raise auth_error
                
                server.sendmail(self.sender_email, owner_email, message.as_string())
            
            logger.info(f"Contact email sent successfully to {owner_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send contact email: {e}")
            return False 