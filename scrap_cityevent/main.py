"""
Main script to run the event scraper and notifier.
"""
import os
import argparse
import logging
from dotenv import load_dotenv
from typing import Dict, List, Optional
import re

from scrap_cityevent.scraper import EventScraper
from scrap_cityevent.notifier import EmailNotifier

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scrap_cityevent.log')
    ]
)
logger = logging.getLogger(__name__)

def parse_search_terms(terms_str: str) -> List[str]:
    """
    Parse a comma-separated string of search terms into a list.
    
    Args:
        terms_str: Comma-separated string of search terms
        
    Returns:
        List of search terms
    """
    if not terms_str:
        return []
    
    # Handle potential trailing commas in the input
    terms_str = terms_str.rstrip(',')
    
    # Split by comma and strip whitespace
    terms = [term.strip() for term in terms_str.split(',')]
    # Remove empty terms
    terms = [term for term in terms if term]
    
    return terms

def main():
    """Main function to run the event scraper and notifier."""
    # Load environment variables from .env file
    load_dotenv()
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Scrape a website for events matching specific search terms and send notifications.')
    parser.add_argument('--url', type=str, help='URL of the website to scrape')
    parser.add_argument('--sender-email', type=str, help='Email address to send from')
    parser.add_argument('--receiver-email', type=str, help='Email address to send to')
    parser.add_argument('--city-email', type=str, help='Email address for event registrations')
    parser.add_argument('--name', type=str, help='Your name to use in email signatures')
    parser.add_argument('--phone', type=str, help='Your phone number')
    parser.add_argument('--smtp-server', type=str, help='SMTP server to use', default='smtp.gmail.com')
    parser.add_argument('--smtp-port', type=int, help='SMTP port to use', default=587)
    parser.add_argument('--max-pages', type=int, help='Maximum number of pages to scrape', default=5)
    parser.add_argument('--search-terms', type=str, help='Comma-separated list of terms to search for in events')
    parser.add_argument('--primary-term', type=str, help='Primary term to use if no search terms provided')
    parser.add_argument('--variants-file', type=str, help='Path to a JSON file containing term variants')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode for more verbose logging')
    parser.add_argument('--exact', action='store_true', help='Use exact matching for search terms', default=True)
    parser.add_argument('--reset', action='store_true', help='Reset the database of processed events')
    args = parser.parse_args()
    
    # Set debug level if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    
    # Get configuration from environment variables if not provided as arguments
    url = args.url or os.environ.get('SCRAPER_URL')
    sender_email = args.sender_email or os.environ.get('SENDER_EMAIL')
    receiver_email = args.receiver_email or os.environ.get('RECEIVER_EMAIL')
    city_email = args.city_email or os.environ.get('CITY_EMAIL')
    name = args.name or os.environ.get('NAME')
    phone = args.phone or os.environ.get('PHONE')
    smtp_server = args.smtp_server or os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = args.smtp_port or int(os.environ.get('SMTP_PORT', '587'))
    max_pages = args.max_pages or int(os.environ.get('MAX_PAGES', '5'))
    primary_term = args.primary_term or os.environ.get('PRIMARY_TERM')
    variants_file = args.variants_file or os.environ.get('VARIANTS_FILE')
    
    # Parse search terms from command line or environment
    search_terms_str = args.search_terms or os.environ.get('SEARCH_TERMS', '')
    search_terms = parse_search_terms(search_terms_str)
    
    # If no search terms provided, use the primary term if available
    if not search_terms and primary_term:
        logger.info(f"No search terms provided, using primary term: '{primary_term}'")
        search_terms = [primary_term]
    
    # Validate required configuration
    if not url:
        logger.error("No URL provided. Set SCRAPER_URL environment variable or provide --url argument.")
        return
    if not sender_email:
        logger.error("No sender email provided. Set SENDER_EMAIL environment variable or provide --sender-email argument.")
        return
    if not receiver_email:
        logger.error("No receiver email provided. Set RECEIVER_EMAIL environment variable or provide --receiver-email argument.")
        return
    
    # For backwards compatibility, we don't require search terms if a variants file is provided
    if not search_terms and not variants_file:
        logger.error("No search terms provided. Set SEARCH_TERMS or PRIMARY_TERM environment variable, or provide --search-terms/--primary-term argument.")
        return
    
    # Ensure data directory exists
    os.makedirs("scrap_cityevent/data", exist_ok=True)
    
    # If variants file is specified, check if it exists
    if variants_file and not os.path.exists(variants_file):
        logger.warning(f"Variants file not found: {variants_file}. Attempting to search with provided search terms only.")
        variants_file = None
    
    # If reset is requested, delete the data file
    data_file = "scrap_cityevent/data/events.json"
    if args.reset and os.path.exists(data_file):
        logger.info(f"Resetting database: {data_file}")
        try:
            os.remove(data_file)
            logger.info("Database reset successful")
        except Exception as e:
            logger.error(f"Failed to reset database: {e}")
    
    # Create scraper and notifier
    scraper = EventScraper(url, max_pages=max_pages, search_terms=search_terms, 
                          debug=args.debug, exact_matching=args.exact,
                          variants_file=variants_file)
    notifier = EmailNotifier(sender_email, receiver_email, smtp_server, smtp_port, 
                           city_email=city_email, name=name, phone=phone)
    
    # Find new events
    logger.info(f"Checking for events matching: '{', '.join(search_terms)}' at {url}...")
    try:
        new_events = scraper.find_new_events()
        logger.info(f"Found {len(new_events)} new events.")
        
        # Send notifications for each new event
        notification_count = 0
        for event in new_events:
            event_id = event['id']
            title = event['title']
            
            # Check if this event has already been notified
            event_record = scraper.processed_events.get(event_id, {})
            if event_record.get('notified', False):
                logger.info(f"Event already notified, skipping: {title}")
                continue
                
            logger.info(f"Sending notification for event: {title}")
            success = notifier.send_notification(event)
            
            if success:
                logger.info(f"Notification sent successfully for event: {event_id}")
                scraper.mark_as_notified(event_id)
                notification_count += 1
            else:
                logger.error(f"Failed to send notification for event: {event_id}")
        
        logger.info(f"Sent {notification_count} notifications out of {len(new_events)} new events found.")
        
        if not new_events:
            logger.info("No new events found.")
    
    except Exception as e:
        logger.exception(f"Error processing events: {e}")
        return

if __name__ == "__main__":
    main() 